from rest_framework import serializers
from .models import Project
from teams.models import Team, TeamMembership

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
    
class TaskCreationSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(allow_blank=True, required=False)
    assignedToId = serializers.IntegerField()
    priority = serializers.ChoiceField(choices=['low', 'medium', 'high'])
    estimatedHours = serializers.IntegerField(required=False)  # Ignored for now
    skillsRequired = serializers.ListField(child=serializers.CharField(), required=False)  # Ignored for now

class PhaseCreationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(allow_blank=True, required=False)
    duration = serializers.CharField(required=False)  # Ignored for now
    tasks = TaskCreationSerializer(many=True)

class ProjectCreationFromProposalSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(allow_blank=True, required=False)
    deadline = serializers.DateField()  # Maps to end_date
    priority = serializers.ChoiceField(choices=['low', 'medium', 'high'], required=False)  # Ignored for now
    estimatedDuration = serializers.CharField(required=False)  # Ignored for now
    teamId = serializers.IntegerField()
    phases = PhaseCreationSerializer(many=True)
    
    # Future fields - will be ignored but validated
    milestones = serializers.ListField(required=False)
    resourceRequirements = serializers.ListField(required=False)  
    riskAssessment = serializers.ListField(required=False)
    successMetrics = serializers.ListField(required=False)

    def validate_teamId(self, value):
        try:
            team = Team.objects.get(id=value)
            # Check if the requesting user is a member of this team
            request = self.context.get('request')
            if request and not team.members.filter(id=request.user.id).exists():
                raise serializers.ValidationError("You are not a member of this team")
            return team
        except Team.DoesNotExist:
            raise serializers.ValidationError("Team does not exist")
    
    def validate_phases(self, phases_data):
        # Validate that all assigned users exist and are team members
        team_id = self.initial_data.get('teamId')
        if not team_id:
            return phases_data
            
        try:
            team = Team.objects.get(id=team_id)
            team_member_ids = set(team.members.values_list('id', flat=True))
            
            for phase in phases_data:
                for task in phase.get('tasks', []):
                    assigned_to_id = task.get('assignedToId')
                    if assigned_to_id and assigned_to_id not in team_member_ids:
                        raise serializers.ValidationError(
                            f"User {assigned_to_id} is not a member of the selected team"
                        )
        except Team.DoesNotExist:
            raise serializers.ValidationError("Team does not exist")
            
        return phases_data
    