import ollama
import json
import re

class TaskAIService:
    """Handles AI-based task extraction using LLaMA 3.1 with Ollama."""

    @staticmethod
    def extract_json_from_text(response_text: str):
        """
        Extracts JSON content from a response string.
        
        Args:
            response_text (str): The raw response from the AI model.

        Returns:
            dict: Parsed JSON data or None if extraction fails.
        """
        # Find the first JSON-like structure using regex
        match = re.search(r"\{.*\}", response_text, re.DOTALL)
        
        if match:
            try:
                return json.loads(match.group())  # Extract and parse the JSON part
            except json.JSONDecodeError:
                return None  # Return None if parsing fails
        
        return None  # Return None if no JSON found

    @staticmethod
    def extract_task_details(task_description: str):
        """
        Uses LLaMA 3.1 to extract structured task details from a description.

        Args:
            task_description (str): The raw task description.

        Returns:
            dict: Extracted details with title, due_date, priority, category.
        """
        prompt = f"""
    Extract structured details from the following task description:
    "{task_description}"

    Return only a valid JSON object with the following fields and no extra text:
    {{
        "title": "Task Title",
        "due_date": "YYYY-MM-DD" (or null if not specified),
        "start_time": "HH:MM:00" (or null if not specified),
        "end_time": "HH:MM:00" (or null if not specified),
        "priority": 1 (1=Low, 2=Medium, 3=High),
        "category": "Category Name" (or null if not specified)
    }}
    """


        response = ollama.generate(model="llama3.1", prompt=prompt)
        # Extract JSON from response
        extracted_data = TaskAIService.extract_json_from_text(response["response"])

        if extracted_data:
            return {
                "title": extracted_data.get("title", "Untitled Task"),
                "due_date": extracted_data.get("due_date"),
                "priority": extracted_data.get("priority", 1),
                "category": extracted_data.get("category"),
            }

        return None  # Return None if extraction failed
