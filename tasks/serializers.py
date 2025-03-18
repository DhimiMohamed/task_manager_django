from rest_framework import serializers
from .models import Task, Category

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'
        read_only_fields = ['user']  # The user will be assigned automatically

class TaskSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), allow_null=True)
    class Meta:
        model = Task
        fields = ['id', 'title', 'description', 'due_date', 'status', 'priority', 'user', 'category']
        read_only_fields = ['user']