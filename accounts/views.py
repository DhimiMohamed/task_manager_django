from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import UserRegistrationSerializer, UserLoginSerializer, ProfileSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
# from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from .models import Profile
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi


User = get_user_model()

class UserRegistrationView(APIView):
    @swagger_auto_schema(
        operation_summary="Register a new user",
        operation_description="Registers a new user and creates a profile. Sends verification email.",
        request_body=UserRegistrationSerializer,
        responses={
            201: openapi.Response(description="User registered successfully"),
            400: openapi.Response(description="Validation errors in request body")
        }
    )
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # Auto-returns 400 with errors
        
        user = serializer.save()
        Profile.objects.create(user=user)
        
        return Response(
            {"message": "User registered successfully. Please check your email."},
            status=status.HTTP_201_CREATED
        )



class VerifyEmailView(APIView):
    @swagger_auto_schema(
        operation_summary="Verify user email",
        operation_description="Verifies a user's email using a user ID and token provided via email.",
        manual_parameters=[
            openapi.Parameter(
                'user_id',
                openapi.IN_PATH,
                description="ID of the user to verify",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'token',
                openapi.IN_PATH,
                description="Verification token from email",
                type=openapi.TYPE_STRING
            )
        ],
        responses={
            200: openapi.Response(description="Email successfully verified"),
            400: openapi.Response(description="Invalid user or token")
        }
    )
    def get(self, request, user_id, token):
        User = get_user_model()

        try:
            user = User.objects.get(id=user_id)  # Fetch user by ID
        except User.DoesNotExist:
            return Response({"error": "Invalid user."}, status=status.HTTP_400_BAD_REQUEST)
        # Check if the user is already verified
        if user.is_verified:
            return Response({"message": "Email already verified. You can log in."}, status=status.HTTP_200_OK)

        # Validate the token
        if default_token_generator.check_token(user, token):
            # Mark the user as verified
            user.is_verified = True
            user.save()

            return Response({"message": "Email successfully verified. You can now log in."}, status=status.HTTP_200_OK)

        return Response({"error": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)


class ResendVerificationEmailView(APIView):
    @swagger_auto_schema(
        operation_description="Resend verification email to a user who has not yet verified their email.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING, description='User\'s email address')
            },
            required=['email']
        ),
        responses={
            200: openapi.Response(
                description="Verification email resent successfully",
                examples={
                    'application/json': {
                        'message': 'Verification email resent.'
                    }
                }
            ),
            400: openapi.Response(
                description="Bad request, email missing or user already verified",
                examples={
                    'application/json': {
                        'error': 'Email is required.'
                    },
                    'error': 'User is already verified.'
                }
            ),
            404: openapi.Response(
                description="User with the provided email not found",
                examples={
                    'application/json': {
                        'error': 'No user with this email.'
                    }
                }
            )
        }
    )
    def post(self, request):
        email = request.data.get('email')

        if not email:
            return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = get_user_model().objects.get(email=email)
        except get_user_model().DoesNotExist:
            return Response({'error': 'No user with this email.'}, status=status.HTTP_404_NOT_FOUND)

        if user.is_verified:
            return Response({'error': 'User is already verified.'}, status=status.HTTP_400_BAD_REQUEST)

        # Generate a new verification token
        token = default_token_generator.make_token(user)
        verification_link = f'http://localhost:5173/verify-email/?user_id={user.id}&token={token}'

        # Send the email
        send_mail(
            'Email Verification - Resent',
            f'Please verify your email by clicking the link: {verification_link}',
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )

        return Response({'message': 'Verification email resent.'}, status=status.HTTP_200_OK)

class UserLoginView(APIView):
    @swagger_auto_schema(
        request_body=UserLoginSerializer,
        responses={
            status.HTTP_200_OK: openapi.Response(
                description="Login successful",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "message": openapi.Schema(type=openapi.TYPE_STRING),
                        "access_token": openapi.Schema(type=openapi.TYPE_STRING),
                        "refresh_token": openapi.Schema(type=openapi.TYPE_STRING),
                    },
                ),
            ),
            status.HTTP_400_BAD_REQUEST: "Invalid credentials",
        },
        operation_description="Authenticate user and return JWT tokens",
    )
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        return Response(
            {
                "message": "Login successful",
                "access_token": access_token,
                "refresh_token": str(refresh),
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_summary="Logout user",
        operation_description="Logs out a user by blacklisting their refresh token.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["refresh"],
            properties={
                "refresh": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Refresh token to be blacklisted"
                )
            }
        ),
        responses={
            200: openapi.Response(description="Successfully logged out"),
            400: openapi.Response(description="Invalid or missing refresh token")
        }
    )
    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            if not refresh_token:
                return Response({'detail': 'Refresh token is required.'}, status=status.HTTP_400_BAD_REQUEST)
            token = RefreshToken(refresh_token)
            token.blacklist()  # Blacklist the refresh token
            return Response({"message": "Successfully logged out."}, status=200)
        except Exception as e:
            return Response({"error": "Invalid refresh token."}, status=400)


class ProfileDetailView(generics.RetrieveUpdateAPIView):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user.profile  # Retrieve the profile of the logged-in user


from django.utils.timezone import now, timedelta
import random
import string
from django.core.mail import send_mail
from django.conf import settings
from .models import PasswordResetOTP
from django.contrib.auth.hashers import make_password


class RequestPasswordResetView(APIView):
    @swagger_auto_schema(
        operation_summary="Request password reset",
        operation_description="Sends a 6-digit OTP to the user's email if the email is associated with an account.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["email"],
            properties={
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_EMAIL,
                    description="Email address associated with the user's account"
                )
            },
            example={"email": "user@example.com"}
        ),
        responses={
            200: openapi.Response(description="OTP sent to email"),
            404: openapi.Response(description="User with this email does not exist")
        }
    )
    def post(self, request):
        email = request.data.get("email")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"message": "User with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)

        # Generate 6-digit OTP
        otp = ''.join(random.choices(string.digits, k=6))

        # Save OTP with expiry time (5 minutes)
        PasswordResetOTP.objects.create(
            user=user,
            otp=otp,
            expires_at=now() + timedelta(minutes=5)
        )

        # Send email with OTP
        send_mail(
            "Password Reset OTP",
            f"Your password reset OTP is: {otp}. It will expire in 5 minutes.",
            settings.DEFAULT_FROM_EMAIL,
            [email],
        )

        return Response({"message": "OTP sent to your email."}, status=status.HTTP_200_OK)


class VerifyOTPView(APIView):
    @swagger_auto_schema(
        operation_summary="Verify password reset OTP",
        operation_description="Verifies the 6-digit OTP sent to the user's email for password reset.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["email", "otp"],
            properties={
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_EMAIL,
                    description="User's email address"
                ),
                "otp": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="6-digit OTP sent via email"
                )
            },
            example={"email": "user@example.com", "otp": "123456"}
        ),
        responses={
            200: openapi.Response(description="OTP verified successfully"),
            400: openapi.Response(description="Invalid or expired OTP"),
            404: openapi.Response(description="User with this email does not exist")
        }
    )
    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"message": "User with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)

        try:
            otp_record = PasswordResetOTP.objects.get(user=user, otp=otp)
        except PasswordResetOTP.DoesNotExist:
            return Response({"message": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

        if otp_record.is_expired():
            return Response({"message": "OTP has expired."}, status=status.HTTP_400_BAD_REQUEST)

        # OTP is valid, proceed to reset password
        return Response({"message": "OTP verified successfully."}, status=status.HTTP_200_OK)
    
class ResetPasswordView(APIView):
    @swagger_auto_schema(
        operation_summary="Reset user password",
        operation_description="Resets the user's password after OTP verification.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["email", "otp", "new_password"],
            properties={
                "email": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_EMAIL,
                    description="User's email address"
                ),
                "otp": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="6-digit OTP sent to email"
                ),
                "new_password": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_PASSWORD,
                    description="New password to be set"
                )
            },
            example={
                "email": "user@example.com",
                "otp": "123456",
                "new_password": "MyNewSecurePassword123"
            }
        ),
        responses={
            200: openapi.Response(description="Password reset successfully"),
            400: openapi.Response(description="Invalid or expired OTP"),
            404: openapi.Response(description="User with this email does not exist")
        }
    )
    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")
        new_password = request.data.get("new_password")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"message": "User with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)

        try:
            otp_record = PasswordResetOTP.objects.get(user=user, otp=otp)
        except PasswordResetOTP.DoesNotExist:
            return Response({"message": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

        if otp_record.is_expired():
            return Response({"message": "OTP has expired."}, status=status.HTTP_400_BAD_REQUEST)

        # Reset the password
        user.password = make_password(new_password)
        user.save()

        # Delete the OTP record
        otp_record.delete()

        return Response({"message": "Password reset successfully."}, status=status.HTTP_200_OK)

# class LogoutAllView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         try:
#             # Get the refresh token from the request (from Authorization header)
#             refresh_token = request.data.get('refresh_token', None)

#             if not refresh_token:
#                 return Response({'detail': 'Refresh token is required.'}, status=status.HTTP_400_BAD_REQUEST)

#             # Create RefreshToken instance
#             token = RefreshToken(refresh_token)

#             # Blacklist the current refresh token (this will prevent further use)
#             token.blacklist()

#             return Response({"message": "Successfully logged out from all sessions."}, status=status.HTTP_200_OK)

#         except TokenError:
#             return Response({"detail": "Token is invalid or already blacklisted."}, status=status.HTTP_401_UNAUTHORIZED)

# @api_view(["GET"])
# @permission_classes([IsAuthenticated])
# def test_authentication(request):
#     user = request.user

#     if not user.is_verified:
#         return Response({"detail": "Email not verified. Please verify your email."}, status=403)

#     return Response({
#         "message": "Authentication successful!",
#         "user": {
#             "email": user.email,
#             "first_name": user.first_name,
#             "last_name": user.last_name,
#             "username": user.username
#         }
#     })

from .serializers import UserSettingsSerializer
from rest_framework import generics, permissions
from .models import Notification
from .serializers import NotificationSerializer


class UserSettingsView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Retrieve or update user settings",
        responses={
            200: UserSettingsSerializer(),
            401: "Unauthorized"
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Update user settings",
        request_body=UserSettingsSerializer,
        responses={
            200: UserSettingsSerializer(),
            400: "Bad Request",
            401: "Unauthorized"
        }
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Partial update user settings",
        request_body=UserSettingsSerializer,
        responses={
            200: UserSettingsSerializer(),
            400: "Bad Request",
            401: "Unauthorized"
        }
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class NotificationListView(generics.ListAPIView):
    """
    View to list all notifications for the authenticated user.
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="List all notifications for the authenticated user",
        responses={
            200: NotificationSerializer(many=True),
            401: "Unauthorized"
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class NotificationMarkAsReadView(generics.UpdateAPIView):
    """
    View to mark a notification as read.
    """
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

    @swagger_auto_schema(
        operation_description="Mark a specific notification as read",
        responses={
            200: NotificationSerializer(),
            401: "Unauthorized",
            404: "Not Found"
        }
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class UserSettingsView(generics.RetrieveUpdateAPIView):
    """
    View to retrieve and update user settings.
    """
    serializer_class = UserSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # Automatically returns the settings for the current user
        return self.request.user.settings

    @swagger_auto_schema(
        operation_description="Retrieve user settings",
        responses={
            200: UserSettingsSerializer(),
            401: "Unauthorized"
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Update all user settings",
        request_body=UserSettingsSerializer,
        responses={
            200: UserSettingsSerializer(),
            400: "Bad Request",
            401: "Unauthorized"
        }
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Partially update user settings",
        request_body=UserSettingsSerializer,
        responses={
            200: UserSettingsSerializer(),
            400: "Bad Request",
            401: "Unauthorized"
        }
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class NotificationListView(generics.ListAPIView):
    """
    View to list all notifications for the authenticated user.
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Returns only notifications for the current authenticated user,
        ordered by most recent first.
        """
        return Notification.objects.filter(
            user=self.request.user
        ).order_by('-created_at')

    @swagger_auto_schema(
        operation_description="List all notifications for the authenticated user (most recent first)",
        responses={
            200: NotificationSerializer(many=True),
            401: "Unauthorized"
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class NotificationMarkAsReadView(generics.UpdateAPIView):
    """
    View to mark a notification as read.
    Only allows marking notifications owned by the current user.
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        """
        Ensures users can only update their own notifications
        """
        return Notification.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        operation_description="Mark a specific notification as read",
        responses={
            200: NotificationSerializer(),
            401: "Unauthorized",
            404: "Not Found"
        }
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class NotificationMarkAllAsReadView(APIView):
    """
    View to mark all unread notifications as read for the authenticated user.
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Mark all unread notifications as read",
        responses={
            200: openapi.Response(
                description="Success response",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'status': openapi.Schema(type=openapi.TYPE_STRING),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER)
                    }
                )
            ),
            401: "Unauthorized"
        }
    )
    def post(self, request, *args, **kwargs):
        # Mark all unread notifications as read for the current user
        updated_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True)
        
        return Response({
            'status': 'success',
            'message': 'Notifications marked as read',
            'count': updated_count
        })