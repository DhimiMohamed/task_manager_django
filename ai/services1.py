import json
import re
import logging
from datetime import date
from django.db.models import Q
from .client import get_ai_client
from .constants import DEFAULT_MODEL, DEFAULT_MODEL_1, DEFAULT_MODEL_4, DEFAULT_MODEL_10, DEFAULT_MODEL_11
from tasks.models import Task, Category
from .tools import TOOLS, create_task, set_task_status, search_tasks_by_date_range


logger = logging.getLogger(__name__)

# ========== Helper Functions ==========
def extract_json_like(text):
    """
    Extracts JSON-like structures from text, handling various formats and malformed JSON.
    
    Args:
        text (str): The text potentially containing JSON data
        
    Returns:
        dict or list: The parsed JSON data, or None if no valid JSON found
    """
    if not text:
        return None
    
    # Try direct JSON parsing first (in case the response is pure JSON)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Common patterns where JSON might be wrapped in markdown or code blocks
    patterns = [
        r'```json\s*(.*?)\s*```',  # Markdown JSON code block
        r'```\s*(.*?)\s*```',      # Generic code block
        r'{(.*)}',                  # Curly brace enclosed
        r'\[(.*)\]',                # Square bracket enclosed
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            # Handle both single matches and groups
            candidate = match[0] if isinstance(match, tuple) and match else match
            if not candidate:
                continue
                
            # Try to parse the candidate
            try:
                # Sometimes the match might be missing outer braces
                if not candidate.strip().startswith('{') and not candidate.strip().startswith('['):
                    candidate = '{' + candidate + '}'
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    
    # Final attempt - look for the first {...} or [...] in the text
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start_idx = text.find(start_char)
        if start_idx == -1:
            continue
            
        end_idx = text.rfind(end_char)
        if end_idx == -1:
            continue
            
        candidate = text[start_idx:end_idx+1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    
    return None


def execute_tool_call(user, tool_name, args):
    """Execute a single tool call and return the result."""
    tool_result = None
    if tool_name == "create_task":
        tool_result = create_task(user, **args)
    elif tool_name == "set_task_status":
        tool_result = set_task_status(user, **args)
    elif tool_name == "search_tasks_by_date_range":
        tool_result = search_tasks_by_date_range(user, **args)
    else:
        return {
            "user_message": f"Unknown tool function: {tool_name}",
            "tool_result": None
        }
    return tool_result


def fallback_tool_call_three_step(user, user_input, model):
    """Three-step fallback tool calling for models without native function calling support."""
    client = get_ai_client()

    # Step 1: Tool Selection (now supports multiple tools)
    tool_names = [tool["function"]["name"] for tool in TOOLS]
    print(f"1")
    stage1_prompt = f"""
You are a task assistant. The user may request multiple actions in one prompt.

Available tools:
{json.dumps(tool_names, indent=2)}

Conversation context:
{user_input}

Analyze the request and identify ALL needed tools. Respond ONLY as JSON with:
{{
  "tools": [
    {{"tool": "tool_name1"}},
    {{"tool": "tool_name2"}},
    ... or {{"tool": null}} if no tools apply
  ]
}} 
if no tools are needed, respond with:
{{
    "user_message": "your response and provide him with the information he needs, but do not use any tools."
}}
""".strip()
    print(f"2")
    response1 = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": stage1_prompt}]
    )
    print(f"++Response from model: {response1.choices[0].message.content}")
    tool_selection = extract_json_like(response1.choices[0].message.content)
    print(f"++tool selection: {tool_selection}")
    if not tool_selection:
        return {
            "user_message": response1.choices[0].message.content,
            "tool_results": []
        }
    
    # Handle both single tool (old format) and multiple tools (new format)
    if isinstance(tool_selection, list):
        tool_selection = tool_selection[0]  # Take first if multiple JSON objects
    
    if "tools" in tool_selection:
        tools_needed = [t["tool"] for t in tool_selection["tools"] if t["tool"]]
    elif "tool" in tool_selection:
        tools_needed = [tool_selection["tool"]] if tool_selection["tool"] else []
    else:
        tools_needed = []
    
    if not tools_needed:
        return {
            "user_message": tool_selection["user_message"] if "user_message" in tool_selection else "No tools needed, but here's the response.",
            "tool_results": []
        }

    # Step 2: Extract Arguments for Each Tool
    today_str = date.today().isoformat()
    categories = Category.objects.filter(user=user)
    category_info = [{"id": cat.id, "name": cat.name} for cat in categories]
    
    stage2_prompt = f"""
The user requested multiple actions. For each needed tool, extract the arguments.

Today's date: {today_str}
User categories: {category_info}

Conversation context:
{user_input}

Tools needed: {json.dumps(tools_needed, indent=2)}

For each tool, here's the schema:
{json.dumps([tool["function"] for tool in TOOLS], indent=2)}

Respond ONLY as JSON in this format:
{{
  "tool_calls": [
    {{
      "tool": "tool_name1",
      "args": {{...}}
    }},
    {{
      "tool": "tool_name2",
      "args": {{...}}
    }}
  ]
}}
""".strip()

    response2 = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": stage2_prompt}]
    )
    print(f"++Response from model: {response2.choices[0].message.content}")
    tool_calls_data = extract_json_like(response2.choices[0].message.content)
    print(f"++Parsed tool calls data: {tool_calls_data}")
    if not tool_calls_data:
        return {
            "user_message": "Failed to parse tool arguments",
            "tool_results": []
        }
    
    if isinstance(tool_calls_data, list):
        tool_calls_data = tool_calls_data[0]  # Take first if multiple JSON objects
    
    tool_calls = tool_calls_data.get("tool_calls", [])
    print(f"++Extracted tool calls: {tool_calls}")
    if not tool_calls:
        return {
            "user_message": "No tool calls were generated",
            "tool_results": []
        }

    # Step 3: Execute All Tools and Generate Final User Response
    tool_results = []
    for call in tool_calls:
        tool_name = call.get("tool")
        args = call.get("args", {})
        
        if not tool_name:
            continue
            
        print(f"+Executing tool: {tool_name} with args: {args}")
        try:
            result = execute_tool_call(user, tool_name, args)
            tool_results.append({
                "tool": tool_name,
                "args": args,
                "result": result
            })
        except Exception as e:
            tool_results.append({
                "tool": tool_name,
                "args": args,
                "error": str(e)
            })

    stage3_prompt = f"""
You are an AI assistant for a task management application. You executed multiple tools with these results:
{json.dumps(tool_results, indent=2)}

Conversation context: {user_input}

Respond ONLY in JSON format like this:
{{
  "user_message": "Your final message summarizing all actions in the user's language",
  "details": [
    "Brief description of action 1",
    "Brief description of action 2"
  ],
  "language": "The language the user is using (e.g., English, Spanish, etc.)"
}}

Make your response clear, concise, and helpful. Summarize all actions taken in the same language the user used in the conversation context.
""".strip()

    response3 = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": stage3_prompt}]
    )

    final_raw = response3.choices[0].message.content
    try:
        final_data = extract_json_like(final_raw)
        return {
            "user_message": final_data.get("user_message", final_raw),
            "details": final_data.get("details", []),
            "tool_results": tool_results
        }
    except Exception:
        return {
            "user_message": final_raw,
            "details": [],
            "tool_results": tool_results
        }


# ========== AI Interaction Functions ==========

def get_ai_response(user, prompt, model=DEFAULT_MODEL_11):
    try:
        print(f"Using fallback model: {model}")
        return fallback_tool_call_three_step(user=user, user_input=prompt, model=model)
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        logger.error(error_msg)
        return {
            "user_message": error_msg,
            "details": [],
            "tool_results": []
        }