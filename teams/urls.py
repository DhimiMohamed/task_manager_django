from django.urls import path
from .views import TeamListCreateView, TeamDetailView, TeamMembershipDetailView, TeamMembershipListView

urlpatterns = [
    path('', TeamListCreateView.as_view(), name='team-list-create'),  # Handles list and create requests
    path('<int:pk>/', TeamDetailView.as_view(), name='team-detail'),  # Handles retrieve, update, and delete
    path('memberships/<int:pk>/', TeamMembershipDetailView.as_view(), name='team-membership-detail'),
    path('<int:team_id>/members/', TeamMembershipListView.as_view(), name='membership-list'),
    path('<int:team_id>/members/<int:pk>/', TeamMembershipDetailView.as_view(), name='membership-detail'),
]