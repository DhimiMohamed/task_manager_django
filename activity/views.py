# task_manager/activity/views.py
from rest_framework import generics, permissions
from .models import ActivityLog
from .serializers import ActivityLogSerializer

from django.db.models import Q
from projects.models import Project
from tasks.models import Task
from teams.models import Team, TeamMembership

class ActivityLogListView(generics.ListAPIView):
    serializer_class = ActivityLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        
        # Get all projects the user has access to
        accessible_projects = Project.objects.filter(
            Q(team__members=user) | Q(created_by=user)
        )
        
        # Filter activities by accessible projects or user's direct activities
        queryset = ActivityLog.objects.filter(
            Q(project__in=accessible_projects) | Q(user=user)
        ).order_by('-timestamp').distinct()

        # Optional filtering by query params
        content_type = self.request.query_params.get('content_type')
        object_id = self.request.query_params.get('object_id')
        if content_type:
            queryset = queryset.filter(content_type__model=content_type)
        if object_id:
            queryset = queryset.filter(object_id=object_id)
        return queryset

class ProjectActivityLogListView(generics.ListAPIView):
    serializer_class = ActivityLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        user = self.request.user
        
        # Verify the user has access to this project
        project = Project.objects.filter(
            Q(team__members=user) | Q(created_by=user),
            id=project_id
        ).first()
        
        if not project:
            return ActivityLog.objects.none()
        
        # Simply filter by project - much cleaner!
        queryset = ActivityLog.objects.filter(
            project=project
        ).order_by('-timestamp')
        
        # Optional filtering by query params
        content_type = self.request.query_params.get('content_type')
        object_id = self.request.query_params.get('object_id')
        if content_type:
            queryset = queryset.filter(content_type__model=content_type)
        if object_id:
            queryset = queryset.filter(object_id=object_id)
            
        return queryset

class TeamMemberActivityLogListView(generics.ListAPIView):
    """Get activity logs for a specific team member within a project"""
    serializer_class = ActivityLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        member_id = self.kwargs.get('member_id')
        user = self.request.user
        
        # Verify the user has access to this project
        project = Project.objects.filter(
            Q(team__members=user) | Q(created_by=user),
            id=project_id
        ).first()
        
        if not project:
            return ActivityLog.objects.none()
        
        # Filter by project and specific member
        queryset = ActivityLog.objects.filter(
            project=project,
            user_id=member_id
        ).order_by('-timestamp')
        
        return queryset