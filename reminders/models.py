from django.db import models
from tasks.models import Task  # Import your Task model

class Reminder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    reminder_time = models.DateTimeField()
    
    # Status fields for each method (optional but recommended)
    email_status = models.CharField(
        max_length=50, 
        choices=STATUS_CHOICES, 
        default='pending',
        blank=True,
        null=True
    )
    in_app_status = models.CharField(
        max_length=50, 
        choices=STATUS_CHOICES, 
        default='pending',
        blank=True,
        null=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reminder for {self.task.title}"