from rest_framework import serializers
from .models import Reminder

class ReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reminder
        fields = ['id', 'task', 'reminder_time', 'email_status', 'in_app_status', 'created_at']