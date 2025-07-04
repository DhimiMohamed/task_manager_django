from rest_framework import generics, permissions, status, serializers
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q, Count
from .models import Team, TeamMembership
from .serializers import TeamSerializer, TeamMembershipSerializer
from django.contrib.auth import get_user_model

User = get_user_model()

class TeamListCreateView(generics.ListCreateAPIView):
    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Show teams where user is a member
        return (
        Team.objects.filter(members=self.request.user)
        .annotate(member_count=Count('members'))
        .order_by('name')
    )

    def perform_create(self, serializer):
        serializer.save()

class TeamDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only allow access if user is a member
        return Team.objects.filter(members=self.request.user)

    def perform_update(self, serializer):
        # Only allow update if user is admin
        if not self.request.user.teammembership_set.filter(
            team=self.get_object(),
            role='admin'
        ).exists():
            raise PermissionDenied("Only team admins can update team details")
        serializer.save()

    def perform_destroy(self, instance):
        # Only allow delete if user is admin
        if not self.request.user.teammembership_set.filter(
            team=instance,
            role='admin'
        ).exists():
            raise PermissionDenied("Only team admins can delete teams")
        instance.delete()

class TeamMembershipListView(generics.ListCreateAPIView):
    serializer_class = TeamMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        team_id = self.kwargs['team_id']
        # Only show members if requesting user is a member
        if not TeamMembership.objects.filter(
            team_id=team_id,
            user=self.request.user
        ).exists():
            raise PermissionDenied("You are not a member of this team")
        return TeamMembership.objects.filter(team_id=team_id)

    def perform_create(self, serializer):
        team_id = self.kwargs['team_id']
        team = Team.objects.get(pk=team_id)
        
        # Only allow adding members if user is admin
        if not self.request.user.teammembership_set.filter(
            team=team,
            role='admin'
        ).exists():
            raise PermissionDenied("Only team admins can add members")
        
        # Check if user is already a member (the serializer handles email-to-user conversion)
        user = serializer.validated_data.get('user')
        if user and TeamMembership.objects.filter(team=team, user=user).exists():
            raise serializers.ValidationError("User is already a team member")
        
        # The serializer already handles setting the team and user
        serializer.save()

class TeamMembershipDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TeamMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        team_id = self.kwargs['team_id']
        # Only allow access if requesting user is a member
        if not TeamMembership.objects.filter(
            team_id=team_id,
            user=self.request.user
        ).exists():
            raise PermissionDenied("You are not a member of this team")
        return TeamMembership.objects.filter(team_id=team_id)

    def perform_update(self, serializer):
        # Only allow update if requesting user is admin
        if not self.request.user.teammembership_set.filter(
            team_id=self.kwargs['team_id'],
            role='admin'
        ).exists():
            raise PermissionDenied("Only team admins can modify memberships")
        
        # Prevent demoting the last admin
        instance = self.get_object()
        if 'role' in serializer.validated_data and instance.role == 'admin':
            admin_count = TeamMembership.objects.filter(
                team=instance.team,
                role='admin'
            ).count()
            if admin_count <= 1 and serializer.validated_data['role'] != 'admin':
                raise PermissionDenied("Cannot demote the last admin")
        
        serializer.save()

    def perform_destroy(self, instance):
        # Only allow removal if requesting user is admin
        if not self.request.user.teammembership_set.filter(
            team=instance.team,
            role='admin'
        ).exists():
            raise PermissionDenied("Only team admins can remove members")
        
        # Prevent removing the last admin
        if instance.role == 'admin':
            admin_count = TeamMembership.objects.filter(
                team=instance.team,
                role='admin'
            ).count()
            if admin_count <= 1:
                raise PermissionDenied("Cannot remove the last admin")
        
        instance.delete()