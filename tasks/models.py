from django.db import models
from django.conf import settings  # Import settings to reference the custom user model

class Category(models.Model):
    """Model to store task categories with user-defined colors"""
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#CCCCCC")  # Hex color (default black)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # Each user has their own categories

    def __str__(self):
        return f"{self.name} ({self.color})"


class Task(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # Reference to the CustomUser model
        on_delete=models.CASCADE
    )
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)  # Linking to category
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    due_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.IntegerField(default=1)  # 1 = Low, Higher = More Priority
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
