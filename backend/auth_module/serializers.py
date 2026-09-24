from django.contrib.auth.validators import UnicodeUsernameValidator
from rest_framework import serializers

from .models import User

PASSWORD_MAX_LENGTH = 128


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'first_name', 'last_name', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class UserProfileSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'role', 'role_display', 'first_name', 'last_name',
            'full_name', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_full_name(self, obj):
        return f'{obj.first_name} {obj.last_name}'.strip()


class UniqueUserFieldsMixin:
    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('Username already exists')
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Email already exists')
        return value


_USER_FIELD_KWARGS = {
    'username': {'validators': [UnicodeUsernameValidator()]},
    'email': {'validators': []},
}


class RegisterSerializer(UniqueUserFieldsMixin, serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, max_length=PASSWORD_MAX_LENGTH)
    password_confirm = serializers.CharField(write_only=True, min_length=8, max_length=PASSWORD_MAX_LENGTH)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm', 'first_name', 'last_name']
        extra_kwargs = _USER_FIELD_KWARGS

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match'})
        return data


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, max_length=PASSWORD_MAX_LENGTH)


class RefreshTokenSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class ProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField(required=False)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, max_length=PASSWORD_MAX_LENGTH)
    new_password = serializers.CharField(write_only=True, min_length=8, max_length=PASSWORD_MAX_LENGTH)
    new_password_confirm = serializers.CharField(write_only=True, min_length=8, max_length=PASSWORD_MAX_LENGTH)

    def validate(self, data):
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': 'Passwords do not match'})
        if data['old_password'] == data['new_password']:
            raise serializers.ValidationError(
                {'new_password': 'New password must be different from the current password'}
            )
        return data


class AdminUserCreateSerializer(UniqueUserFieldsMixin, serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, max_length=PASSWORD_MAX_LENGTH)
    password_confirm = serializers.CharField(write_only=True, min_length=8, max_length=PASSWORD_MAX_LENGTH)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm', 'role', 'first_name', 'last_name']
        extra_kwargs = _USER_FIELD_KWARGS

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match'})
        return data


class AdminUserUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField(required=False)
    role = serializers.ChoiceField(choices=User.Role.choices, required=False)
    is_active = serializers.BooleanField(required=False)


class LogoutSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(required=False, allow_blank=True)