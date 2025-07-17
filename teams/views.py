# task_manager/teams/views.py
from rest_framework import generics, permissions, status, serializers
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.decorators import api_view, permission_classes
from django.db.models import Q, Count
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from .models import Team, TeamMembership, TeamInvitation
from .serializers import TeamSerializer, TeamMembershipSerializer, TeamInvitationSerializer

User = get_user_model()

class TeamListCreateView(generics.ListCreateAPIView):
    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Show teams where user is a member, and count all members using a Subquery
        from django.db.models import OuterRef, Subquery
        member_count = TeamMembership.objects.filter(team=OuterRef('pk')).values('team').annotate(
            c=Count('id')
        ).values('c')
        return (
            Team.objects.filter(members=self.request.user)
            .annotate(member_count=Subquery(member_count[:1]))
            .prefetch_related('teammembership_set__user', 'invitations')
            .order_by('name')
        )

    def perform_create(self, serializer):
        serializer.save()

class TeamDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # from projects.models import Project
        team_id = self.kwargs['pk']
        return (
            Team.objects.filter(pk=team_id)
            .annotate(
                member_count=Count('teammembership', distinct=True),
                project_count=Count('project', distinct=True)  # 'project' is the related_name for Project.team FK
            )
            .prefetch_related('teammembership_set__user', 'invitations')
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # Add project_count to serializer context for use in serializer if needed
        team = self.get_object()
        context['project_count'] = getattr(team, 'project_count', 0)
        return context


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
        return TeamMembership.objects.filter(team_id=team_id).select_related('user', 'team')

    def perform_create(self, serializer):
        team_id = self.kwargs['team_id']
        team = get_object_or_404(Team, pk=team_id)
        
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
        return TeamMembership.objects.filter(team_id=team_id).select_related('user', 'team')

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

class TeamInvitationListView(generics.ListCreateAPIView):
    serializer_class = TeamInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        team_id = self.kwargs['team_id']
        # Only show invitations if requesting user is a member
        if not TeamMembership.objects.filter(
            team_id=team_id,
            user=self.request.user
        ).exists():
            raise PermissionDenied("You are not a member of this team")
        return TeamInvitation.objects.filter(team_id=team_id).select_related('invited_by', 'user', 'team')

    def perform_create(self, serializer):
        team_id = self.kwargs['team_id']
        team = get_object_or_404(Team, pk=team_id)
        
        # Only allow admins to send invitations
        if not self.request.user.teammembership_set.filter(
            team=team,
            role='admin'
        ).exists():
            raise PermissionDenied("Only team admins can send invitations")
        
        # Extract data
        validated_data = serializer.validated_data
        email = validated_data.get('email')
        user = validated_data.get('user')

        # Check for pending invitations for the email (whether or not user exists)
        if email and TeamInvitation.objects.filter(
            team=team, 
            email=email, 
            status='pending'
        ).exists():
            raise serializers.ValidationError({"email": f"Pending invitation already exists for this email: {email}"})

        # Only check for existing membership if USER was EXPLICITLY provided
        # (not auto-resolved from email)
        if 'user' in serializer.initial_data:  # <-- Key change: Check initial_data, not validated_data
            if TeamMembership.objects.filter(team=team, user=user).exists():
                raise serializers.ValidationError("User is already a team member")

        serializer.save(team=team)

class TeamInvitationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TeamInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        team_id = self.kwargs['team_id']
        # Only allow access if requesting user is a member
        if not TeamMembership.objects.filter(
            team_id=team_id,
            user=self.request.user
        ).exists():
            raise PermissionDenied("You are not a member of this team")
        return TeamInvitation.objects.filter(team_id=team_id).select_related('invited_by', 'user', 'team')

    def perform_update(self, serializer):
        instance = self.get_object()
        is_admin = self.request.user.teammembership_set.filter(
            team=instance.team,
            role='admin'
        ).exists()
        is_invited_user = instance.user == self.request.user

        if not (is_admin or is_invited_user):
            raise PermissionDenied("Only team admins or invited users can modify invitations")

        # Validation: either email or user must be provided (moved from serializer)
        email = serializer.validated_data.get('email') or getattr(instance, 'email', None)
        user = serializer.validated_data.get('user') or getattr(instance, 'user', None)
        if not email and not user:
            raise serializers.ValidationError("Either email or user must be provided")

        # If user is accepting invitation, create membership if not already a member
        if 'status' in serializer.validated_data and serializer.validated_data['status'] == 'accepted':
            if not is_invited_user:
                # ...your logic...
                pass

            # Only create membership if it doesn't exist
            if not TeamMembership.objects.filter(team=instance.team, user=self.request.user).exists():
                TeamMembership.objects.create(
                    team=instance.team,
                    user=self.request.user,
                    role='member'
                )

        serializer.save()

    def perform_destroy(self, instance):
        # Only allow deletion if requesting user is admin or the invited user
        is_admin = self.request.user.teammembership_set.filter(
            team=instance.team,
            role='admin'
        ).exists()
        is_invited_user = instance.user == self.request.user
        
        if not (is_admin or is_invited_user):
            raise PermissionDenied("Only team admins or invited users can delete invitations")
        
        instance.delete()

# Public view for accepting invitations via email link
@api_view(['GET', 'POST'])
@permission_classes([permissions.AllowAny])
def accept_invitation(request, token):
    """
    Accept team invitation via token (for email links)
    GET: Show invitation details
    POST: Accept invitation (requires authentication)
    """
    try:
        invitation = TeamInvitation.objects.get(token=token, status='pending')
    except TeamInvitation.DoesNotExist:
        raise NotFound("Invalid or expired invitation token")
    
    if request.method == 'GET':
        serializer = TeamInvitationSerializer(invitation)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required to accept invitation"}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Check if user's email matches invitation email
        if request.user.email != invitation.email:
            return Response(
                {"detail": "Email mismatch"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if already a member
        if TeamMembership.objects.filter(
            team=invitation.team, 
            user=request.user
        ).exists():
            return Response(
                {"detail": "Already a team member"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Accept invitation
        invitation.status = 'accepted'
        invitation.user = request.user
        invitation.save()
        
        # Create membership
        TeamMembership.objects.create(
            team=invitation.team,
            user=request.user,
            role='member'
        )
        
        return Response(
            {"detail": "Invitation accepted successfully"}, 
            status=status.HTTP_200_OK
        )