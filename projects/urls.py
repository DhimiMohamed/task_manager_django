from django.urls import path
from .views import ProjectListCreateView, ProjectDetailView, TeamProjectsListView, TeamMemberSkillsView, ProjectProposalView

urlpatterns = [
    path('', ProjectListCreateView.as_view(), name='project-list-create'),  # Handles list and create requests
    path('<int:pk>/', ProjectDetailView.as_view(), name='project-detail'),  # Handles retrieve, update, and delete
    # Team-specific projects
    path('teams/<int:team_id>/projects/', TeamProjectsListView.as_view(), name='team-projects-list'),
    
    # Existing endpoint - now with optional AI proposal generation
    path('team-member-skills/', TeamMemberSkillsView.as_view(), name='team-member-skills'),
    # Dedicated endpoint for generating project proposals
    path('generate-proposal/', ProjectProposalView.as_view(), name='generate-project-proposal'),
]