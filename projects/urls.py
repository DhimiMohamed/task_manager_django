from django.urls import path
from .views import ProjectListCreateView, ProjectDetailView, TeamProjectsListView

urlpatterns = [
    path('', ProjectListCreateView.as_view(), name='project-list-create'),  # Handles list and create requests
    path('<int:pk>/', ProjectDetailView.as_view(), name='project-detail'),  # Handles retrieve, update, and delete
    # Team-specific projects
    path('teams/<int:team_id>/projects/', TeamProjectsListView.as_view(), name='team-projects-list'),
]