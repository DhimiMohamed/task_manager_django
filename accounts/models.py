# from django.contrib.auth.models import AbstractUser
# from django.db import models
# from django.conf import settings


# class CustomUser(AbstractUser):
#     email = models.EmailField(unique=True)  # Ensure the email is unique
#     username = models.CharField(max_length=150, unique=True, blank=True, null=True)
#     # username = None
#     is_verified = models.BooleanField(default=False)  # Field to track email verification status
#     REQUIRED_FIELDS = ['first_name', 'last_name']  # Required fields during registration
#     USERNAME_FIELD = 'email'

#     def __str__(self):
#         return self.email



# class Profile(models.Model):
#     user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
#     bio = models.TextField(blank=True, null=True)
#     # profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
#     date_of_birth = models.DateField(blank=True, null=True)
#     location = models.CharField(max_length=100, blank=True, null=True)

#     def __str__(self):
#         return self.user.email  # Or any other unique identifier




from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.conf import settings
from django.utils.timezone import now


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)  # Ensure the email is unique
    # username = models.CharField(max_length=150, unique=True, blank=True, null=True)
    username = None
    is_verified = models.BooleanField(default=False)  # Field to track email verification status
    REQUIRED_FIELDS = ['first_name', 'last_name']  # Required fields during registration
    USERNAME_FIELD = 'email'

    objects = CustomUserManager()  # Use the custom manager

    def __str__(self):
        return self.email


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    bio = models.TextField(blank=True, null=True)
    skills = models.CharField(max_length=255, blank=True, null=True, help_text="Comma-separated list of skills")
    experience = models.TextField(blank=True, null=True, help_text="Details about user's experience")
    date_of_birth = models.DateField(blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)

    def __str__(self):
        return self.user.email  # Or any other unique identifier
    
class PasswordResetOTP(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)  # Use settings.AUTH_USER_MODEL
    otp = models.CharField(max_length=6, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_expired(self):
        return now() > self.expires_at
    

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.email}: {self.message[:20]}..."
    

class UserSettings(models.Model):
    LANGUAGES = [
        ('en', 'English'),
        ('fr', 'French'),
        ('es', 'Spanish'),
        # Add more languages as needed
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='settings')
    
    # Notification Preferences
    email_notifications = models.BooleanField(default=True)
    in_app_notifications = models.BooleanField(default=True)
    
    # Display Preferences
    dark_mode = models.BooleanField(default=False)
    language = models.CharField(max_length=10, choices=LANGUAGES, default='en')
    
    
    def __str__(self):
        return f"Settings for {self.user.email}"