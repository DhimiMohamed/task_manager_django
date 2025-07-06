# task_manager/activity/models.py
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist

class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Created'),
        ('update', 'Updated'),
        ('delete', 'Deleted'),
        ('move', 'Moved'),
        ('comment', 'Commented'),
        ('complete', 'Completed'),
        ('add', 'Added'),
        ('status_change', 'Status Changed'),
        ('file_upload', 'File Uploaded'),
        ('recurrence_created', 'Recurrence Created'),
        ('recurrence_triggered', 'Recurrence Triggered'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='activities'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Generic foreign key for the object being tracked
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Project association for filtering activities by project
    project = models.ForeignKey(
        'projects.Project',  # Adjust the app name if different
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='activity_logs'
    )
    
    from_state = models.CharField(max_length=50, blank=True, null=True)
    to_state = models.CharField(max_length=50, blank=True, null=True)
    comment_text = models.TextField(blank=True, null=True)
    attachment_info = models.JSONField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = 'Activity Logs'
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['project', '-timestamp']),  # Index for project filtering
            models.Index(fields=['user', '-timestamp']),     # Index for user filtering
        ]

    @property
    def safe_content_object(self):
        """Safely returns the content object or None if deleted"""
        try:
            return self.content_object
        except (AttributeError, ObjectDoesNotExist):
            return None

    def __str__(self):
        user_email = self.user.email if self.user else '[no user]'
        obj = self.safe_content_object
        return f"{user_email} {self.action} {obj if obj else '[deleted]'} at {self.timestamp}"