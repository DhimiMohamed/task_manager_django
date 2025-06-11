import logging
from datetime import datetime, date
# from django.contrib.auth import get_user_model
# from .client import get_ai_client
# from .constants import DEFAULT_MODEL, DEFAULT_MODEL_1, DEFAULT_MODEL_4, DEFAULT_MODEL_10, DEFAULT_MODEL_11
from tasks.models import Task, Category

logger = logging.getLogger(__name__)

def validate_due_date(due_date_str):
    """Validate and parse the due_date string into a date object."""
    try:
        return datetime.strptime(due_date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Invalid date format. Use YYYY-MM-DD.")

def search_tasks(user, filters=None):
    """
    Search tasks with filters for:
    - category (ID or name)
    - date (due_date)
    - status
    - date range (start_date and end_date)
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
    
    # Date range filter
    if 'start_date' in filters and 'end_date' in filters:
        try:
            start_date = date.fromisoformat(filters['start_date'])
            end_date = date.fromisoformat(filters['end_date'])
            queryset = queryset.filter(due_date__range=(start_date, end_date))
        except ValueError:
            pass
    
    # Status filter
    if 'status' in filters:
        queryset = queryset.filter(status=filters['status'])
    
    return queryset.order_by('-priority', 'due_date')

def generate_message(tasks):
    """Helper to generate user-friendly message."""
    if not tasks:
        return "No tasks found."
    
    if len(tasks) == 1:
        task = tasks[0]
        due_date = task.due_date.strftime("%Y-%m-%d") if task.due_date else None
        return f"Found task: '{task.title}' (Due: {due_date if due_date else 'No deadline'}) (Category: {task.category.name if task.category else 'No category'})"
    
    message = f"Found {len(tasks)} tasks:"
    for idx, task in enumerate(tasks, 1):
        due_date_str = task.due_date.strftime("%Y-%m-%d") if task.due_date else 'No deadline'
        message += f"\n{idx}. {task.title} (Due: {due_date_str}) (Category: {task.category.name if task.category else 'No category'})"
    return message

# ========== Task CRUD Functions ==========
def create_task(user, **kwargs):
    """Create a task directly via ORM."""
    try:
        logger.info(f"Creating task for user {user.id} with args: {kwargs}")

        # Validate and parse date/time fields
        if 'due_date' in kwargs:
            kwargs['due_date'] = validate_due_date(kwargs['due_date'])
        
        if 'start_time' in kwargs:
            try:
                kwargs['start_time'] = datetime.strptime(kwargs['start_time'], "%H:%M:%S").time()
            except ValueError:
                raise ValueError("Invalid start_time format. Use HH:MM:SS.")
        
        if 'end_time' in kwargs:
            try:
                kwargs['end_time'] = datetime.strptime(kwargs['end_time'], "%H:%M:%S").time()
            except ValueError:
                raise ValueError("Invalid end_time format. Use HH:MM:SS.")

        category = None
        if 'category_id' in kwargs:
            category = Category.objects.get(id=kwargs['category_id'], user=user)
            logger.info(f"Category found: {category}")

        task = Task.objects.create(
            user=user,
            title=kwargs['title'],
            description=kwargs.get('description', ''),
            due_date=kwargs.get('due_date'),
            start_time=kwargs.get('start_time'),
            end_time=kwargs.get('end_time'),
            category=category,
            status=kwargs.get('status', 'pending'),
            priority=kwargs.get('priority', 1)
        )
        logger.info(f"Task created: {task.id}")

        return {
            "status": "success",
            "message": f"Task '{task.title}' created successfully."
        }

    except Category.DoesNotExist:
        error_msg = "Category not found or access denied."
        logger.error(error_msg)
        return {
            "status": "error",
            "message": error_msg,
            "error": "invalid_category"
        }
    except ValueError as e:
        logger.error(str(e))
        return {
            "status": "error",
            "message": str(e),
            "error": "invalid_format"
        }
    except Exception as e:
        logger.error(str(e))
        return {
            "status": "error",
            "message": "An error occurred while creating the task.",
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

def search_tasks_by_date_range(user, start_date, end_date):
    """
    Search for tasks within a specific date range.
    Returns tasks due between start_date and end_date (inclusive).
    """
    try:
        start_date_obj = validate_due_date(start_date)
        end_date_obj = validate_due_date(end_date)
        
        # Ensure end_date is not before start_date
        if end_date_obj < start_date_obj:
            return {
                "status": "error",
                "message": "End date cannot be before start date."
            }
            
        filters = {
            'start_date': start_date,
            'end_date': end_date
        }
        tasks = search_tasks(user, filters)
        
        message = generate_message(tasks)
        
        return {
            "status": "success",
            "message": message,
            "count": tasks.count()
        }
        
    except ValueError as e:
        return {
            "status": "error",
            "message": str(e)
        }
    except Exception as e:
        logger.error(f"Error in search_tasks_by_date_range: {str(e)}")
        return {
            "status": "error",
            "message": "An error occurred while searching tasks."
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
            "name": "search_tasks_by_date_range",
            "description": "Search for tasks within a specific date range. Returns tasks due between start_date and end_date (inclusive). Use this to answer questions about user's day, week, or specific date ranges.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string", 
                        "format": "date", 
                        "description": "The start date of the range in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string", 
                        "format": "date", 
                        "description": "The end date of the range in YYYY-MM-DD format"
                    }
                },
                "required": ["start_date", "end_date"]
            }
        }
    }
]