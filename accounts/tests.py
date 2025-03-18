from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models import Profile

# Get the custom user model
User = get_user_model()

class CustomUserModelTest(TestCase):
    def test_create_user(self):
        # Test creating a user with required fields
        user = User.objects.create_user(
            email='test@example.com',
            first_name='John',
            last_name='Doe',
            password='testpass123'
        )
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.first_name, 'John')
        self.assertEqual(user.last_name, 'Doe')
        self.assertFalse(user.is_verified)  # is_verified should default to False

    def test_email_uniqueness(self):
        # Test that the email field is unique
        User.objects.create_user(
            email='test@example.com',
            first_name='John',
            last_name='Doe',
            password='testpass123'
        )
        with self.assertRaises(Exception):  # Should raise an error if email is not unique
            User.objects.create_user(
                email='test@example.com',
                first_name='Jane',
                last_name='Doe',
                password='testpass123'
            )


class ProfileModelTest(TestCase):
    def test_create_profile(self):
        # Create a user
        user = User.objects.create_user(
            email='test@example.com',
            first_name='John',
            last_name='Doe',
            password='testpass123'
        )
        # Create a profile linked to the user
        profile = Profile.objects.create(
            user=user,
            bio='This is a test bio.',
            date_of_birth='1990-01-01',
            location='Test City'
        )
        self.assertEqual(profile.user.email, 'test@example.com')
        self.assertEqual(profile.bio, 'This is a test bio.')
        self.assertEqual(profile.location, 'Test City')

    def test_optional_fields(self):
        # Test that bio, date_of_birth, and location are optional
        user = User.objects.create_user(
            email='test@example.com',
            first_name='John',
            last_name='Doe',
            password='testpass123'
        )
        profile = Profile.objects.create(user=user)
        self.assertIsNone(profile.bio)
        self.assertIsNone(profile.date_of_birth)
        self.assertIsNone(profile.location)


from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth.tokens import default_token_generator
from rest_framework_simplejwt.tokens import RefreshToken
 

class UserRegistrationViewTest(APITestCase):
    def test_user_registration_success(self):
        # Test successful user registration
        data = {
            'email': 'test@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'password': 'testpass123',
            'password2': 'testpass123'
        }
        response = self.client.post('/api/accounts/register/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['message'], 'User registered successfully. Please check your email for verification.')

    def test_user_registration_invalid_data(self):
        # Test registration with invalid data (mismatched passwords)
        data = {
            'email': 'test@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'password': 'testpass123',
            'password2': 'wrongpass'
        }
        response = self.client.post('/api/accounts/register/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)  # Ensure the error is related to password mismatch

class VerifyEmailViewTest(APITestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='John',
            last_name='Doe',
            password='testpass123'
        )
        self.token = default_token_generator.make_token(self.user)

    def test_email_verification_success(self):
        # Test successful email verification
        response = self.client.get(f'/api/accounts/verify/{self.user.id}/{self.token}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Email successfully verified. You can now log in.')

    def test_email_verification_invalid_token(self):
        # Test verification with an invalid token
        response = self.client.get(f'/api/accounts/verify/{self.user.id}/invalid-token/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Invalid or expired token.')

class UserLoginViewTest(APITestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='John',
            last_name='Doe',
            password='testpass123'
        )
        self.user.is_verified = True
        self.user.save()

    def test_user_login_success(self):
        # Test successful login
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        response = self.client.post('/api/accounts/login/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Login successful')
        self.assertIn('access_token', response.data)
        self.assertIn('refresh_token', response.data)

    def test_user_login_invalid_credentials(self):
        # Test login with invalid credentials
        data = {
            'email': 'test@example.com',
            'password': 'wrongpass'
        }
        response = self.client.post('/api/accounts/login/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['detail'], 'Invalid email or password.')

    def test_user_login_unverified(self):
        # Test login for an unverified user
        self.user.is_verified = False
        self.user.save()
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        response = self.client.post('/api/accounts/login/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['detail'], 'Email not verified. Please check your inbox.')

class LogoutViewTest(APITestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='John',
            last_name='Doe',
            password='testpass123'
        )
        self.user.is_verified = True
        self.user.save()
        self.refresh_token = str(RefreshToken.for_user(self.user))

    def test_user_logout_success(self):
        # Test successful logout
        self.client.force_authenticate(user=self.user)
        data = {'refresh': self.refresh_token}
        response = self.client.post('/api/accounts/logout/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Successfully logged out.')

    def test_user_logout_invalid_token(self):
        # Test logout with an invalid refresh token
        self.client.force_authenticate(user=self.user)
        data = {'refresh': 'invalid-token'}
        response = self.client.post('/api/accounts/logout/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Invalid refresh token.')

class ProfileDetailViewTest(APITestCase):
    def setUp(self):
        # Create a test user and profile
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='John',
            last_name='Doe',
            password='testpass123'
        )
        self.user.is_verified = True
        self.user.save()
        self.profile = Profile.objects.create(user=self.user, bio='Test bio', location='Test City')

    def test_profile_retrieval(self):
        # Test retrieving the profile of the logged-in user
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/accounts/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['email'], 'test@example.com')
        self.assertEqual(response.data['bio'], 'Test bio')

    def test_profile_update(self):
        # Test updating the profile
        self.client.force_authenticate(user=self.user)
        data = {'bio': 'Updated bio', 'location': 'Updated City'}
        response = self.client.patch('/api/accounts/profile/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['bio'], 'Updated bio')
        self.assertEqual(response.data['location'], 'Updated City')


from rest_framework.exceptions import ValidationError, AuthenticationFailed
from .serializers import UserRegistrationSerializer, UserLoginSerializer, ProfileSerializer


class UserRegistrationSerializerTest(TestCase):
    def test_user_registration_success(self):
        # Test successful user registration
        data = {
            'email': 'test@example.com',
            'username': 'testuser',
            'first_name': 'John',
            'last_name': 'Doe',
            'password': 'testpass123',
            'password2': 'testpass123'
        }
        serializer = UserRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.first_name, 'John')
        self.assertEqual(user.last_name, 'Doe')
        self.assertFalse(user.is_verified)  # User should be unverified initially

    def test_user_registration_password_mismatch(self):
        # Test registration with mismatched passwords
        data = {
            'email': 'test@example.com',
            'username': 'testuser',
            'first_name': 'John',
            'last_name': 'Doe',
            'password': 'testpass123',
            'password2': 'wrongpass'
        }
        serializer = UserRegistrationSerializer(data=data)
        with self.assertRaises(ValidationError) as context:
            serializer.is_valid(raise_exception=True)
        self.assertIn('password', context.exception.detail)  # Ensure the error is related to password mismatch

    def test_user_registration_missing_fields(self):
        # Test registration with missing required fields
        data = {
            'email': 'test@example.com',
            'password': 'testpass123',
            'password2': 'testpass123'
        }
        serializer = UserRegistrationSerializer(data=data)
        with self.assertRaises(ValidationError) as context:
            serializer.is_valid(raise_exception=True)
        self.assertIn('first_name', context.exception.detail)  # Ensure the error is related to missing fields


class UserLoginSerializerTest(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='John',
            last_name= 'Doe',
            password='testpass123'
        )
        self.user.is_verified = True
        self.user.save()

    def test_user_login_success(self):
        # Test successful login
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        serializer = UserLoginSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['user'], self.user)

    def test_user_login_invalid_credentials(self):
        # Test login with invalid credentials
        data = {
            'email': 'test@example.com',
            'password': 'wrongpass'
        }
        serializer = UserLoginSerializer(data=data)
        with self.assertRaises(AuthenticationFailed) as context:
            serializer.is_valid(raise_exception=True)
        self.assertEqual(str(context.exception), 'Invalid email or password.')

    def test_user_login_unverified(self):
        # Test login for an unverified user
        self.user.is_verified = False
        self.user.save()
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        serializer = UserLoginSerializer(data=data)
        with self.assertRaises(AuthenticationFailed) as context:
            serializer.is_valid(raise_exception=True)
        self.assertEqual(str(context.exception), 'Email not verified. Please check your inbox.')


class ProfileSerializerTest(TestCase):
    def setUp(self):
        # Create a test user and profile
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='John',
            last_name='Doe',
            password='testpass123'
        )
        self.profile = Profile.objects.create(user=self.user, bio='Test bio', location='Test City')

    def test_profile_serialization(self):
        # Test serialization of profile data
        serializer = ProfileSerializer(instance=self.profile)
        expected_data = {
            'user': {
                'email': 'test@example.com',
                'first_name': 'John',
                'last_name': 'Doe'
            },
            'bio': 'Test bio',
            'location': 'Test City'
        }
        self.assertEqual(serializer.data, expected_data)

    def test_profile_deserialization(self):
        # Test updating profile data
        data = {
            'bio': 'Updated bio',
            'location': 'Updated City'
        }
        serializer = ProfileSerializer(instance=self.profile, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        updated_profile = serializer.save()
        self.assertEqual(updated_profile.bio, 'Updated bio')
        self.assertEqual(updated_profile.location, 'Updated City')


from django.utils.timezone import now, timedelta
from .models import PasswordResetOTP


class PasswordResetOTPModelTest(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='John',
            last_name='Doe',
            password='testpass123'
        )

    def test_otp_creation(self):
        # Test creating an OTP record
        otp = PasswordResetOTP.objects.create(
            user=self.user,
            otp='123456',
            expires_at=now() + timedelta(minutes=5)
        )
        self.assertEqual(otp.user.email, 'test@example.com')
        self.assertEqual(otp.otp, '123456')
        self.assertFalse(otp.is_expired())  # OTP should not be expired

    def test_otp_expiry(self):
        # Test OTP expiry
        otp = PasswordResetOTP.objects.create(
            user=self.user,
            otp='123456',
            expires_at=now() - timedelta(minutes=5))  # OTP expired 5 minutes ago
        self.assertTrue(otp.is_expired())  # OTP should be expired


class RequestPasswordResetViewTest(APITestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='John',
            last_name='Doe',
            password='testpass123'
        )

    def test_request_password_reset_success(self):
        # Test successful OTP generation
        data = {'email': 'test@example.com'}
        response = self.client.post('/api/accounts/password-reset/request/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'OTP sent to your email.')

        # Check if OTP record was created
        otp_record = PasswordResetOTP.objects.filter(user=self.user).first()
        self.assertIsNotNone(otp_record)
        self.assertEqual(len(otp_record.otp), 6)  # OTP should be 6 digits

    def test_request_password_reset_user_not_found(self):
        # Test case where user does not exist
        data = {'email': 'nonexistent@example.com'}
        response = self.client.post('/api/accounts/password-reset/request/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['message'], 'User with this email does not exist.')


class VerifyOTPViewTest(APITestCase):
    def setUp(self):
        # Create a test user and OTP record
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='John',
            last_name='Doe',
            password='testpass123'
        )
        self.otp = PasswordResetOTP.objects.create(
            user=self.user,
            otp='123456',
            expires_at=now() + timedelta(minutes=5)
        )

    def test_verify_otp_success(self):
        # Test successful OTP verification
        data = {'email': 'test@example.com', 'otp': '123456'}
        response = self.client.post('/api/accounts/password-reset/verify-otp/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'OTP verified successfully.')

    def test_verify_otp_invalid(self):
        # Test invalid OTP
        data = {'email': 'test@example.com', 'otp': '000000'}
        response = self.client.post('/api/accounts/password-reset/verify-otp/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], 'Invalid OTP.')

    def test_verify_otp_expired(self):
        # Test expired OTP
        self.otp.expires_at = now() - timedelta(minutes=5)
        self.otp.save()
        data = {'email': 'test@example.com', 'otp': '123456'}
        response = self.client.post('/api/accounts/password-reset/verify-otp/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], 'OTP has expired.')


class ResetPasswordViewTest(APITestCase):
    def setUp(self):
        # Create a test user and OTP record
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='John',
            last_name='Doe',
            password='testpass123'
        )
        self.otp = PasswordResetOTP.objects.create(
            user=self.user,
            otp='123456',
            expires_at=now() + timedelta(minutes=5)
        )

    def test_reset_password_success(self):
        # Test successful password reset
        data = {
            'email': 'test@example.com',
            'otp': '123456',
            'new_password': 'newpass123'
        }
        response = self.client.post('/api/accounts/password-reset/reset-password/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Password reset successfully.')

        # Check if password was updated
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpass123'))

        # Check if OTP record was deleted
        self.assertFalse(PasswordResetOTP.objects.filter(user=self.user).exists())

    def test_reset_password_invalid_otp(self):
        # Test invalid OTP
        data = {
            'email': 'test@example.com',
            'otp': '000000',
            'new_password': 'newpass123'
        }
        response = self.client.post('/api/accounts/password-reset/reset-password/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], 'Invalid OTP.')

    def test_reset_password_expired_otp(self):
        # Test expired OTP
        self.otp.expires_at = now() - timedelta(minutes=5)
        self.otp.save()
        data = {
            'email': 'test@example.com',
            'otp': '123456',
            'new_password': 'newpass123'
        }
        response = self.client.post('/api/accounts/password-reset/reset-password/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['message'], 'OTP has expired.')