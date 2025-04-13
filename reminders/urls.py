from django.urls import path
from .views import ReminderListCreateView, ReminderDetailView

urlpatterns = [
    path('reminders/', ReminderListCreateView.as_view(), name='reminder-list'),
    path('reminders/<int:pk>/', ReminderDetailView.as_view(), name='reminder-detail'),
]