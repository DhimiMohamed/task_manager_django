from django.contrib import admin

# Register your models here.
from .models import Task, Category, RecurringTask, Comment, FileAttachment
admin.site.register(Task)
admin.site.register(Category)
admin.site.register(RecurringTask)
admin.site.register(Comment)
admin.site.register(FileAttachment)