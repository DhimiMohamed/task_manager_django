from django.urls import path
from .views import (
    BulkTaskUpdateView, TaskListCreateView, TaskDetailView,
    CategoryListCreateView, CategoryDetailView,
    ExtractTaskDetailsView, TaskListBetweenDatesView,
    TaskStatisticsView, AITaskAssistantView, VoiceToTextView,
    RecurringTaskListCreateView, RecurringTaskDetailView,
    GenerateRecurringTasksView, CommentListCreateView,
    CommentDetailView, FileAttachmentListCreateView,
    FileAttachmentDownloadView, FileAttachmentDetailView, ChatAgent, ChatTextAgent
)

urlpatterns = [
    # Task endpoints
    path('', TaskListCreateView.as_view(), name='task-list-create'),
    path('<int:pk>/', TaskDetailView.as_view(), name='task-detail'),
    path('between-dates/', TaskListBetweenDatesView.as_view(), name='task-list-between-dates'),
    path('stats/', TaskStatisticsView.as_view(), name='task-stats'),

    path('bulk_update/', BulkTaskUpdateView.as_view(), name='task-bulk-update'),
    
    # Category endpoints
    path('categories/', CategoryListCreateView.as_view(), name='category-list-create'),
    path('categories/<int:pk>/', CategoryDetailView.as_view(), name='category-detail'),
    
    # Recurring Task endpoints
    path('recurring/', RecurringTaskListCreateView.as_view(), name='recurring-task-list-create'),
    path('recurring/<int:pk>/', RecurringTaskDetailView.as_view(), name='recurring-task-detail'),
    path('recurring/generate/', GenerateRecurringTasksView.as_view(), name='generate-recurring-tasks'),
    
    # Comment endpoints (nested under tasks)
    path('<int:task_id>/comments/', CommentListCreateView.as_view(), name='comment-list-create'),
    path('comments/<int:pk>/', CommentDetailView.as_view(), name='comment-detail'),
    
    # File Attachment endpoints (nested under tasks)
    path('<int:task_id>/attachments/', FileAttachmentListCreateView.as_view(), name='fileattachment-list-create'),
    path('attachments/<int:pk>/', FileAttachmentDetailView.as_view(), name='fileattachment-detail'),
    path('attachments/<int:pk>/download/', FileAttachmentDownloadView.as_view(), name='fileattachment-download'),
    
    # AI endpoints
    path('extract-task-details/', ExtractTaskDetailsView.as_view(), name='extract-task-details'),
    path('ai/task-assistant/', AITaskAssistantView.as_view(), name='ai_task_assistant'),
    path('ai/voice-to-text/', VoiceToTextView.as_view(), name='voice_to_text'),

    # n8n
    path('chat-agent/', ChatAgent.as_view(), name='audio-forward'),
    path('text-agent/', ChatTextAgent.as_view(), name='text-forward'),  # new text URL

]