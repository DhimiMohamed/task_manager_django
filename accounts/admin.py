from django.contrib import admin

# Register your models here.
from .models import CustomUser, Profile, PasswordResetOTP, Notification, UserSettings
admin.site.register(CustomUser)
admin.site.register(Profile)
admin.site.register(PasswordResetOTP)
admin.site.register(Notification)
admin.site.register(UserSettings)