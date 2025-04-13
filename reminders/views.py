from django.shortcuts import render

from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied
from .models import Reminder
from .serializers import ReminderSerializer

class ReminderListCreateView(generics.ListCreateAPIView):
    serializer_class = ReminderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Reminder.objects.filter(task__user=self.request.user)

    def perform_create(self, serializer):
        # This ensures the reminder can only be created for tasks owned by the user
        task = serializer.validated_data['task']
        if task.user != self.request.user:
            raise PermissionDenied("You do not have permission to add a reminder to this task.")
        serializer.save()

class ReminderDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ReminderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only allow reminders linked to the logged-in user's tasks
        return Reminder.objects.filter(task__user=self.request.user)

    def perform_update(self, serializer):
        # Extra safety check to ensure the user owns the task the reminder is for
        task = serializer.validated_data.get('task', serializer.instance.task)
        if task.user != self.request.user:
            raise PermissionDenied("You cannot update a reminder for someone else's task.")
        serializer.save()

    def perform_destroy(self, instance):
        # Ensure only the owner can delete the reminder
        if instance.task.user != self.request.user:
            raise PermissionDenied("You cannot delete a reminder for someone else's task.")
        instance.delete()