# task_manager\teams\serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Team, TeamMembership

User = get_user_model()

class TeamMembershipSerializer(serializers.ModelSerializer):
    # Write-only field for adding members by email
    email = serializers.EmailField(write_only=True, required=False)
    
    # Read-only user information fields
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)  # ✅ RENAMED
    team_name = serializers.CharField(source='team.name', read_only=True)

    class Meta:
        model = TeamMembership
        fields = [
            'id', 'user_id', 'username', 'email', 'user_email', 'team', 'team_name',
            'role', 'joined_at'
        ]
        read_only_fields = ['joined_at', 'team', 'user_id', 'username', 'user_email']

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
    member_count = serializers.IntegerField(read_only=True)
    is_admin = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = [
            'id', 'name', 'members', 'member_count',
            'created_at', 'is_admin', 'created_by'
        ]
        read_only_fields = ['created_at']

    def get_is_admin(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.teammembership_set.filter(
                user=request.user,
                role='admin'
            ).exists()
        return False

    def get_created_by(self, obj):
        # Get the first admin member (creator)
        creator = obj.teammembership_set.filter(role='admin').first()
        return creator.user.username if creator else None

    def create(self, validated_data):
        request = self.context.get('request')
        team = Team.objects.create(**validated_data)
        
        # Automatically make creator an admin member
        TeamMembership.objects.create(
            team=team,
            user=request.user,
            role='admin'
        )
        return team