
import logging
from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework.exceptions import AuthenticationFailed

from .models import User


audit_logger = logging.getLogger('audit')

ACCESS_TOKEN_LIFETIME_MINUTES = 30
REFRESH_TOKEN_LIFETIME_DAYS = 7


class AuthService:

    @staticmethod
    def register_user(validated_data):
        role = validated_data.get('role', User.Role.DRIVER)

        try:
            user = User.objects.create_user(
                username=validated_data['username'],
                email=validated_data['email'],
                password=validated_data['password'],
                role=role,
                first_name=validated_data.get('first_name', ''),
                last_name=validated_data.get('last_name', ''),
            )
        except IntegrityError as exc:
            message = str(exc).lower()
            if 'username' in message:
                raise ValidationError({'username': 'Username already exists'})
            if 'email' in message:
                raise ValidationError({'email': 'Email already exists'})
            raise ValidationError({'detail': 'Could not create user due to a conflicting record'})

        audit_logger.info(
            'user_registered', extra={'actor': user.id, 'action': 'register', 'target': user.id}
        )
        return user

    @staticmethod
    def login_user(username, password):
        from django.contrib.auth import authenticate

        user = authenticate(username=username, password=password)

        if not user:
            raise AuthenticationFailed('Invalid username or password')

        if not user.is_active:
            raise AuthenticationFailed('User account is disabled')

        access_token = AuthService._generate_token(user, 'access', minutes=ACCESS_TOKEN_LIFETIME_MINUTES)
        refresh_token = AuthService._generate_token(user, 'refresh', days=REFRESH_TOKEN_LIFETIME_DAYS)

        audit_logger.info('user_login', extra={'actor': user.id, 'action': 'login', 'target': user.id})

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

            access_token = AuthService._generate_token(user, 'access', minutes=ACCESS_TOKEN_LIFETIME_MINUTES)

            return {'access_token': access_token}

        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Refresh token has expired')
        except jwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid refresh token')

    @staticmethod
    def _generate_token(user, token_type, minutes=0, days=0):
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(minutes=minutes) if token_type == 'access' else now + timedelta(days=days)

        payload = {
            'user_id': user.id,
            'username': user.username,
            'role': user.role,
            'exp': expiry,
            'iat': now,
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
    def list_users(role=None):
        queryset = User.objects.all().order_by('-created_at')
        if role:
            queryset = queryset.filter(role=role)
        return queryset

    @staticmethod
    def update_user_profile(user, data):
        allowed_fields = ['first_name', 'last_name', 'email']
        for field in allowed_fields:
            if field in data:
                setattr(user, field, data[field])

        try:
            user.save()
        except IntegrityError:
            raise ValidationError({'email': 'Email already exists'})

        audit_logger.info('profile_updated', extra={'actor': user.id, 'action': 'update_profile', 'target': user.id})
        return user

    @staticmethod
    def change_password(user, old_password, new_password):
        if not user.check_password(old_password):
            raise AuthenticationFailed('Current password is incorrect')

        user.set_password(new_password)
        user.save()

        audit_logger.info('password_changed', extra={'actor': user.id, 'action': 'change_password', 'target': user.id})
        return True

    @staticmethod
    def admin_update_user(actor, user_id, data):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValidationError({'detail': 'User not found'})

        allowed_fields = ['first_name', 'last_name', 'email', 'role', 'is_active']
        for field in allowed_fields:
            if field in data:
                setattr(user, field, data[field])

        try:
            user.save()
        except IntegrityError:
            raise ValidationError({'email': 'Email already exists'})

        audit_logger.info('user_updated_by_admin', extra={'actor': actor.id, 'action': 'admin_update_user', 'target': user.id})
        return user

    @staticmethod
    def delete_user(actor, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValidationError({'detail': 'User not found'})

        audit_logger.info('user_deleted_by_admin', extra={'actor': actor.id, 'action': 'delete_user', 'target': user_id})
        user.delete()
