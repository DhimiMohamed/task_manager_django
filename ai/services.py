import json
import re
import logging
from datetime import datetime, date, time
from django.db.models import Q
from django.contrib.auth import get_user_model
from .client import get_ai_client
from .constants import DEFAULT_MODEL, DEFAULT_MODEL_1, DEFAULT_MODEL_4, DEFAULT_MODEL_10, DEFAULT_MODEL_11
from tasks.models import Task, Category
from tasks.serializers import TaskSerializer
import time


logger = logging.getLogger(__name__)

# ========== Helper Functions ==========
def validate_due_date(due_date_str):
    """Validate and parse the due_date string into a date object."""
    try:
        return datetime.strptime(due_date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Invalid date format. Use YYYY-MM-DD.")

def extract_json_like(text):
    """
    Try to extract and load the first JSON-like object in text.
    Returns:
        dict: If a valid JSON object is found and parsed
        None: If no valid JSON object is found
    """
    try:
        # Improved pattern to handle nested structures
        match = re.search(r'\{[^{}]*\{[^{}]*}[^{}]*}|{[^{}]*}', text, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            if isinstance(parsed, dict):  # Ensure we only return dicts
                return parsed
    except (json.JSONDecodeError, AttributeError):
        pass
    return None

def search_tasks(user, filters=None):
    """
    Search tasks with filters for:
    - category (ID or name)
    - date (due_date)
    - title (partial match)
    - status
    - priority
    """
    queryset = Task.objects.filter(user=user)
    
    if not filters:
        return queryset
    
    # Category filter (ID only, since name is not in TOOLS spec)
    if 'category_id' in filters:
        queryset = queryset.filter(category_id=filters['category_id'])
    
    # Date filter (due_date)
    if 'due_date' in filters:
        try:
            filter_date = date.fromisoformat(filters['due_date'])
            queryset = queryset.filter(due_date=filter_date)
        except ValueError:
            pass
    
    # Title filter (partial match, case insensitive)
    # if 'title' in filters:
    #     queryset = queryset.filter(title__icontains=filters['title'])
    
    # Status filter
    if 'status' in filters:
        queryset = queryset.filter(status=filters['status'])
    
    # Priority filter
    if 'priority' in filters:
        try:
            priority = int(filters['priority'])
            queryset = queryset.filter(priority=priority)
        except (ValueError, TypeError):
            pass
    
    return queryset.order_by('-priority', 'due_date')

def generate_message(tasks):
    """Helper to generate user-friendly message."""
    if not tasks:
        return "No tasks found."
    
    if len(tasks) == 1:
        task = tasks[0]
        due_date = task.get('due_date', None)
        return f"Found task: '{task['title']}' (Due: {due_date if due_date else 'No deadline'})"
    
    message = f"Found {len(tasks)} tasks:"
    for idx, task in enumerate(tasks, 1):
        message += f"\n{idx}. {task['title']}"
        if task.get('due_date'):
            message += f" (Due: {task['due_date']})"
    return message

# ========== Task CRUD Functions ==========
def create_task(user, **kwargs):
    """Create a task directly via ORM."""
    try:
        logger.info(f"Creating task for user {user.id} with args: {kwargs}")

        if 'due_date' in kwargs:
            kwargs['due_date'] = validate_due_date(kwargs['due_date'])

        category = None
        if 'category_id' in kwargs:
            category = Category.objects.get(id=kwargs['category_id'], user=user)
            logger.info(f"Category found: {category}")

        task = Task.objects.create(
            user=user,
            title=kwargs['title'],
            description=kwargs.get('description', ''),
            due_date=kwargs['due_date'],
            category=category,
            status=kwargs.get('status', 'pending'),
            priority=kwargs.get('priority', 1)
        )
        logger.info(f"Task created: {task.id}")

        return {
            "status": "success",
            "message": f"Task '{task.title}' created successfully (ID: {task.id})."
        }

    except Category.DoesNotExist:
        error_msg = "Category not found or access denied."
        logger.error(error_msg)
        return {
            "status": "error",
            "message": error_msg,
            "error": "invalid_category"
        }

    except Exception as e:
        logger.error(str(e))
        return {
            "status": "error",
            "message": "An error occurred while creating the task.",
            "error": str(e)
        }

def delete_task_by_id(user, task_id):
    """Delete a task by ID if it belongs to the given user."""
    try:
        logger.info(f"Attempting to delete task {task_id} for user {user.id}")

        task = Task.objects.get(id=task_id, user=user)
        task_title = task.title
        task.delete()
        
        logger.info(f"Task {task_id} deleted successfully")
        
        return {
            "status": "success",
            "message": f"Task '{task_title}' (ID: {task_id}) deleted successfully."
        }

    except Task.DoesNotExist:
        error_msg = f"Task not found or access denied (ID: {task_id})."
        logger.error(error_msg)
        return {
            "status": "error",
            "message": error_msg,
            "error": "invalid_task"
        }

    except Exception as e:
        logger.error(f"Error deleting task {task_id}: {str(e)}")
        return {
            "status": "error",
            "message": "An error occurred while deleting the task.",
            "error": str(e)
        }


def delete_task_without_id(user, **kwargs):
    """Delete task(s) matching the given filters."""
    try:
        logger.info(f"Deleting tasks for user {user.id} with filters: {kwargs}")
        
        matching_tasks = search_tasks(user, kwargs)

        if not matching_tasks.exists():
            return {
                "status": "success",
                "message": "No tasks found matching your criteria."
            }

        serializer = TaskSerializer(matching_tasks, many=True)
        serialized_tasks = serializer.data

        return {
            "status": "success",
            "action": "confirm_delete",
            "data": serialized_tasks,
            "count": len(serialized_tasks),
            "message": generate_message(serialized_tasks)
        }

    except Exception as e:
        logger.error(str(e))
        return {
            "status": "error",
            "message": "An error occurred while deleting tasks.",
            "error": str(e)
        }


def set_task_status(user, **kwargs):
    """Update status of task(s) matching the given filters."""
    try:
        logger.info(f"Setting task status for user {user.id} with args: {kwargs}")
        
        status = kwargs.pop('status')
        status_mapping = {
            0: 'pending',
            1: 'in_progress',
            2: 'completed',
        }

        if status not in status_mapping:
            valid_options = [f"{k}={v}" for k, v in status_mapping.items()]
            return {
                "status": "error",
                "message": f"Invalid status '{status}'. Valid options are: {', '.join(valid_options)}",
                "error": "invalid_status"
            }

        status_str = status_mapping[status]
        matching_tasks = search_tasks(user, kwargs)

        if not matching_tasks.exists():
            return {
                "status": "success",
                "message": "No tasks found matching your criteria."
            }

        updated_count = matching_tasks.update(status=status_str)

        return {
            "status": "success",
            "message": f"Updated {updated_count} task(s) to status '{status_str}'."
        }

    except Exception as e:
        logger.error(str(e))
        return {
            "status": "error",
            "message": "An error occurred while updating task status.",
            "error": str(e)
        }

    # ========== Tools definition ==========
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a new task for the user. Requires a title and due date (YYYY-MM-DD). Optional fields: description, category_id, status (0=pending, 1=in_progress, 2=completed), priority (1-3).",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Title of the task"},
                    "description": {"type": "string", "description": "Detailed description of the task"},
                    "due_date": {"type": "string", "format": "date", "description": "Due date in YYYY-MM-DD format"},
                    "start_time": {"type": "string", "format": "time", "description": "Start time of the task in HH:MM:SS format (optional)"},
                    "end_time": {"type": "string", "format": "time", "description": "End time of the task in HH:MM:SS format (optional)"},
                    "category_id": {"type": "integer", "description": "ID of the category this task belongs to"},
                    "status": {"type": "integer", "enum": [0, 1, 2], "description": "Status of the task (0=pending, 1=in_progress, 2=completed)"},
                    "priority": {"type": "integer", "description": "Priority level (1-3, where 1 is highest)"}
                },
                "required": ["title", "due_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task_without_id",
            "description": "Delete task(s) matching the given filters. Provide at least one filter (title, due_date, category_id, status, or priority) to identify the task(s) to delete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Title of the task to delete"},
                    "due_date": {"type": "string", "format": "date", "description": "Due date of the task to delete (YYYY-MM-DD)"},
                    "category_id": {"type": "integer", "description": "Category ID of the task(s) to delete"},
                    "status": {"type": "integer", "enum": [0, 1, 2], "description": "Status of the task(s) to delete (0=pending, 1=in_progress, 2=completed)"},
                    "priority": {"type": "integer", "description": "Priority level of the task(s) to delete (1-3)"}
                },
                "required": []  
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task_by_id",
            "description": "Delete a task by its unique ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "The ID of the task to delete."}
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_task_status",
            "description": "Update the status of task(s) matching the given filters. Provide filters (due_date, category_id, or priority) to identify the task(s) and the new status (0=pending, 1=in_progress, 2=completed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "due_date": {"type": "string", "format": "date", "description": "Due date of the task to update (YYYY-MM-DD)"},
                    "category_id": {"type": "integer", "description": "Category ID of the task(s) to update"},
                    "priority": {"type": "integer", "description": "Priority level of the task(s) to update (1-3)"},
                    "status": {
                        "type": "integer",
                        "enum": [0, 1, 2],
                        "description": "New status to set for the matching task(s) (0=pending, 1=in_progress, 2=completed)."
                    }
                },
                "required": ["status"]  
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_task_by_id",
            "description": "Update a task by its unique ID. All fields are optional except task_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "The ID of the task to update."},
                    "title": {"type": "string", "description": "New title of the task"},
                    "description": {"type": "string", "description": "New detailed description of the task"},
                    "due_date": {"type": "string", "format": "date", "description": "New due date in YYYY-MM-DD format"},
                    "start_time": {"type": "string", "format": "time", "description": "New start time of the task in HH:MM:SS format"},
                    "end_time": {"type": "string", "format": "time", "description": "New end time of the task in HH:MM:SS format"},
                    "category_id": {"type": "integer", "description": "New category ID for the task"},
                    "status": {"type": "integer", "enum": [0, 1, 2], "description": "New status of the task (0=pending, 1=in_progress, 2=completed)"},
                    "priority": {"type": "integer", "description": "New priority level (1-3, where 1 is highest)"}
                },
                "required": ["task_id"]
            }
        }
    }
]
def fallback_tool_call_three_step(user, user_input, model):
    """Three-step fallback tool calling for models without native function calling support."""
    client = get_ai_client()

    # Step 1: Tool Selection
    tool_names = [tool["function"]["name"] for tool in TOOLS]
    stage1_prompt = f"""
You are a task assistant.

Choose the most appropriate tool for this request, or null if none apply:
{tool_names}

Conversation context:
{user_input}

Respond ONLY as JSON:
{{"tool": "tool_name"}} or {{"tool": null}}
""".strip()
    print(f"0")
    response1 = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": stage1_prompt}]
    )
    print(f"1")
    tool_selection = extract_json_like(response1.choices[0].message.content)
    tool_name = tool_selection.get("tool")
    print(f"+Tool selected: {tool_name}")
    if not tool_name:
        return {
            "user_message": response1.choices[0].message.content,
            "tool_result": None
        }  # No matching tool — just return the fallback message

    # Step 2: Extract Tool Arguments
    today_str = date.today().isoformat()
    categories = Category.objects.filter(user=user)
    category_info = [{"id": cat.id, "name": cat.name} for cat in categories]
    tool_def = next(tool["function"] for tool in TOOLS if tool["function"]["name"] == tool_name)

    stage2_prompt = f"""
Tool selected: {tool_name}

Tool description:
{tool_def["description"]}

Tool schema:
{json.dumps(tool_def["parameters"], indent=2)}

Today's date: {today_str}
User categories: {category_info}

Conversation context:
{user_input}

Respond ONLY as JSON in this format:
{{"tool": "{tool_name}", "args": {{...}}}}
""".strip()

    response2 = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": stage2_prompt}]
    )
    print(f"2")
    tool_call = extract_json_like(response2.choices[0].message.content)
    args = tool_call.get("args", {})
    print(f"+Tool call arguments: {args}")

    # Step 3: Execute Tool and Generate Final User Response
    tool_result = None
    if tool_name == "create_task":
        tool_result = create_task(user, **args)
    elif tool_name == "delete_task_without_id":
        print(f"---d1")
        tool_result = delete_task_without_id(user, **args)
        print(f"---d2 tool_result: {tool_result}")
    elif tool_name == "delete_task_by_id":
        print(f"---d1")
        tool_result = delete_task_by_id(user, args["task_id"])
        print(f"---d2 tool_result: {tool_result}")
    elif tool_name == "set_task_status":
        tool_result = set_task_status(user, **args)
    else:
        return {
            "user_message": f"Unknown tool function: {tool_name}",
            "tool_result": None
        }
    print(f"+Tool result: {tool_result}")
    stage3_prompt = f"""
You executed the tool `{tool_name}` with arguments:
{json.dumps(args, indent=2)}

Result from the tool:
{json.dumps(tool_result, indent=2)}

Respond ONLY in JSON format like this:
{{"user_message": "Your final message to the user."}}

Make it clear, concise, and helpful.
""".strip()

    response3 = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": stage3_prompt}]
    )
    print(f"3")

    final_raw = response3.choices[0].message.content
    print(f"+Final raw response: {final_raw}")
    try:
        final_data = extract_json_like(final_raw)
        return {
            "user_message": final_data.get("user_message", final_raw),
            "tool_result": tool_result
        }
    except Exception:
        return {
            "user_message": final_raw,
            "tool_result": tool_result
        }  # Fallback to raw string if parsing fails


# ========== AI Interaction Functions ==========
def build_tool_prompt(user_input, user):
    """Construct a prompt that guides the AI to return a tool-callable JSON."""
    categories = Category.objects.filter(user=user)
    category_info = [{"id": cat.id, "name": cat.name} for cat in categories]
    today_str = date.today().isoformat()

    prompt = f"""
    Analyze this user request and respond with a JSON object containing:
    - 'tool': The name of the tool to use (one of: {[tool['function']['name'] for tool in TOOLS]}).
    - 'args': The arguments for the tool (key-value pairs).

    Today's date is {today_str}.
    User categories: {category_info}

    Example:
    {{
        "tool": "create_task",
        "args": {{
            "title": "Finish report",
            "due_date": "2023-12-31",
            "category_id": 3
        }}
    }}

    User request: {user_input}
    """
    return prompt.strip()

def get_ai_response(user, prompt, model=DEFAULT_MODEL_11):
    """Get AI response, handling both tool-supported and fallback models."""
    client = get_ai_client()

    TOOL_SUPPORTED_MODELS = [
        "openai/gpt-4", "openai/gpt-4-0613", "openai/gpt-4-1106-preview",
        "openai/gpt-3.5-turbo-1106",
        "anthropic/claude-3-opus-20240229", 
    ]

    categories = Category.objects.filter(user=user)
    category_info = [{"id": cat.id, "name": cat.name} for cat in categories]
    today_str = date.today().isoformat()

    system_message = f"""
    You are an AI assistant for a task management application. Your role is to:
    - Create, update, delete, and search for tasks.
    - Use the provided tools to interact with the task system.
    - Respond in a helpful, concise, and user-friendly manner.

    Today's date: {today_str}
    User's available categories: {category_info}
    """

    messages = [
        {"role": "system", "content": system_message.strip()},
        {"role": "user", "content": prompt}
    ]

    try:
        if model in TOOL_SUPPORTED_MODELS:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto"
            )
            print(f"+Model response: {response}")
            message = response.choices[0].message

            # Handle tool call (function calling)
            if hasattr(message, 'tool_calls') and message.tool_calls:
                tool_call = message.tool_calls[0]
                func_name = tool_call.function.name
                print(f"+Tool call detected: {func_name}")
                kwargs = json.loads(tool_call.function.arguments)
                print(f"+Tool call arguments: {kwargs}")

                # Call the appropriate function
                tool_result = None
                if func_name == "create_task":
                    tool_result = create_task(user, **kwargs)
                elif func_name == "delete_task_without_id":
                    tool_result = delete_task_without_id(user, **kwargs)
                elif func_name == "set_task_status":
                    tool_result = set_task_status(user, **kwargs)
                else:
                    return {"status": "error", "message": f"Unknown tool function: {func_name}"}

                print(f"+Tool result: {tool_result}")

                # Append tool result back as function response
                messages.append({
                    "role": "assistant",
                    "tool_calls": [tool_call.model_dump()]
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result)
                })

                # Let model generate final response to user
                final_response = client.chat.completions.create(
                    model=model,
                    messages=messages
                )
                print(final_response)
                print(f"Final response: {final_response.choices[0].message.content}")
                return final_response.choices[0].message.content

            # If no tool was called, just return the raw message
            print(f"Model response without tool call: {message.content}")
            return message.content

        else:
            print(f"Using fallback model: {model}")
            return fallback_tool_call_three_step(user=user, user_input=prompt, model=model)
            # # Fallback for non-tool models
            # tool_prompt = build_tool_prompt(prompt, user)
            # response = client.chat.completions.create(
            #     model=model,
            #     messages=[{"role": "user", "content": tool_prompt}]
            # )
            # content = response.choices[0].message.content
            # print(f"+Fallback model response: {content}")
            # print("\n")
            # data = extract_json_like(content)

            # if data and isinstance(data, dict):
            #     func_name = data.get("tool")
            #     args = data.get("args", {})

            #     tool_result = None
            #     if func_name == "create_task":
            #         tool_result = create_task(user, **args)
            #     elif func_name == "delete_task_without_id":
            #         tool_result = delete_task_without_id(user, **args)
            #     elif func_name == "set_task_status":
            #         tool_result = set_task_status(user, **args)
            #     else:
            #         return {"status": "error", "message": f"Unknown tool function: {func_name}"}
            #     print(f"+Tool result: {tool_result}")
            #     print("\n")

            #     # Simulate tool interaction messages
            #     tool_call_message = {
            #         "role": "assistant",
            #         "content": content  # Simulated tool call output
            #     }
            #     tool_result_message = {
            #         "role": "tool",
            #         "content": json.dumps(tool_result)
            #     }

            #     final_messages = [
            #         {"role": "system", "content": system_message.strip()},
            #         {"role": "user", "content": prompt},
            #         tool_call_message,
            #         tool_result_message
            #     ]

            #     final_response = client.chat.completions.create(
            #         model=model,
            #         messages=final_messages
            #     )
            #     # print(f"+Final response after tool call: {final_response}")
            #     print("\n")
            #     return final_response.choices[0].message.content
            

            # return content  # Fallback if no proper JSON found

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        logger.error(error_msg)
        return error_msg
