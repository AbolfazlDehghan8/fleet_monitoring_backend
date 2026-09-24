import jwt
from rest_framework import authentication, exceptions

from . import tokens
from .models import User


class JWTAuthentication(authentication.BaseAuthentication):

    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            raise exceptions.AuthenticationFailed('Invalid Authorization header format. Use: Bearer <token>')

        try:
            payload = tokens.decode(parts[1])
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Access token has expired')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('Invalid token')

        if payload.get('type') != tokens.ACCESS:
            raise exceptions.AuthenticationFailed('Invalid token type. Use access token.')

        try:
            user = User.objects.get(id=payload['user_id'])
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('User not found')
        except (ValueError, TypeError):
            raise exceptions.AuthenticationFailed('Invalid token')

        if not user.is_active:
            raise exceptions.AuthenticationFailed('User account is disabled')

        return (user, payload)

    def authenticate_header(self, request):
        return 'Bearer'