from rest_framework import generics, permissions
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from .models import Project
from .serializers import ProjectCreationFromProposalSerializer, ProjectSerializer
from teams.models import Team, TeamMembership
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

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
    
# task_manager/projects/views.py
# ai part 
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from accounts.models import Profile
from ai.services2 import ProjectProposalService

class TeamMemberSkillsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        team_id = request.data.get('team_id')
        member_ids = request.data.get('member_ids', [])
        project_requirements = request.data.get('project_requirements', None)  # Optional project requirements
        generate_proposal = request.data.get('generate_proposal', False)  # Flag to generate AI proposal

        # Validate input
        if not team_id or not member_ids:
            return Response(
                {'error': 'Both team_id and member_ids are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            team = get_object_or_404(Team, id=team_id)
            
            # Verify requesting user has access to this team
            if not TeamMembership.objects.filter(team=team, user=request.user).exists():
                return Response(
                    {'error': 'You are not a member of this team'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Get profiles of selected members who are actually in the team
            profiles = Profile.objects.filter(
                user__id__in=member_ids,
                user__teammembership__team=team
            ).select_related('user')

            member_data = []
            for profile in profiles:
                # Process skills - get all skills as a cleaned list
                skills_list = []
                if profile.skills:
                    skills_list = [skill.strip() for skill in profile.skills.split(',') if skill.strip()]
                
                member_data.append({
                    'user_id': profile.user.id,
                    'email': profile.user.email,
                    'all_skills': skills_list,
                    'full_experience': profile.experience if profile.experience else None
                })

            # Prepare team data
            team_data = {
                'team_id': team.id,
                'team_name': team.name,
                'members': member_data
            }

            response_data = team_data.copy()

            # Generate AI proposal if requested
            if generate_proposal:
                try:
                    proposal_service = ProjectProposalService()
                    
                    # Generate the proposal
                    proposal_result = proposal_service.generate_project_proposal(
                        team_data, 
                        project_requirements
                    )
                    
                    if proposal_result['success']:
                        # Validate the proposal
                        validation_result = proposal_service.validate_proposal(
                            proposal_result['proposal'], 
                            team_data
                        )
                        
                        response_data.update({
                            'ai_proposal': proposal_result['proposal'],
                            'proposal_validation': validation_result,
                            'project_requirements': project_requirements
                        })
                    else:
                        response_data.update({
                            'ai_proposal_error': proposal_result['error'],
                            'project_requirements': project_requirements
                        })
                        
                except Exception as ai_error:
                    response_data.update({
                        'ai_proposal_error': f'AI service error: {str(ai_error)}',
                        'project_requirements': project_requirements
                    })

            return Response(response_data)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProjectProposalView(APIView):
    """
    Dedicated view for generating project proposals
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Generate a project proposal for a team",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['team_id', 'member_ids'],
            properties={
                'team_id': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description='ID of the team'
                ),
                'member_ids': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_INTEGER),
                    description='List of member IDs to include in the proposal'
                ),
                'project_requirements': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Project requirements description',
                    default=''
                )
            }
        ),
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'team_data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'team_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'team_name': openapi.Schema(type=openapi.TYPE_STRING),
                            'members': openapi.Schema(
                                type=openapi.TYPE_ARRAY,
                                items=openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    properties={
                                        'user_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                        'email': openapi.Schema(type=openapi.TYPE_STRING),
                                        'all_skills': openapi.Schema(
                                            type=openapi.TYPE_ARRAY,
                                            items=openapi.Schema(type=openapi.TYPE_STRING)
                                        ),
                                        'full_experience': openapi.Schema(type=openapi.TYPE_STRING)
                                    }
                                )
                            )
                        }
                    ),
                    'project_requirements': openapi.Schema(type=openapi.TYPE_STRING),
                    'proposal': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'project_name': openapi.Schema(type=openapi.TYPE_STRING),
                            'description': openapi.Schema(type=openapi.TYPE_STRING),
                            'estimated_duration': openapi.Schema(type=openapi.TYPE_STRING),
                            'phases': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                            'resource_requirements': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING)),
                            'risk_assessment': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                            'success_metrics': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING))
                        }
                    ),
                    'validation': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'valid': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                            'warnings': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING)),
                            'errors': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING))
                        }
                    )
                }
            )
        }
    )

    def post(self, request, *args, **kwargs):
        team_id = request.data.get('team_id')
        member_ids = request.data.get('member_ids', [])
        project_requirements = request.data.get('project_requirements', '')

        # Validate input
        if not team_id or not member_ids:
            return Response(
                {'error': 'Both team_id and member_ids are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            team = get_object_or_404(Team, id=team_id)
            
            # Verify requesting user has access to this team
            if not TeamMembership.objects.filter(team=team, user=request.user).exists():
                return Response(
                    {'error': 'You are not a member of this team'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Verify all requested members are part of the team
            team_members = TeamMembership.objects.filter(
                team=team,
                user_id__in=member_ids
            ).select_related('user')

            if team_members.count() != len(member_ids):
                return Response(
                    {'error': 'One or more requested members are not part of this team'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get profiles of all verified members
            member_data = []
            for membership in team_members:
                try:
                    profile = Profile.objects.get(user=membership.user)
                    skills_list = []
                    if profile.skills:
                        skills_list = [skill.strip() for skill in profile.skills.split(',') if skill.strip()]
                    
                    member_data.append({
                        'user_id': profile.user.id,
                        'email': profile.user.email,
                        'all_skills': skills_list,
                        'full_experience': profile.experience if profile.experience else None
                    })
                except Profile.DoesNotExist:
                    member_data.append({
                        'user_id': membership.user.id,
                        'email': membership.user.email,
                        'all_skills': [],
                        'full_experience': None
                    })

            # Prepare team data
            team_data = {
                'team_id': team.id,
                'team_name': team.name,
                'members': member_data
            }

            # Generate AI proposal
            proposal_service = ProjectProposalService()
            proposal_result = proposal_service.generate_project_proposal(
                team_data, 
                project_requirements
            )
            
            if proposal_result['success']:
                # Validate the proposal
                validation_result = proposal_service.validate_proposal(
                    proposal_result['proposal'], 
                    team_data
                )
                
                return Response({
                    'success': True,
                    'team_data': team_data,
                    'project_requirements': project_requirements,
                    'proposal': proposal_result['proposal'],
                    'validation': validation_result
                })
            else:
                return Response({
                    'success': False,
                    'error': proposal_result['error'],
                    'team_data': team_data,
                    'project_requirements': project_requirements
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



# class ProjectProposalView(APIView):
#     """
#     Dedicated view for generating project proposals
#     """
#     permission_classes = [permissions.IsAuthenticated]

#     def post(self, request, *args, **kwargs):
#         team_id = request.data.get('team_id')
#         member_ids = request.data.get('member_ids', [])
#         project_requirements = request.data.get('project_requirements', '')

#         # Validate input
#         if not team_id or not member_ids:
#             return Response(
#                 {'error': 'Both team_id and member_ids are required'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         try:
#             team = get_object_or_404(Team, id=team_id)
            
#             # Verify requesting user has access to this team
#             if not TeamMembership.objects.filter(team=team, user=request.user).exists():
#                 return Response(
#                     {'error': 'You are not a member of this team'},
#                     status=status.HTTP_403_FORBIDDEN
#                 )

#             # Verify all requested members are part of the team
#             team_members = TeamMembership.objects.filter(
#                 team=team,
#                 user_id__in=member_ids
#             ).select_related('user')

#             if team_members.count() != len(member_ids):
#                 return Response(
#                     {'error': 'One or more requested members are not part of this team'},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )

#             # Get profiles of all verified members
#             member_data = []
#             for membership in team_members:
#                 try:
#                     profile = Profile.objects.get(user=membership.user)
#                     skills_list = []
#                     if profile.skills:
#                         skills_list = [skill.strip() for skill in profile.skills.split(',') if skill.strip()]
                    
#                     member_data.append({
#                         'user_id': profile.user.id,
#                         'email': profile.user.email,
#                         'all_skills': skills_list,
#                         'full_experience': profile.experience if profile.experience else None
#                     })
#                 except Profile.DoesNotExist:
#                     member_data.append({
#                         'user_id': membership.user.id,
#                         'email': membership.user.email,
#                         'all_skills': [],
#                         'full_experience': None
#                     })

#             # Prepare team data
#             team_data = {
#                 'team_id': team.id,
#                 'team_name': team.name,
#                 'members': member_data
#             }

#             # Return the response with team data and project requirements
#             response_data = {
#                 'team': team_data,
#                 'project_requirements': project_requirements,
#                 'message': 'Team member data retrieved successfully'
#             }
#             return Response(response_data, status=status.HTTP_200_OK)

#         except Exception as e:
#             return Response(
#                 {'error': f'An error occurred: {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )


from django.db import transaction
from django.contrib.auth import get_user_model
from tasks.models import Task

User = get_user_model()
class CreateProjectFromProposalView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """
        Create a project and its tasks from an AI-generated proposal.
        
        Expected JSON structure:
        {
            "name": "Project Name",
            "description": "Project description",
            "deadline": "2025-12-31",
            "teamId": 1,
            "phases": [
                {
                    "name": "Phase 1",
                    "description": "Phase description",
                    "tasks": [
                        {
                            "title": "Task title",
                            "description": "Task description",
                            "assignedToId": 2,
                            "priority": "high"
                        }
                    ]
                }
            ]
        }
        """
        serializer = ProjectCreationFromProposalSerializer(
            data=request.data, 
            context={'request': request}
        )
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors,
                'message': 'Validation failed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                # Extract validated data
                validated_data = serializer.validated_data
                team = validated_data['teamId']  # This is now a Team object due to validate_teamId
                
                # Create the project
                project = Project.objects.create(
                    name=validated_data['name'],
                    description=validated_data.get('description', ''),
                    end_date=validated_data['deadline'],
                    team=team,
                    created_by=request.user,
                    last_modified_by=request.user,
                    status='planning'  # Default status for new AI projects
                )
                
                # Create tasks from all phases
                created_tasks = []
                
                for phase_index, phase in enumerate(validated_data['phases']):
                    phase_name = phase['name']
                    
                    for task_index, task_data in enumerate(phase['tasks']):
                        # Map priority from string to integer
                        priority_mapping = {'low': 1, 'medium': 2, 'high': 3}
                        priority_int = priority_mapping.get(task_data['priority'], 2)
                        
                        # Get assigned user
                        assigned_user = None
                        if task_data.get('assignedToId'):
                            try:
                                assigned_user = User.objects.get(id=task_data['assignedToId'])
                            except User.DoesNotExist:
                                # Log this but continue - task will be unassigned
                                pass
                        
                        # Create task with phase info in title
                        task_title = f"[{phase_name}] {task_data['title']}"
                        task_description = task_data.get('description', '')
                        
                        # Add phase context to description if it exists
                        if phase.get('description'):
                            task_description = f"Phase: {phase['description']}\n\n{task_description}"
                        
                        task = Task.objects.create(
                            title=task_title,
                            description=task_description,
                            project=project,
                            assigned_to=assigned_user,
                            priority=priority_int,
                            user=request.user,  # Required field for Task model
                            created_by=request.user,
                            last_modified_by=request.user,
                            is_personal=False,  # Project tasks are not personal
                            status='pending'
                        )
                        
                        created_tasks.append({
                            'id': task.id,
                            'title': task.title,
                            'phase': phase_name,
                            'assigned_to': assigned_user.email if assigned_user else 'Unassigned',
                            'priority': task_data['priority']
                        })
                
                # Prepare response data
                response_data = {
                    'success': True,
                    'message': f'Project "{project.name}" created successfully with {len(created_tasks)} tasks',
                    'project': {
                        'id': project.id,
                        'name': project.name,
                        'description': project.description,
                        'team_id': project.team.id,
                        'team_name': project.team.name,
                        'status': project.status,
                        'end_date': project.end_date.isoformat() if project.end_date else None,
                        'created_at': project.created_at.isoformat(),
                        'created_by': project.created_by.email
                    },
                    'tasks_created': len(created_tasks),
                    'tasks': created_tasks,
                    'phases_processed': len(validated_data['phases'])
                }
                
                return Response(response_data, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error creating project: {str(e)}',
                'error_type': type(e).__name__
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)