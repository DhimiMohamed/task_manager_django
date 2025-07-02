from rest_framework import generics, permissions
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from .models import Project
from .serializers import ProjectSerializer
from teams.models import TeamMembership

class ProjectListCreateView(generics.ListCreateAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        return Project.objects.filter(
            Q(team__members=user) | 
            Q(created_by=user)
        ).distinct().order_by('-created_at')
    
    def perform_create(self, serializer):
        team = serializer.validated_data['team']
        # Verify user has permission to create projects for this team
        if not TeamMembership.objects.filter(
            team=team,
            user=self.request.user,
            role__in=['admin', 'member']  # Adjust based on your requirements
        ).exists():
            raise PermissionDenied("You don't have permission to create projects in this team")
        serializer.save()

class ProjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        return Project.objects.filter(
            Q(team__members=user) | 
            Q(created_by=user)
        ).distinct()
    
    def perform_update(self, serializer):
        instance = self.get_object()
        team = serializer.validated_data.get('team', instance.team)
        
        # Verify user has permission to update projects for this team
        if not TeamMembership.objects.filter(
            team=team,
            user=self.request.user,
            role='admin'  # Only admins can modify projects
        ).exists():
            raise PermissionDenied("Only team admins can modify projects")
        
        serializer.save()
    
    def perform_destroy(self, instance):
        # Verify user has permission to delete the project
        if not TeamMembership.objects.filter(
            team=instance.team,
            user=self.request.user,
            role='admin'
        ).exists():
            raise PermissionDenied("Only team admins can delete projects")
        instance.delete()

class TeamProjectsListView(generics.ListAPIView):
    """List all projects for a specific team"""
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        team_id = self.kwargs['team_id']
        user = self.request.user
        
        # Verify user is a member of the team
        if not TeamMembership.objects.filter(
            team_id=team_id,
            user=user
        ).exists():
            raise PermissionDenied("You are not a member of this team")
        
        return Project.objects.filter(team_id=team_id).order_by('-created_at')