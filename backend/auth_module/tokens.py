import uuid
from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings

ALGORITHM = 'HS256'
REQUIRED_CLAIMS = ['exp', 'iat', 'type', 'user_id']
LEEWAY_SECONDS = 10

ACCESS = 'access'
REFRESH = 'refresh'


def access_lifetime():
    return timedelta(minutes=settings.JWT_ACCESS_LIFETIME_MINUTES)


def refresh_lifetime():
    return timedelta(days=settings.JWT_REFRESH_LIFETIME_DAYS)


def encode(user, token_type, lifetime, jti=None):
    now = datetime.now(timezone.utc)
    payload = {
        'user_id': user.id,
        'username': user.username,
        'role': user.role,
        'type': token_type,
        'iat': now,
        'exp': now + lifetime,
        'jti': str(jti or uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm=ALGORITHM), payload


def decode(token):
    return jwt.decode(
        token,
        settings.JWT_SIGNING_KEY,
        algorithms=[ALGORITHM],
        options={'require': REQUIRED_CLAIMS},
        leeway=LEEWAY_SECONDS,
    )