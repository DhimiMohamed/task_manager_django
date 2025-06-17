from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db import models
from .models import Reminder
from accounts.models import Notification, UserSettings
from django.contrib.auth import get_user_model

User = get_user_model()

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_and_send_reminders(self):
    """
    Checks pending reminders and sends notifications based on UserSettings
    """
    try:
        now = timezone.now()
        
        # Get reminders with pending notifications that are due
        pending_reminders = Reminder.objects.filter(
            models.Q(email_status='pending') | models.Q(in_app_status='pending'),
            reminder_time__lte=now
        ).select_related('task__user')

        for reminder in pending_reminders:
            user = reminder.task.user
            
            try:
                # Get user settings (or defaults if not exists)
                try:
                    user_settings  = user.settings
                except UserSettings.DoesNotExist:
                    user_settings  = UserSettings.objects.create(user=user)

                # Process email if enabled in settings
                if reminder.email_status == 'pending' and user_settings .email_notifications:
                    try:
                        print("1")
                        send_mail(
                            subject=f"Reminder: {reminder.task.title}",
                            message=(
                                f"Task: {reminder.task.title}\n"
                                f"Description: {reminder.task.description}\n"
                                f"Original Due: {reminder.task.due_date}\n"
                                f"Reminder Time: {reminder.reminder_time}"
                            ),
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[user.email],
                            fail_silently=False,
                        )
                        reminder.email_status = 'sent'
                        print("2")
                    except Exception as e:
                        print(f"Email sending failed: {e}")
                        reminder.email_status = 'failed'

                # Always process in-app notifications (as per your requirement)
                if reminder.in_app_status == 'pending':
                    try:
                        Notification.objects.create(
                            user=user,
                            message=f"Reminder: {reminder.task.title}",
                            is_read=False
                        )
                        reminder.in_app_status = 'sent'
                    except Exception as e:
                        print(f"In-app notification creation failed: {e}")
                        reminder.in_app_status = 'failed'

                reminder.save()

            except Exception as e:
                continue  # Skip this reminder if error occurs

    except Exception as e:
        self.retry(exc=e, countdown=120)