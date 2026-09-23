import logging

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger('audit')

CONFLICT_MESSAGE = 'Could not save record due to a conflicting record'
SERVER_ERROR_MESSAGE = 'Internal server error'


def api_exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        detail = exc.message_dict if hasattr(exc, 'message_dict') else {'detail': exc.messages}
        return Response(detail, status=status.HTTP_400_BAD_REQUEST)

    if isinstance(exc, IntegrityError):
        logger.warning(
            'integrity_error',
            extra={'actor': 'api', 'action': 'integrity_error', 'target': str(exc)[:200]},
        )
        return Response({'detail': [CONFLICT_MESSAGE]}, status=status.HTTP_409_CONFLICT)

    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    if settings.DEBUG:
        return None

    logger.exception('unhandled_api_exception')
    return Response({'detail': SERVER_ERROR_MESSAGE}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)