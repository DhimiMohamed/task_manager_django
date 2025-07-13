# task_manager\tasks\models.py
from django.db import models
from django.conf import settings
from projects.models import Project
import os
from django.core.validators import MinValueValidator

class Category(models.Model):
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#CCCCCC")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_personal = models.BooleanField(default=True)
    # project = models.ForeignKey(
    #     'projects.Project', 
    #     on_delete=models.CASCADE, 
    #     null=True, 
    #     blank=True
    # )

    # class Meta:
    #     verbose_name_plural = 'categories'
    #     unique_together = [
    #         ('user', 'name', 'project'),  # Unique for personal categories
    #         ('project', 'name')          # Unique within a project
    #     ]

    def __str__(self):
        return f"{self.name} ({'Personal' if self.is_personal else 'Project'})"

def task_attachment_path(instance, filename):
    return os.path.join('attachments', 'tasks', str(instance.task.id), filename)

class Task(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    PRIORITY_CHOICES = [
        (1, 'Low'),
        (2, 'Medium'),
        (3, 'High'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='old_tasks')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    due_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_personal = models.BooleanField(default=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    depends_on = models.ManyToManyField('self', symmetrical=False, blank=True)
    is_recurring = models.BooleanField(default=False)
    recurring_task = models.ForeignKey('RecurringTask', on_delete=models.SET_NULL, null=True, blank=True, related_name='instances')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_tasks', null=True)

    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        editable=False,
        related_name='modified_tasks'
    )

    class Meta:
        ordering = ['-due_date']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.created_by_id:
            self.created_by = self.user
        super().save(*args, **kwargs)

class RecurringTask(models.Model):
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
        ('custom', 'Custom'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='recurring_tasks')
    priority = models.IntegerField(choices=Task.PRIORITY_CHOICES, default=2)
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='weekly')
    interval = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    days_of_week = models.JSONField(default=list, blank=True)
    day_of_month = models.PositiveIntegerField(null=True, blank=True)
    custom_rule = models.CharField(max_length=100, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    max_occurrences = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    next_trigger_at = models.DateTimeField(null=True, blank=True)
    occurrences_created = models.PositiveIntegerField(default=0)
    auto_archive = models.BooleanField(default=False)
    preserve_history = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['next_trigger_at']

    def __str__(self):
        return f"Recurring: {self.title} ({self.get_frequency_display()})"

class Comment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Comment by {self.author.email} on {self.task.title}"

class FileAttachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    file = models.FileField(upload_to=task_attachment_path)
    original_filename = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.original_filename} (attached to {self.task.title})"

    def save(self, *args, **kwargs):
        if not self.original_filename and self.file:
            self.original_filename = os.path.basename(self.file.name)
        super().save(*args, **kwargs)
