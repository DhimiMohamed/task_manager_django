from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import UserSettings

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def handle_user_settings(sender, instance, created, **kwargs):
    if created:  # New user → create settings
        UserSettings.objects.create(user=instance)
    elif hasattr(instance, 'settings'):  # Existing user → save settings
        instance.settings.save()