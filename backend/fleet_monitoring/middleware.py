import re
import uuid
from contextvars import ContextVar

_correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='-')

_VALID_REQUEST_ID = re.compile(r'[A-Za-z0-9._:-]{1,128}')


def get_correlation_id():
    return _correlation_id_var.get()


def set_correlation_id(correlation_id):
    return _correlation_id_var.set(correlation_id)


def reset_correlation_id(token):
    _correlation_id_var.reset(token)


class CorrelationIdMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied = request.headers.get('X-Request-ID', '')
        correlation_id = supplied if _VALID_REQUEST_ID.fullmatch(supplied) else str(uuid.uuid4())
        request.correlation_id = correlation_id
        token = set_correlation_id(correlation_id)
        try:
            response = self.get_response(request)
        finally:
            reset_correlation_id(token)
        response['X-Request-ID'] = correlation_id
        return response