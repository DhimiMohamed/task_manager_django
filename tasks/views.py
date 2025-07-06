# task_manager\tasks\views.py
from rest_framework import generics, permissions, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils.timezone import localdate
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.http import FileResponse
from django.db import models
from django.db.models import Q, Count
from datetime import timedelta,datetime
from django.utils.timezone import make_aware
from django_filters.rest_framework import DjangoFilterBackend

from projects.models import Project
from .models import FileAttachment, RecurringTask, Task, Category, Comment
from .serializers import CommentSerializer, FileAttachmentSerializer, RecurringTaskSerializer, TaskSerializer, CategorySerializer
from .services import TaskAIService
from rest_framework.exceptions import ValidationError
from django.utils.timezone import now
from rest_framework.permissions import IsAuthenticated
from collections import defaultdict
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

class CategoryListCreateView(generics.ListCreateAPIView):
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Get personal categories and project categories where user is a member
        return Category.objects.filter(
            models.Q(user=self.request.user, is_personal=True) | 
            models.Q(project__team__members=self.request.user, is_personal=False)
        ).distinct()

    def perform_create(self, serializer):
        project_id = self.request.data.get('project')
        
        if project_id:
            project = Project.objects.get(id=project_id)
            if not project.team.members.filter(id=self.request.user.id).exists():
                raise PermissionDenied("You don't have permission to create project categories")
            
            serializer.save(
                user=self.request.user,
                project=project,
                is_personal=False
            )
        else:
            # Personal category
            serializer.save(
                user=self.request.user,
                is_personal=True,
                project=None
            )

class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Allows users to update or delete their categories."""
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)

class TaskListCreateView(generics.ListCreateAPIView):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['category', 'status', 'priority', 'project', 'assigned_to']
    ordering_fields = ['due_date', 'priority']

    def get_queryset(self):
        user = self.request.user
        # Get tasks where user is owner, assigned to, or part of the project team
        queryset = Task.objects.filter(
            models.Q(user=user) |
            models.Q(assigned_to=user) |
            models.Q(project__team__members=user)
        ).distinct()

        # Add project filtering if specified
        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(project_id=project_id)

        # Get query parameters for date filtering
        date_filter = self.request.query_params.get('date', None)
        week_filter = self.request.query_params.get('week', None)
        month_filter = self.request.query_params.get('month', None)
        year_filter = self.request.query_params.get('year', None)

        if date_filter:
            queryset = queryset.filter(due_date=date_filter)  # Filter tasks for a specific date

        if week_filter and year_filter:
            start_of_week = localdate().replace(year=int(year_filter), month=1, day=1) + timedelta(weeks=int(week_filter) - 1)
            end_of_week = start_of_week + timedelta(days=6)
            queryset = queryset.filter(due_date__range=[start_of_week, end_of_week])

        if month_filter and year_filter:
            queryset = queryset.filter(due_date__year=int(year_filter), due_date__month=int(month_filter))

        return queryset

    def perform_create(self, serializer):
        # Handle assignment, project permissions, etc.
        assigned_to_id = self.request.data.get('assigned_to')
        project_id = self.request.data.get('project')
        
        if project_id:
            project = Project.objects.get(id=project_id)
            if not project.team.members.filter(id=self.request.user.id).exists():
                raise PermissionDenied("You don't have permission to create tasks in this project")
        
        if assigned_to_id and assigned_to_id != self.request.user.id:
            # Verify assignee is in the same team if project task
            if project_id and not project.team.members.filter(id=assigned_to_id).exists():
                raise PermissionDenied("You can only assign to team members")
        
        serializer.save(
            user=self.request.user,
            created_by=self.request.user,
            is_personal=not bool(project_id)
        )

class TaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Task.objects.filter(
            models.Q(user=user) |
            models.Q(assigned_to=user) |
            models.Q(project__team__members=user)
        ).distinct()

class TaskListBetweenDatesView(generics.ListAPIView):
    """
    Lists tasks due between two specified dates.
    """
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        start_date_str = self.request.query_params.get('start_date')
        end_date_str = self.request.query_params.get('end_date')

        if not start_date_str or not end_date_str:
            raise ValidationError("Both start_date and end_date are required.")

        try:
            # Parse date strings to date objects
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        except ValueError:
            raise ValidationError("Invalid date format. Please use YYYY-MM-DD.")

        if start_date > end_date:
            raise ValidationError("start_date must be before end_date.")

        # Filter the tasks by date range
        queryset = Task.objects.filter(models.Q(user=user) |
            models.Q(assigned_to=user) |
            models.Q(project__team__members=user),
            due_date__range=[start_date, end_date]
        ).distinct()
        return queryset
# ----------------------------------------------------

class RecurringTaskListCreateView(generics.ListCreateAPIView):
    serializer_class = RecurringTaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return RecurringTask.objects.filter(
            models.Q(created_by=user) |
            models.Q(assigned_to=user) |
            models.Q(project__team__members=user)
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class RecurringTaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RecurringTaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return RecurringTask.objects.filter(
            models.Q(created_by=user) |
            models.Q(assigned_to=user) |
            models.Q(project__team__members=user)
        ).distinct()

class GenerateRecurringTasksView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        # Logic to generate task instances from recurring tasks
        pass


class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        task_id = self.kwargs.get('task_id')
        return Comment.objects.filter(task_id=task_id)

    def perform_create(self, serializer):
        task = get_object_or_404(Task, pk=self.kwargs.get('task_id'))
        # Verify user has permission to comment on this task
        if not (task.user == self.request.user or 
                task.assigned_to == self.request.user or
                (task.project and task.project.team.members.filter(id=self.request.user.id).exists())):
            raise PermissionDenied("You don't have permission to comment on this task")
        serializer.save(author=self.request.user, task=task)

class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Comment.objects.filter(author=self.request.user)


from rest_framework.parsers import MultiPartParser, FormParser

class FileAttachmentListCreateView(generics.ListCreateAPIView):
    serializer_class = FileAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # Add this line

    def get_queryset(self):
        task_id = self.kwargs.get('task_id')
        return FileAttachment.objects.filter(task_id=task_id)

    def perform_create(self, serializer):
        task = get_object_or_404(Task, pk=self.kwargs.get('task_id'))
        if not (task.user == self.request.user or 
                task.assigned_to == self.request.user or
                (task.project and task.project.team.members.filter(id=self.request.user.id).exists())):
            raise PermissionDenied("You don't have permission to add attachments to this task")
        
        # Auto-set the original filename if not provided
        file = self.request.FILES.get('file')
        if file and not serializer.validated_data.get('original_filename'):
            serializer.validated_data['original_filename'] = file.name
            
        serializer.save(uploaded_by=self.request.user, task=task)

class FileAttachmentDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk, format=None):
        attachment = get_object_or_404(FileAttachment, pk=pk)
        # Check permissions
        if not (attachment.task.user == request.user or 
                attachment.task.assigned_to == request.user or
                (attachment.task.project and attachment.task.project.team.members.filter(id=request.user.id).exists())):
            raise PermissionDenied("You don't have permission to access this file")
        
        response = FileResponse(attachment.file)
        response['Content-Disposition'] = f'attachment; filename="{attachment.original_filename}"'
        return response

class FileAttachmentDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = FileAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return FileAttachment.objects.filter(
            models.Q(task__user=self.request.user) |
            models.Q(task__assigned_to=self.request.user) |
            models.Q(task__project__team__members=self.request.user)
        ).distinct()
# ---------------------------------- AI ----------------------

class ExtractTaskDetailsView(APIView):
    """
    API endpoint to extract task details from a text description using AI,
    process the data (parse dates, handle category), and return it for user verification.
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Extract task details from natural language text using AI",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['description'],
            properties={
                'description': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Natural language description of the task'
                )
            }
        ),
        responses={
            200: openapi.Response(
                description="Successfully extracted task details",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'title': openapi.Schema(type=openapi.TYPE_STRING),
                        'due_date': openapi.Schema(type=openapi.TYPE_STRING, format='date', nullable=True),
                        'start_time': openapi.Schema(type=openapi.TYPE_STRING, format='time', nullable=True),
                        'end_time': openapi.Schema(type=openapi.TYPE_STRING, format='time', nullable=True),
                        'priority': openapi.Schema(type=openapi.TYPE_STRING),
                        'category': openapi.Schema(type=openapi.TYPE_STRING, nullable=True),
                        'category_id': openapi.Schema(type=openapi.TYPE_INTEGER, nullable=True),
                        'status': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            400: openapi.Response(
                description="Bad request",
                examples={
                    "application/json": {
                        "error": "Task description is required."
                    }
                }
            ),
            500: openapi.Response(
                description="AI extraction failed",
                examples={
                    "application/json": {
                        "error": "AI extraction failed."
                    }
                }
            )
        },
        tags=['Tasks']
    )
    def post(self, request):
        task_description = request.data.get("description", "")

        if not task_description:
            return Response({"error": "Task description is required."}, status=status.HTTP_400_BAD_REQUEST)

        extracted_data = TaskAIService.extract_task_details(task_description)

        if extracted_data is None:
            return Response({"error": "AI extraction failed."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        print (extracted_data)  # Debugging line to check the extracted data
        
        # Convert due_date, start_time, and end_time from string to datetime (if they exist)
        due_date = extracted_data.get("due_date")  # Get the date
        start_time = extracted_data.get("start_time") #get start time
        end_time = extracted_data.get("end_time") #get end time
        
        due_date_obj = None # Initialize
        start_time_obj = None # Initialize
        end_time_obj = None # Initialize

        if due_date:
            try:
                due_date_obj = datetime.strptime(due_date, "%Y-%m-%d").date()  # Parse as date
            except ValueError:
                return Response({"error": "Invalid due_date format. Please use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
        
        if start_time:
            try:
                start_time_obj = datetime.strptime(start_time, "%H:%M:%S").time()
            except ValueError:
                return Response({"error": "Invalid start_time format. Please use HH:MM:SS."}, status=status.HTTP_400_BAD_REQUEST)

        if end_time:
            try:
                end_time_obj = datetime.strptime(end_time, "%H:%M:%S").time()
            except ValueError:
                return Response({"error": "Invalid end_time format. Please use HH:MM:SS."}, status=status.HTTP_400_BAD_REQUEST)
        

        # Get or create the category if provided
        category_name = extracted_data.get("category")
        category = None
        if category_name:
            category, _ = Category.objects.get_or_create(name=category_name, user=request.user)


        response_data = {
            "title": extracted_data["title"],
            "due_date": due_date_obj.isoformat() if due_date_obj else None,
            "start_time": start_time_obj.isoformat() if start_time_obj else None,
            "end_time": end_time_obj.isoformat() if end_time_obj else None,
            "priority": extracted_data["priority"],
            "category": category_name,  # Return the name (frontend can use this for display)
            "category_id": category.id if category else None,  # Include ID if needed
            "status": "unverified",  # Helps frontend know this needs confirmation
        }

        return Response(response_data, status=status.HTTP_200_OK)
    
# statistics


from django.db.models import Count, Q
from django.utils.timezone import now
from datetime import timedelta
from collections import defaultdict
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Task, Project, Category

class TaskStatisticsView(APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get task statistics for the authenticated user",
        responses={
            200: openapi.Response(
                description="Task statistics data",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'total_tasks': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'completed_tasks': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'pending_tasks': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'upcoming_tasks': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'daily_tasks': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'labels': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(type=openapi.TYPE_STRING)
                                ),
                                'data': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(type=openapi.TYPE_INTEGER)
                                )
                            }
                        ),
                        'heatmap_data': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_ARRAY,
                                items=openapi.Schema(type=openapi.TYPE_INTEGER)
                            )
                        ),
                        'categories': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'total': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'completed': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'value': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'color': openapi.Schema(type=openapi.TYPE_STRING)
                                }
                            )
                        ),
                        'projects': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'total': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'completed': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'completion_rate': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'color': openapi.Schema(type=openapi.TYPE_STRING),
                                    'team_name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'team_members_count': openapi.Schema(type=openapi.TYPE_INTEGER)
                                }
                            )
                        ),
                        'completion_rate': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'pending_rate': openapi.Schema(type=openapi.TYPE_INTEGER)
                    }
                )
            ),
            401: "Unauthorized"
        },
        security=[{"Bearer": []}]
    )

    def get(self, request):
        user = request.user
        today = now().date()
        
        # Get last 7 days for the overview chart
        last_week_dates = [today - timedelta(days=i) for i in range(6, -1, -1)]
        
        # Get all tasks for the user
        tasks = Task.objects.filter(user=user)

        # Basic counts for the cards
        total = tasks.count()
        completed = tasks.filter(status='completed').count()
        pending = tasks.filter(status='pending').count()
        upcoming = tasks.filter(due_date__gte=today, due_date__lt=today + timedelta(days=1)).count()

        # Weekly task data for the bar chart (last 7 days)
        daily_tasks = defaultdict(int)
        
        for date in last_week_dates:
            daily_tasks[date.strftime("%a")] = tasks.filter(
                due_date=date
            ).count()

        # Productivity heatmap data (tasks by scheduled hour and day of week)
        heatmap_data = [[0] * 24 for _ in range(7)]  # 7 days x 24 hours
        
        for task in tasks.exclude(due_date__isnull=True).exclude(start_time__isnull=True):
            day_of_week = task.due_date.weekday()  # Monday=0, Sunday=6
            hour_of_day = task.start_time.hour if task.start_time else 12  # Default to noon if no time specified
            heatmap_data[day_of_week][hour_of_day] += 1

        # Category breakdown for pie chart
        category_stats = []
        category_tasks = tasks.values('category__name').annotate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='completed'))
        )
        
        for item in category_tasks:
            name = item['category__name'] or "Uncategorized"
            category_stats.append({
                "name": name,
                "total": item['total'],
                "completed": item['completed'],
                "value": item['total'],  # For the pie chart
                "color": Category.objects.filter(name=name, user=user).first().color if name != "Uncategorized" else "#CCCCCC"
            })

        # Project breakdown - NEW IMPROVED VERSION
        project_stats = []
        
        # Get all projects the user is associated with (either through team membership or ownership)
        user_projects = Project.objects.filter(
            Q(team__members=user) | Q(created_by=user)
        ).distinct().prefetch_related('team__members')
        
        for project in user_projects:
            project_tasks = tasks.filter(project=project)
            total_tasks = project_tasks.count()
            completed_tasks = project_tasks.filter(status='completed').count()
            
            project_stats.append({
                "name": project.name,
                "total": total_tasks,
                "completed": completed_tasks,
                "completion_rate": round((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0,
                "color": "#4CAF50",  # You might want to store this on the Project model
                "team_name": project.team.name if project.team else "Personal",
                "team_members_count": project.team.members.count() if project.team else 1
            })

        return Response({
            # Card data
            "total_tasks": total,
            "completed_tasks": completed,
            "pending_tasks": pending,
            "upcoming_tasks": upcoming,
            
            # Task overview chart data (last 7 days)
            "daily_tasks": {
                "labels": list(daily_tasks.keys()),
                "data": list(daily_tasks.values())
            },
            
            # Productivity heatmap data (based on scheduled time)
            "heatmap_data": heatmap_data,
            
            # Category breakdown
            "categories": category_stats,
            
            # Project breakdown (now with team info)
            "projects": project_stats,
            
            # Additional info that might be useful
            "completion_rate": round((completed / total) * 100) if total > 0 else 0,
            "pending_rate": round((pending / total) * 100) if total > 0 else 0
        })






from ai.services1 import get_ai_response

class AITaskAssistantView(APIView):
    """
    Handle AI task assistant requests with DRF.
    Supports: POST /ai/task-assistant/
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_id="ai_task_assistant",
        operation_description="""
        Process user prompts with AI assistant that can perform task-related actions.
        The AI can create tasks, update task statuses, search tasks, and answer questions.
        Requires authentication.
        """,
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['prompt'],
            properties={
                'prompt': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="User's natural language prompt/request",
                    example="Create a task called 'Finish project' due tomorrow"
                ),
                # Add other possible parameters if your frontend might send them
            }
        ),
        responses={
            200: openapi.Response(
                description="Successful AI response",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'response': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            description="AI response containing message and any actions taken",
                            properties={
                                'user_message': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description="AI's response to the user"
                                ),
                                'details': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(type=openapi.TYPE_STRING),
                                    description="List of actions performed"
                                ),
                                'tool_results': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    description="Detailed results of any tools executed",
                                    items=openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'tool': openapi.Schema(type=openapi.TYPE_STRING),
                                            'args': openapi.Schema(type=openapi.TYPE_OBJECT),
                                            'result': openapi.Schema(type=openapi.TYPE_OBJECT),
                                            'error': openapi.Schema(type=openapi.TYPE_STRING)
                                        }
                                    )
                                )
                            }
                        )
                    }
                ),
                examples={
                    "application/json": {
                        "response": {
                            "user_message": "I've created a task 'Finish project' due tomorrow",
                            "details": ["Created task 'Finish project'"],
                            "tool_results": [
                                {
                                    "tool": "create_task",
                                    "args": {"title": "Finish project", "due_date": "2023-12-01"},
                                    "result": {"id": 123, "title": "Finish project"}
                                }
                            ]
                        }
                    }
                }
            ),
            400: openapi.Response(
                description="Bad Request",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Error message"
                        )
                    }
                ),
                examples={
                    "application/json": {
                        "error": "Prompt is required"
                    }
                }
            ),
            401: openapi.Response(
                description="Unauthorized",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example="Authentication credentials were not provided."
                        )
                    }
                )
            ),
            500: openapi.Response(
                description="Internal Server Error",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description="Error details"
                        )
                    }
                )
            )
        },
        security=[{"Bearer": []}],
        tags=['AI Assistant']
    )
    def post(self, request, format=None):
        prompt = request.data.get('prompt')
    
        if not prompt:
            return Response(
                {"error": "Prompt is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            response = get_ai_response(request.user, prompt)
            return Response({"response": response})
        
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
from rest_framework.parsers import MultiPartParser  # Changed from FileUploadParser
import time
import os
from ai.voice_service import VoiceRecognitionService
from ai.exceptions import VoiceProcessingError

class VoiceToTextView(APIView):
    """
    Handle voice input requests with DRF, convert to text, and process with AI assistant.
    Supports: POST /ai/voice-to-text/
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    @swagger_auto_schema(
        operation_id="voice_to_text",
        operation_description="""
        Convert speech in audio files to text and process with AI assistant.
        The AI can create tasks, update task statuses, search tasks, and answer questions.
        Supports MP3, WEBM, and WAV formats.
        Maximum file size: 25MB (default Django setting).
        Requires authentication.
        """,
        manual_parameters=[
            openapi.Parameter(
                name='file',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
                description="Audio file to transcribe (MP3, WEBM, or WAV)"
            )
        ],
        responses={
            200: openapi.Response(
                description="Successful AI response",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'response': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            description="AI response containing message and any actions taken",
                            properties={
                                'user_message': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description="AI's response to the user"
                                ),
                                'details': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(type=openapi.TYPE_STRING),
                                    description="List of actions performed"
                                ),
                                'tool_results': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    description="Detailed results of any tools executed",
                                    items=openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'tool': openapi.Schema(type=openapi.TYPE_STRING),
                                            'args': openapi.Schema(type=openapi.TYPE_OBJECT),
                                            'result': openapi.Schema(type=openapi.TYPE_OBJECT),
                                            'error': openapi.Schema(type=openapi.TYPE_STRING)
                                        }
                                    )
                                )
                            }
                        )
                    }
                ),
            ),
            
        },
        consumes=['multipart/form-data'],
        produces=['application/json'],
        security=[{"Bearer": []}],
        tags=['AI Assistant']
    )
    def post(self, request, format=None):
        # Check if file was uploaded
        if 'file' not in request.FILES:
            return Response(
                {"error": "No audio file provided. Please upload an MP3, WEBM, or WAV file."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        audio_file = request.FILES['file']
        
        # Validate file type
        if not audio_file.name.lower().endswith(('.mp3', '.webm', '.wav')):
            return Response(
                {"error": "Unsupported file format. Please upload MP3, WEBM, or WAV."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # First transcribe the audio to text
            service = VoiceRecognitionService()
            filename = f"audio_{int(time.time())}{os.path.splitext(audio_file.name)[1]}"
            transcription_result = service.transcribe_audio_file(audio_file, filename)
            
            # Then process the transcribed text with the AI assistant
            prompt = transcription_result.get('text', '')
            if not prompt:
                return Response(
                    {"error": "No speech detected in the audio file"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            response = get_ai_response(request.user, prompt)
            return Response({"response": response})
            
        except VoiceProcessingError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )