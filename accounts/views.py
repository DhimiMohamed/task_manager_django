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

User = get_user_model()

class UserRegistrationView(APIView):
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            Profile.objects.create(user=user)  # Create a profile for the new user
            return Response({'message': 'User registered successfully. Please check your email for verification.'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class VerifyEmailView(APIView):
    def get(self, request, user_id, token):
        User = get_user_model()

        try:
            user = User.objects.get(id=user_id)  # Fetch user by ID
        except User.DoesNotExist:
            return Response({"error": "Invalid user."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate the token
        if default_token_generator.check_token(user, token):
            # Mark the user as verified
            user.is_verified = True
            user.save()

            return Response({"message": "Email successfully verified. You can now log in."}, status=status.HTTP_200_OK)

        return Response({"error": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)



class UserLoginView(APIView):
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

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def test_authentication(request):
    user = request.user

    if not user.is_verified:
        return Response({"detail": "Email not verified. Please verify your email."}, status=403)

    return Response({
        "message": "Authentication successful!",
        "user": {
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username
        }
    })