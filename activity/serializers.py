# task_manager/activity/serializers.py
from rest_framework import serializers
from .models import ActivityLog

class ActivityLogSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    content_type = serializers.StringRelatedField(read_only=True)
    content_object = serializers.SerializerMethodField()
    project = serializers.StringRelatedField(read_only=True)  # Add project field

    class Meta:
        model = ActivityLog
        fields = [
            'id',
            'user',
            'action',
            'timestamp',
            'content_type',
            'object_id',
            'content_object',
            'project',  # Include project in fields
            'from_state',
            'to_state',
            'comment_text',
            'attachment_info',
        ]
        read_only_fields = fields

    def get_content_object(self, obj):
        # Return a string representation of the related object, or None if deleted
        return str(obj.safe_content_object) if obj.safe_content_object else None