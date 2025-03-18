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
            queryset = queryset.filter(due_date__date=date_filter)  # Filter tasks for a specific date

        if week_filter and year_filter:
            start_of_week = localdate().replace(year=int(year_filter), month=1, day=1) + timedelta(weeks=int(week_filter) - 1)
            end_of_week = start_of_week + timedelta(days=6)
            queryset = queryset.filter(due_date__date__range=[start_of_week, end_of_week])

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



class ExtractTaskDetailsView(APIView):
    """
    API endpoint to extract task details from a text description using AI
    and save it to the database.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        task_description = request.data.get("description", "")

        if not task_description:
            return Response({"error": "Task description is required."}, status=status.HTTP_400_BAD_REQUEST)

        extracted_data = TaskAIService.extract_task_details(task_description)

        if extracted_data is None:
            return Response({"error": "AI extraction failed."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Convert due_date from string to datetime (if it exists)
        due_date = extracted_data.get("due_date")
        due_datetime = None

        if due_date:
            try:
                due_datetime = make_aware(datetime.strptime(due_date, "%Y-%m-%d"))  # Convert to timezone-aware DateTime
            except ValueError:
                return Response({"error": "Invalid date format received."}, status=status.HTTP_400_BAD_REQUEST)

        # Get or create the category if provided
        category_name = extracted_data.get("category")
        category = None
        if category_name:
            category, _ = Category.objects.get_or_create(name=category_name, user=request.user)

        # Create and save the Task
        task = Task.objects.create(
            user=request.user,
            title=extracted_data["title"],
            due_date=due_datetime,  # Now in correct DateTime format
            priority=extracted_data["priority"],
            category=category  # Can be None
        )

        # Serialize the created task and return it
        return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)