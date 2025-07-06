# task_manager/activity/urls.py
from django.urls import path
from .views import ActivityLogListView, ProjectActivityLogListView, TeamMemberActivityLogListView

urlpatterns = [
    # General activity logs for authenticated user
    path('logs/', ActivityLogListView.as_view(), name='activity-log-list'),
    
    # All activity logs for a specific project
    path('projects/<int:project_id>/logs/', ProjectActivityLogListView.as_view(), name='project-activity-logs'),
    
    # Activity logs for a specific team member within a project
    path('projects/<int:project_id>/members/<int:member_id>/logs/', TeamMemberActivityLogListView.as_view(), name='project-member-activity-logs'),
]