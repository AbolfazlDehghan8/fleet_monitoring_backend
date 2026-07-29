from rest_framework import authentication, exceptions
import jwt
from django.conf import settings
from .models import User


class JWTAuthentication(authentication.BaseAuthentication):

    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            return None

        try:
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != 'bearer':
                raise exceptions.AuthenticationFailed(
                    'Invalid Authorization header format. Use: Bearer <token>'
                )

            token = parts[1]

            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])

            if payload.get('type') != 'access':
                raise exceptions.AuthenticationFailed(
                    'Invalid token type. Use access token.'
                )

            user = User.objects.get(id=payload['user_id'])

            if not user.is_active:
                raise exceptions.AuthenticationFailed('User account is disabled')

            return (user, payload)

        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Access token has expired')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('Invalid token')
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('User not found')

    def authenticate_header(self, request):
        return 'Bearer'