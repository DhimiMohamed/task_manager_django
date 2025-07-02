# task_manager\tasks\serializers.py
from rest_framework import serializers
from .models import Task, Category, RecurringTask, Comment, FileAttachment
from projects.models import Project
from django.contrib.auth import get_user_model

User = get_user_model()

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'
        read_only_fields = ['user']


class TaskSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), 
        allow_null=True, 
        required=False
    )
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), 
        allow_null=True, 
        required=False
    )
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), 
        allow_null=True, 
        required=False
    )
    depends_on = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(), 
        many=True, 
        required=False
    )
    recurring_task = serializers.PrimaryKeyRelatedField(
        queryset=RecurringTask.objects.all(), 
        allow_null=True, 
        required=False
    )

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'due_date', 'start_time', 'end_time',
            'status', 'priority', 'user', 'category', 'created_by',
            'is_personal', 'project', 'assigned_to', 'depends_on',
            'is_recurring', 'recurring_task', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'created_by', 'created_at', 'updated_at', 'is_personal']

class RecurringTaskSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), allow_null=True)
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), allow_null=True)
    assigned_to = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), allow_null=True)

    class Meta:
        model = RecurringTask
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'last_triggered_at', 'next_trigger_at', 'occurrences_created']


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = Comment
        fields = ['id', 'task', 'author', 'text', 'created_at', 'updated_at']
        read_only_fields = ['task', 'author', 'created_at', 'updated_at']  # Make task read-only
        extra_kwargs = {
            'text': {'required': True}  # Ensure text is required
        }


class FileAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = FileAttachment
        fields = ['id', 'task', 'uploaded_by', 'file', 'original_filename', 'description', 'uploaded_at']
        read_only_fields = ['uploaded_by', 'original_filename', 'uploaded_at', 'task']
        extra_kwargs = {
            'file': {'required': True}
        }
