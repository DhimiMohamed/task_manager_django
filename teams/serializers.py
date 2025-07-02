from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Team, TeamMembership

User = get_user_model()

class TeamMembershipSerializer(serializers.ModelSerializer):
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), 
        source='user'
    )
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)

    class Meta:
        model = TeamMembership
        fields = [
            'id', 'user_id', 'username', 'email', 'team', 'team_name',
            'role', 'joined_at'
        ]
        read_only_fields = ['joined_at', 'team']

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