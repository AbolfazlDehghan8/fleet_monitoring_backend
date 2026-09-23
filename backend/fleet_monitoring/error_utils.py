import re

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response

_KEY_COLUMNS_RE = re.compile(r'Key \(([^)]+)\)=')


def validation_error_response(exc, status_code=status.HTTP_400_BAD_REQUEST):
    detail = exc.message_dict if hasattr(exc, 'message_dict') else {'detail': exc.messages}
    return Response(detail, status=status_code)


def integrity_error_to_validation(exc, known_fields, messages=None, aliases=None,
                                  default='Could not save record due to a conflicting record'):
    messages = messages or {}
    aliases = aliases or {}
    cause = getattr(exc, '__cause__', None)
    detail = getattr(getattr(cause, 'diag', None), 'message_detail', None) or str(exc)

    match = _KEY_COLUMNS_RE.search(detail)
    if match:
        for column in (c.strip() for c in match.group(1).split(',')):
            field = aliases.get(column, column)
            if field in known_fields:
                return DjangoValidationError({field: messages.get(field, f'{field} already exists')})
    return DjangoValidationError({'detail': default})