# task_manager/activity/signals.py
from django.db.models.signals import post_save, pre_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.utils.functional import cached_property
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from .models import ActivityLog
from tasks.models import Task
from .middleware import get_current_user

# Dictionary of fields to ignore when logging changes
IGNORED_FIELDS = {
    'Project': ['created_at', 'updated_at'],
    'Team': ['created_at']
}

ALLOWED_APPS = ('tasks', 'projects', 'teams')

class ModelTracker:
    """Helper class to track model changes"""
    
    @cached_property
    def content_type(self):
        return ContentType.objects.get_for_model(self)

    def get_field_diff(self, old_instance, new_instance):
        diff = {}
        for field in new_instance._meta.fields:
            field_name = field.name
            if field_name in IGNORED_FIELDS.get(new_instance.__class__.__name__, []):
                continue
            
            old_value = getattr(old_instance, field_name, None)
            new_value = getattr(new_instance, field_name, None)
            
            if old_value != new_value:
                diff[field_name] = {
                    'from': str(old_value),
                    'to': str(new_value)
                }
        return diff

def get_project_from_instance(instance):
    """Extract project from various model instances"""
    # Direct project reference
    if hasattr(instance, 'project') and instance.project:
        return instance.project
    
    # Task model - get project from task
    if hasattr(instance, 'project_id') and instance.project_id:
        return getattr(instance, 'project', None)
    
    # Comment model - get project through task
    if hasattr(instance, 'task') and instance.task:
        return getattr(instance.task, 'project', None)
    
    # FileAttachment model - get project through task
    if hasattr(instance, 'task') and instance.task:
        return getattr(instance.task, 'project', None)
    
    # Team model - might need to handle differently based on your structure
    if instance.__class__.__name__ == 'Team':
        # If team has projects, you might need to handle multiple projects
        # For now, return None or handle based on your business logic
        return None
    
    # Project model - return itself
    if instance.__class__.__name__ == 'Project':
        return instance
    
    return None

# Core signal handlers
@receiver(pre_save)
def pre_save_handler(sender, instance, **kwargs):
    """Capture state before save"""
    if not hasattr(instance, '_pre_save_state'):
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._pre_save_state = old_instance
        except (ObjectDoesNotExist, sender.DoesNotExist):
            instance._pre_save_state = None

@receiver(post_save)
def post_save_handler(sender, instance, created, **kwargs):
    if sender.__module__.split('.')[0] not in ALLOWED_APPS:
        return  # Avoid infinite recursion
    
    # Get user in priority order:
    # 1. last_modified_by from instance
    # 2. current request user
    # 3. None (will be set to [no user])
    user = getattr(instance, 'last_modified_by', None) or get_current_user()
    
    tracker = ModelTracker()
    action = 'create' if created else 'update'
    
    changes = {}
    if not created and hasattr(instance, '_pre_save_state'):
        old_instance = instance._pre_save_state
        changes = tracker.get_field_diff(old_instance, instance)
    
    # Skip logging if no meaningful changes
    if not created and not changes:
        return
    
    # Get project from instance
    project = get_project_from_instance(instance)
    
    with transaction.atomic():
        ActivityLog.objects.create(
            user=user,
            action=action,
            content_object=instance,
            from_state=str(instance._pre_save_state) if not created else None,
            to_state=str(instance) if not created else None,
            attachment_info=changes if changes else None,
            project=project  # Add project to activity log
        )

@receiver(post_delete)
def post_delete_handler(sender, instance, **kwargs):
    """Log deletions"""
    if sender.__module__.split('.')[0] not in ALLOWED_APPS:
        return
    
    tracker = ModelTracker()
    user = getattr(instance, 'last_modified_by', None)
    project = get_project_from_instance(instance)
    
    ActivityLog.objects.create(
        user=user,
        action='delete',
        content_object=instance,
        from_state=str(instance),
        to_state='Deleted',
        project=project  # Add project to activity log
    )

# Custom signal handlers for specific models
@receiver(m2m_changed, sender=Task.depends_on.through)
def log_task_dependencies(sender, instance, action, pk_set, **kwargs):
    """Log task dependency changes"""
    if action not in ['post_add', 'post_remove', 'post_clear']:
        return
    
    verb = {
        'post_add': 'added',
        'post_remove': 'removed',
        'post_clear': 'cleared'
    }[action]
    
    project = get_project_from_instance(instance)
    
    ActivityLog.objects.create(
        user=getattr(instance, 'last_modified_by', None),
        action='update',
        content_object=instance,
        comment_text=f"Dependencies {verb} for task",
        project=project  # Add project to activity log
    )

# Status change handler (needs custom signal)
def status_change_handler(sender, instance, old_status, new_status, **kwargs):
    """Handle status changes from custom signal"""
    project = get_project_from_instance(instance)
    
    ActivityLog.objects.create(
        user=getattr(instance, 'last_modified_by', None),
        action='status_change',
        content_object=instance,
        from_state=old_status,
        to_state=new_status,
        project=project  # Add project to activity log
    )