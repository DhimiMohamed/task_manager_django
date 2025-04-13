from django.db import models
from tasks.models import Task  # Import your Task model

class Reminder(models.Model):
    METHOD_CHOICES = [
        ('email', 'Email'),
        ('in_app', 'In-App'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    reminder_time = models.DateTimeField()
    method = models.CharField(max_length=50, choices=METHOD_CHOICES, default='email')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reminder for {self.task.title}"