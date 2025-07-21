from rest_framework import serializers
from .models import Project
from teams.models import TeamMembership

class ProjectSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='team.name', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    is_team_admin = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'team', 'team_name', 'name', 'description', 'status',
            'start_date', 'end_date', 'created_by', 'created_by_email',
            'created_at', 'is_team_admin'
        ]
        read_only_fields = ['created_by', 'created_at']
    
    def get_is_team_admin(self, obj):
        """Check if the requesting user is an admin of the project's team"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return TeamMembership.objects.filter(
                team=obj.team,
                user=request.user,
                role='admin'
            ).exists()
        return False
    
    def validate_team(self, value):
        """Validate that the user is a member of the team"""
        request = self.context.get('request')
        if request and not value.members.filter(id=request.user.id).exists():
            raise serializers.ValidationError("You are not a member of this team")
        return value
    
    def validate(self, data):
        """Validate date consistency"""
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError(
                {"end_date": "End date must be after start date"}
            )
        
        return data
    
    def create(self, validated_data):
        """Automatically set the created_by user"""
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)