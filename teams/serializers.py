# task_manager/teams/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from .models import Team, TeamMembership, TeamInvitation

User = get_user_model()

class TeamInvitationSerializer(serializers.ModelSerializer):
    invited_by_email = serializers.CharField(source='invited_by.email', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    email = serializers.EmailField(required=False)  # <-- Add this line

    class Meta:
        model = TeamInvitation
        fields = [
            'id', 'team', 'email', 'invited_by', 'invited_by_email', 
            'user', 'user_email', 'team_name', 'status', 'token', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['team', 'invited_by', 'token', 'created_at', 'updated_at']

    # Validation moved to the view. No validation here.

    def create(self, validated_data):
        # Generate unique token
        validated_data['token'] = get_random_string(64)
        
        # Set invited_by from context
        validated_data['invited_by'] = self.context['request'].user
        
        # If email is provided but no user, try to find existing user
        if validated_data.get('email') and not validated_data.get('user'):
            try:
                user = User.objects.get(email=validated_data['email'])
                validated_data['user'] = user
            except User.DoesNotExist:
                pass  # User doesn't exist yet, invitation will be for email only
        
        return super().create(validated_data)

class TeamMembershipSerializer(serializers.ModelSerializer):
    # Write-only field for adding members by email
    email = serializers.EmailField(write_only=True, required=False)
    
    # Read-only user information fields
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)
    
    # Profile fields
    skills = serializers.SerializerMethodField()
    experience = serializers.SerializerMethodField()
    
    class Meta:
        model = TeamMembership
        fields = [
            'id', 'user_id', 'username', 'email', 'user_email', 
            'team', 'team_name', 'role', 'joined_at',
            'skills', 'experience'  # Add the new fields
        ]
        read_only_fields = ['joined_at', 'team', 'user_id', 'username', 'user_email']

    def get_skills(self, obj):
        # Get skills from the user's profile if it exists
        if hasattr(obj.user, 'profile'):
            return obj.user.profile.skills
        return None

    def get_experience(self, obj):
        # Get experience from the user's profile if it exists
        if hasattr(obj.user, 'profile'):
            return obj.user.profile.experience
        return None

    def validate(self, data):
        # Only require email/user validation for CREATE operations
        if self.instance is None:  # Creating new instance
            if 'email' not in data and 'user' not in data:
                raise serializers.ValidationError("Either email or user must be provided")
        return data

    def create(self, validated_data):
        email = validated_data.pop('email', None)
        
        if email:
            try:
                user = User.objects.get(email=email)
                validated_data['user'] = user
            except User.DoesNotExist:
                raise serializers.ValidationError({"email": "User with this email does not exist"})
        
        # Ensure the team is set from the URL parameter
        team_id = self.context['view'].kwargs.get('team_id')
        validated_data['team'] = Team.objects.get(pk=team_id)
        
        return super().create(validated_data)

class TeamSerializer(serializers.ModelSerializer):
    members = TeamMembershipSerializer(
        source='teammembership_set', 
        many=True, 
        read_only=True
    )
    invitations = TeamInvitationSerializer(
        many=True, 
        read_only=True
    )
    member_count = serializers.IntegerField(read_only=True)
    project_count = serializers.SerializerMethodField(read_only=True)
    pending_invitations_count = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    color = serializers.CharField(required=False)
    owner = serializers.EmailField(required=False, read_only=True)
    
    class Meta:
        model = Team
        fields = [
            'id', 'name', 'color', 'owner', 'members', 'invitations', 'member_count',
            'project_count',
            'pending_invitations_count', 'created_at', 'is_admin', 'created_by'
        ]
        read_only_fields = ['created_at']

    def get_project_count(self, obj):
        # Prefer annotated value, fallback to context if present
        if hasattr(obj, 'project_count'):
            return obj.project_count
        context_count = self.context.get('project_count')
        if context_count is not None:
            return context_count
        # Fallback: count related projects
        return obj.project_set.count()

    def get_pending_invitations_count(self, obj):
        return obj.invitations.filter(status='pending').count()

    def get_is_admin(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.teammembership_set.filter(
                user=request.user, 
                role='admin'
            ).exists()
        return False

    def get_created_by(self, obj):
        # Get the first admin member (creator) - ordered by joined_at
        creator = obj.teammembership_set.filter(role='admin').order_by('joined_at').first()
        return creator.user.username if creator else None

    def create(self, validated_data):
        request = self.context.get('request')
        # Always set owner as the request user's email
        validated_data['owner'] = request.user.email
        team = Team.objects.create(**validated_data)
        # Automatically make creator an admin member
        TeamMembership.objects.create(
            team=team,
            user=request.user,
            role='admin'
        )
        return team