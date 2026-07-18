from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from drf_spectacular.utils import extend_schema
from .serializers import RegisterSerializer, LoginSerializer, RefreshTokenSerializer, UserSerializer
from .services import AuthService, UserService
from django.core.exceptions import ValidationError
from rest_framework.exceptions import AuthenticationFailed


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=RegisterSerializer,
        responses={201: UserSerializer, 400: 'Bad Request'},
        summary='Register a new user',
        description='Create a new user account with username, email, password, and role'
    )
    def post(self, request):
        try:
            user = AuthService.register_user(request.data)
            return Response(
                UserSerializer(user).data,
                status=status.HTTP_201_CREATED
            )
        except ValidationError as e:
            return Response(e.message_dict, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=LoginSerializer,
        responses={200: 'Success', 401: 'Unauthorized'},
        summary='Login and get JWT tokens',
        description='Authenticate user and return access and refresh tokens'
    )
    def post(self, request):
        try:
            result = AuthService.login_user(
                username=request.data.get('username'),
                password=request.data.get('password')
            )
            return Response(result, status=status.HTTP_200_OK)
        except AuthenticationFailed as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_401_UNAUTHORIZED
            )


class RefreshTokenView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=RefreshTokenSerializer,
        responses={200: 'Success', 401: 'Unauthorized'},
        summary='Refresh access token',
        description='Get a new access token using a valid refresh token'
    )
    def post(self, request):
        try:
            result = AuthService.refresh_access_token(
                request.data.get('refresh_token')
            )
            return Response(result, status=status.HTTP_200_OK)
        except AuthenticationFailed as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_401_UNAUTHORIZED
            )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Logout user',
        description='Logout the current user (client side token discard)'
    )
    def post(self, request):
        # With stateless JWT, logout is handled client-side
        return Response(
            {'message': 'Successfully logged out'},
            status=status.HTTP_200_OK
        )


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: UserSerializer, 401: 'Unauthorized'},
        summary='Get current user profile',
        description='Get the authenticated user\'s profile information'
    )
    def get(self, request):
        profile_data = UserService.get_user_profile(request.user)
        return Response(profile_data, status=status.HTTP_200_OK)