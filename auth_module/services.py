from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework.exceptions import AuthenticationFailed
import jwt
from datetime import datetime, timedelta
from django.conf import settings
from .models import User


class AuthService:

    @staticmethod
    def register_user(data):
        required_fields = ['username', 'email', 'password', 'password_confirm']
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationError({field: f'{field} is required'})

        if data['password'] != data['password_confirm']:
            raise ValidationError({'password_confirm': 'Passwords do not match'})

        if len(data['password']) < 8:
            raise ValidationError({'password': 'Password must be at least 8 characters long'})

        valid_roles = ['admin', 'fleet_manager', 'driver']
        role = data.get('role', 'driver')
        if role not in valid_roles:
            raise ValidationError({'role': f'Role must be one of: {", ".join(valid_roles)}'})

        try:
            user = User.objects.create_user(
                username=data['username'],
                email=data['email'],
                password=data['password'],
                role=role,
                first_name=data.get('first_name', ''),
                last_name=data.get('last_name', '')
            )
            return user
        except IntegrityError as e:
            if 'username' in str(e):
                raise ValidationError({'username': 'Username already exists'})
            elif 'email' in str(e):
                raise ValidationError({'email': 'Email already exists'})
            raise

    @staticmethod
    def login_user(username, password):
        user = authenticate(username=username, password=password)

        if not user:
            raise AuthenticationFailed('Invalid username or password')

        if not user.is_active:
            raise AuthenticationFailed('User account is disabled')

        access_token = AuthService._generate_token(user, 'access', minutes=30)
        refresh_token = AuthService._generate_token(user, 'refresh', days=7)

        return {
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'access_token': access_token,
            'refresh_token': refresh_token,
        }

    @staticmethod
    def refresh_access_token(refresh_token):
        try:
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=['HS256'])

            if payload.get('type') != 'refresh':
                raise AuthenticationFailed('Invalid token type. Use refresh token.')

            try:
                user = User.objects.get(id=payload['user_id'])
            except User.DoesNotExist:
                raise AuthenticationFailed('User not found')

            if not user.is_active:
                raise AuthenticationFailed('User account is disabled')

            access_token = AuthService._generate_token(user, 'access', minutes=30)

            return {
                'access_token': access_token,
            }

        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Refresh token has expired')
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid refresh token')

    @staticmethod
    def _generate_token(user, token_type, minutes=0, days=0):
        if token_type == 'access':
            expiry = datetime.utcnow() + timedelta(minutes=minutes)
        else:
            expiry = datetime.utcnow() + timedelta(days=days)

        payload = {
            'user_id': user.id,
            'username': user.username,
            'role': user.role,
            'exp': expiry,
            'iat': datetime.utcnow(),
            'type': token_type,
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


class UserService:

    @staticmethod
    def get_user_profile(user):
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'role_display': user.get_role_display(),
            'first_name': user.first_name,
            'last_name': user.last_name,
            'full_name': f"{user.first_name} {user.last_name}".strip(),
            'is_active': user.is_active,
            'created_at': user.created_at,
            'updated_at': user.updated_at,
        }

    @staticmethod
    def get_user_by_id(user_id):
        return User.objects.get(id=user_id)

    @staticmethod
    def get_users_by_role(role):
        return User.objects.filter(role=role, is_active=True)

    @staticmethod
    def update_user_profile(user, data):
        allowed_fields = ['first_name', 'last_name', 'email']

        for field in allowed_fields:
            if field in data and data[field]:
                setattr(user, field, data[field])

        user.save()
        return user

    @staticmethod
    def change_password(user, old_password, new_password, new_password_confirm):
        if not user.check_password(old_password):
            raise AuthenticationFailed('Current password is incorrect')

        if len(new_password) < 8:
            raise ValidationError({'new_password': 'Password must be at least 8 characters long'})

        if new_password != new_password_confirm:
            raise ValidationError({'new_password_confirm': 'Passwords do not match'})

        user.set_password(new_password)
        user.save()
        return True