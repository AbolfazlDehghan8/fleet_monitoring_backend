from rest_framework import status
from rest_framework.response import Response


def validation_error_response(exc, status_code=status.HTTP_400_BAD_REQUEST):
    detail = exc.message_dict if hasattr(exc, 'message_dict') else {'detail': exc.messages}
    return Response(detail, status=status_code)