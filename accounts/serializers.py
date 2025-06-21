from django.contrib.auth import get_user_model, authenticate
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from .models import Profile, UserSettings

User = get_user_model()

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = get_user_model()
        fields = ['email', 'first_name', 'last_name', 'password', 'password2']
        extra_kwargs = {
        'password': {'write_only': True},
        'first_name': {'required': True},
        'last_name': {'required': True},
        }  # Hide password field

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise ValidationError({'password': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')  # Remove password2 from validated data

        # Create the user, set is_verified=False, and save
        user = get_user_model().objects.create_user(
            email=validated_data['email'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            password=validated_data['password']
        )
        user.is_verified = False  # Set user as unverified initially
        user.save()

        # Generate email verification token
        token = default_token_generator.make_token(user)
        verification_link = f'http://localhost:5173/verify-email/?user_id={user.id}&token={token}'

        # Send the verification email
        send_mail(
            'Email Verification',
            f'Please verify your email by clicking the link: {verification_link}',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )

        return user
    
class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(email=email, password=password)

        if not user:
            raise AuthenticationFailed("Invalid email or password.")

        if not user.is_verified:
            raise AuthenticationFailed("Email not verified. Please check your inbox.")

        attrs["user"] = user
        return attrs

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name'] 

class ProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)  # Include the nested UserSerializer

    class Meta:
        model = Profile
        fields = ['user', 'bio', 'location'] 
        read_only_fields = ['user']  # Ensure user is set automatically


class UserSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSettings
        fields = ['email_notifications', 'in_app_notifications', 'dark_mode', 'language']
        extra_kwargs = {
            'user': {'read_only': True}
        }

from .models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'message', 'is_read', 'created_at']
        read_only_fields = ['id', 'message', 'created_at']