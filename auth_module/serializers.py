from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from .models import User
import jwt
from django.conf import settings


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'first_name', 'last_name', 'created_at']
        read_only_fields = ['id', 'created_at']


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm', 'role', 'first_name', 'last_name']

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match'})
        return data

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data['username'], password=data['password'])
        if not user:
            raise AuthenticationFailed('Invalid username or password')
        if not user.is_active:
            raise AuthenticationFailed('User account is disabled')

        access_token = self._generate_jwt_token(user, 'access')
        refresh_token = self._generate_jwt_token(user, 'refresh')

        return {
            'user': UserSerializer(user).data,
            'access_token': access_token,
            'refresh_token': refresh_token,
        }

    def _generate_jwt_token(self, user, token_type):
        import datetime
        if token_type == 'access':
            exp = datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
        else:
            exp = datetime.datetime.utcnow() + datetime.timedelta(days=7)

        payload = {
            'user_id': user.id,
            'username': user.username,
            'role': user.role,
            'exp': exp,
            'iat': datetime.datetime.utcnow(),
            'type': token_type,
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


class RefreshTokenSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()

    def validate(self, data):
        try:
            payload = jwt.decode(data['refresh_token'], settings.SECRET_KEY, algorithms=['HS256'])
            if payload.get('type') != 'refresh':
                raise AuthenticationFailed('Invalid token type')

            from .models import User
            user = User.objects.get(id=payload['user_id'])

            access_token = self._generate_access_token(user)

            return {
                'access_token': access_token,
            }
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Refresh token has expired')
        except (jwt.InvalidTokenError, User.DoesNotExist):
            raise AuthenticationFailed('Invalid refresh token')

    def _generate_access_token(self, user):
        import datetime
        exp = datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
        payload = {
            'user_id': user.id,
            'username': user.username,
            'role': user.role,
            'exp': exp,
            'iat': datetime.datetime.utcnow(),
            'type': 'access',
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')