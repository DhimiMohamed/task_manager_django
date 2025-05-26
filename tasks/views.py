from rest_framework import generics, permissions, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils.timezone import localdate
from django.db.models import Q
from datetime import timedelta,datetime
from django.utils.timezone import make_aware
from django_filters.rest_framework import DjangoFilterBackend
from .models import Task, Category
from .serializers import TaskSerializer, CategorySerializer
from .services import TaskAIService
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.utils.timezone import now
from rest_framework.permissions import IsAuthenticated
from collections import defaultdict
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

class CategoryListCreateView(generics.ListCreateAPIView):
    """Allows users to list and create categories."""
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)  # Show only user's categories

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)  # Assign category to the authenticated user

class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Allows users to update or delete their categories."""
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)

class TaskListCreateView(generics.ListCreateAPIView):
    """Handles listing all tasks and creating new tasks."""
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['category', 'status', 'priority']
    ordering_fields = ['due_date', 'priority']

    def get_queryset(self):
        user = self.request.user
        queryset = Task.objects.filter(user=user)

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
        serializer.save(user=self.request.user)

class TaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Handles retrieving, updating, and deleting a single task."""
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Task.objects.filter(user=self.request.user)  # Ensure users can only access their own tasks

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
        queryset = Task.objects.filter(user=user, due_date__range=[start_date, end_date])
        return queryset

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
class TaskStatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = now().date()
        start_week = today - timedelta(days=today.weekday())  # Monday
        start_month = today.replace(day=1)

        tasks = Task.objects.filter(user=user)

        # Basic counts
        total = tasks.count()
        completed = tasks.filter(status='completed').count()
        pending = tasks.filter(status='pending').count()

        week_tasks = tasks.filter(due_date__gte=start_week)
        month_tasks = tasks.filter(due_date__gte=start_month)

        # Category breakdown
        category_stats = defaultdict(lambda: {'total': 0, 'completed': 0, 'pending': 0})
        for task in tasks:
            category = task.category.name if task.category else "Uncategorized"
            category_stats[category]['total'] += 1
            if task.status == 'completed':
                category_stats[category]['completed'] += 1
            elif task.status == 'pending':
                category_stats[category]['pending'] += 1

        # Calendar heatmap-style grouping (date string -> task count)
        calendar = defaultdict(int)
        for task in tasks:
            if task.due_date:
                date_str = task.due_date.isoformat()
                calendar[date_str] += 1

        return Response({
            "total_tasks": total,
            "completed_tasks": completed,
            "pending_tasks": pending,
            "this_week": {
                "total": week_tasks.count(),
                "completed": week_tasks.filter(status='completed').count()
            },
            "this_month": {
                "total": month_tasks.count(),
                "completed": month_tasks.filter(status='completed').count()
            },
            "categories": category_stats,
            "calendar": calendar
        })
    





# test
from ai.services import get_ai_response
class AIAssistantView(APIView):
    """
    API View for handling AI assistant requests
    """
    
    def post(self, request, format=None):
        # Get prompt from request data
        prompt = request.data.get('prompt', '').strip()
        
        # Validate prompt
        if not prompt:
            return Response(
                {'error': 'Prompt is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get AI response
            ai_response = get_ai_response(prompt)
            return Response(
                {'response': ai_response},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {'error': f'AI service error: {str(e)}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )