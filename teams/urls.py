# task_manager/teams/urls.py
from django.urls import path
from .views import (
    TeamListCreateView, 
    TeamDetailView, 
    TeamMembershipListView,
    TeamMembershipDetailView,
    TeamInvitationListView,
    TeamInvitationDetailView,
    accept_invitation
)

urlpatterns = [
    # Team URLs
    path('', TeamListCreateView.as_view(), name='team-list-create'),
    path('<int:pk>/', TeamDetailView.as_view(), name='team-detail'),
    
    # Team Membership URLs
    path('<int:team_id>/members/', TeamMembershipListView.as_view(), name='team-membership-list'),
    path('<int:team_id>/members/<int:pk>/', TeamMembershipDetailView.as_view(), name='team-membership-detail'),
    
    # Team Invitation URLs
    path('<int:team_id>/invitations/', TeamInvitationListView.as_view(), name='team-invitation-list'),
    path('<int:team_id>/invitations/<int:pk>/', TeamInvitationDetailView.as_view(), name='team-invitation-detail'),
    
    # Public invitation acceptance (via email link)
    path('invitations/accept/<str:token>/', accept_invitation, name='accept-invitation'),
]