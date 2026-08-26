from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import User
from .permissions import IsAdmin
from .serializers import (
    AdminUserCreateSerializer,
    AdminUserUpdateSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    ProfileUpdateSerializer,
    RefreshTokenSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .services import AuthService, UserService
from fleet_monitoring.error_utils import validation_error_response


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'register'

    @extend_schema(
        request=RegisterSerializer,
        responses={201: UserSerializer, 400: 'Bad Request'},
        summary='Register a new user',
        description=(
            'Create a new user account with username, email, and password. '
            'All self-registered accounts are created with the driver role; '
            'elevated roles are assigned by an Admin (see /api/v1/admin/users/).'
        ),
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = AuthService.register_user(serializer.validated_data)
        except ValidationError as exc:
            return validation_error_response(exc)

        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    @extend_schema(
        request=LoginSerializer,
        responses={200: 'Success', 401: 'Unauthorized'},
        summary='Login and get JWT tokens',
        description='Authenticate user and return access and refresh tokens',
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = AuthService.login_user(**serializer.validated_data)
        except AuthenticationFailed as exc:
            return Response({'error': str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

        return Response(result, status=status.HTTP_200_OK)


class RefreshTokenView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=RefreshTokenSerializer,
        responses={200: 'Success', 401: 'Unauthorized'},
        summary='Refresh access token',
        description='Get a new access token using a valid refresh token',
    )
    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = AuthService.refresh_access_token(serializer.validated_data['refresh_token'])
        except AuthenticationFailed as exc:
            return Response({'error': str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

        return Response(result, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=LogoutSerializer,
        summary='Logout user',
        description=(
            'Logs out the current user. Access tokens remain stateless and simply expire '
            '(ADR 15.7). If a refresh_token is supplied in the body, it is revoked '
            'immediately (RSK-S01 mitigation) so it cannot be used again.'
        ),
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AuthService.logout_user(request.user, serializer.validated_data.get('refresh_token'))

        return Response({'message': 'Successfully logged out'}, status=status.HTTP_200_OK)


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: UserSerializer, 401: 'Unauthorized'},
        summary='Get current user profile',
        description="Get the authenticated user's profile information",
    )
    def get(self, request):
        return Response(UserService.get_user_profile(request.user), status=status.HTTP_200_OK)

    @extend_schema(
        request=ProfileUpdateSerializer,
        responses={200: UserSerializer, 400: 'Bad Request'},
        summary='Update current user profile',
        description="Update the authenticated user's own first name, last name, or email",
    )
    def patch(self, request):
        serializer = ProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            user = UserService.update_user_profile(request.user, serializer.validated_data)
        except ValidationError as exc:
            return validation_error_response(exc)

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ChangePasswordSerializer,
        responses={200: 'Success', 400: 'Bad Request', 401: 'Unauthorized'},
        summary='Change current user password',
        description="Change the authenticated user's password",
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            UserService.change_password(request.user, data['old_password'], data['new_password'])
        except AuthenticationFailed as exc:
            return Response({'error': str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

        return Response({'message': 'Password changed successfully'}, status=status.HTTP_200_OK)


class AdminUserListView(APIView):

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        responses={200: UserSerializer(many=True), 403: 'Forbidden'},
        summary='List all users (admin only)',
        description='List all users in the system, optionally filtered by role',
    )
    def get(self, request):
        role = request.query_params.get('role')
        users = UserService.list_users(role=role)
        return Response(UserSerializer(users, many=True).data, status=status.HTTP_200_OK)

    @extend_schema(
        request=AdminUserCreateSerializer,
        responses={201: UserSerializer, 400: 'Bad Request', 403: 'Forbidden'},
        summary='Create (provision) a user with any role (admin only)',
        description=(
            'Section 2.1: System Administrators own user provisioning and role assignment. '
            'Unlike public registration, this endpoint may create admin/fleet_manager accounts.'
        ),
    )
    def post(self, request):
        serializer = AdminUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = AuthService.admin_create_user(request.user, serializer.validated_data)
        except ValidationError as exc:
            return validation_error_response(exc)

        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class AdminUserDetailView(APIView):

    permission_classes = [IsAuthenticated, IsAdmin]

    @extend_schema(
        responses={200: UserSerializer, 404: 'Not Found', 403: 'Forbidden'},
        summary='Retrieve a user by id (admin only)',
    )
    def get(self, request, user_id):
        try:
            user = UserService.get_user_by_id(user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)

    @extend_schema(
        request=AdminUserUpdateSerializer,
        responses={200: UserSerializer, 400: 'Bad Request', 403: 'Forbidden', 404: 'Not Found'},
        summary='Update a user (admin only)',
        description='Admin can update role, active status, name, and email of any user',
    )
    def patch(self, request, user_id):
        serializer = AdminUserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            user = UserService.admin_update_user(request.user, user_id, serializer.validated_data)
        except ValidationError as exc:
            detail = exc.message_dict if hasattr(exc, 'message_dict') else {'detail': exc.messages}
            status_code = status.HTTP_404_NOT_FOUND if detail.get('detail') == 'User not found' else status.HTTP_400_BAD_REQUEST
            return Response(detail, status=status_code)

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)

    @extend_schema(
        responses={204: None, 403: 'Forbidden', 404: 'Not Found'},
        summary='Delete a user (admin only)',
    )
    def delete(self, request, user_id):
        try:
            UserService.delete_user(request.user, user_id)
        except ValidationError:
            return Response({'detail': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response(status=status.HTTP_204_NO_CONTENT)