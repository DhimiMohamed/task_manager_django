from django.urls import path
from .views import UserRegistrationView, VerifyEmailView, UserLoginView, LogoutView, ProfileDetailView, RequestPasswordResetView, VerifyOTPView, ResetPasswordView, ResendVerificationEmailView, UserSettingsView, NotificationListView, NotificationMarkAsReadView, NotificationMarkAllAsReadView
from rest_framework_simplejwt.views import TokenRefreshView


urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='user_register'),
    path('verify/<int:user_id>/<str:token>/', VerifyEmailView.as_view(), name='verify-email'),
    path('resend-verification/', ResendVerificationEmailView.as_view(), name='resend-verification'),
    path("login/", UserLoginView.as_view(), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),  # Refresh token endpoint
    # path("test-auth/", test_authentication, name="test-auth"),
    path('logout/', LogoutView.as_view(), name='logout'),
    # path('logout/all/', LogoutAllView.as_view(), name='logout-all'),
    path('profile/', ProfileDetailView.as_view(), name='profile-detail'),
    path("password-reset/request/", RequestPasswordResetView.as_view(), name="password_reset_request"),
    path('password-reset/verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('password-reset/reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('settings/', UserSettingsView.as_view(), name='user-settings-api'),
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/<int:id>/mark-as-read/', NotificationMarkAsReadView.as_view(), name='notification-mark-read'),
    path('notifications/mark-all-as-read/', NotificationMarkAllAsReadView.as_view(), name='notification-mark-all-read'),
]

