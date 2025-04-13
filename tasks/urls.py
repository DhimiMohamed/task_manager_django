from django.urls import path
from .views import TaskListCreateView, TaskDetailView, CategoryListCreateView, CategoryDetailView, ExtractTaskDetailsView, TaskListBetweenDatesView, TaskStatisticsView

urlpatterns = [
    path('', TaskListCreateView.as_view(), name='task-list-create'),  # Handles list and create requests
    path('<int:pk>/', TaskDetailView.as_view(), name='task-detail'),  # Handles retrieve, update, and delete
    path('categories/', CategoryListCreateView.as_view(), name='category-list-create'),
    path('categories/<int:pk>/', CategoryDetailView.as_view(), name='category-detail'),
    path("extract-task-details/", ExtractTaskDetailsView.as_view(), name="extract-task-details"),
    path('between-dates/', TaskListBetweenDatesView.as_view(), name='task-list-between-dates'), # Add this line
    path('stats/', TaskStatisticsView.as_view(), name='task-stats'),
]