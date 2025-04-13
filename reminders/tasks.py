from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Reminder
from accounts.models import Notification
from django.contrib.auth import get_user_model

User = get_user_model()

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_and_send_reminders(self):
    """
    Checks all pending reminders across all users and sends appropriate notifications.
    """
    try:
        now = timezone.now()

        # Get all due, pending reminders
        pending_reminders = Reminder.objects.filter(
            status='pending',
            reminder_time__lte=now
        ).select_related('task', 'task__user')

        for reminder in pending_reminders:
            user = reminder.task.user  # Get the user from related task

            try:
                # Send Email Notification
                if reminder.method == 'email':
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
                    print(f"✅ EMAIL SENT to {user.email}: {reminder.task.title}")

                # Send In-App Notification
                elif reminder.method == 'in_app':
                    Notification.objects.create(
                        user=user,
                        message=f"Reminder: {reminder.task.title} (Due: {reminder.task.due_date})",
                        is_read=False
                    )
                    print(f"✅ IN-APP NOTIFICATION CREATED for {user.email}: {reminder.task.title}")

                # Update reminder status
                reminder.status = 'sent'
                reminder.save()

            except Exception as e:
                reminder.status = 'failed'
                reminder.save()
                print(f"❌ Reminder Failed (ID: {reminder.id}) — {e}")

    except Exception as e:
        print(f"🔥 Task failed — retrying in 2 minutes. Error: {e}")
        self.retry(exc=e, countdown=120)
