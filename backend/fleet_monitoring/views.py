import logging
import secrets

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import Http404
from django_prometheus.exports import ExportToDjangoView
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([])
def health_check(request):
    checks = {}

    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        checks['database'] = 'ok'
    except Exception:
        logger.exception('health_check_database_failed')
        checks['database'] = 'error'

    try:
        cache.set('health_check_probe', '1', timeout=5)
        checks['cache'] = 'ok' if cache.get('health_check_probe') == '1' else 'error'
    except Exception:
        logger.exception('health_check_cache_failed')
        checks['cache'] = 'error'

    healthy = all(v == 'ok' for v in checks.values())
    return Response(
        {'status': 'ok' if healthy else 'degraded', 'checks': checks},
        status=200 if healthy else 503,
    )


def metrics(request):
    token = settings.METRICS_TOKEN
    if token:
        supplied = request.headers.get('Authorization', '').removeprefix('Bearer ').strip()
        if not secrets.compare_digest(supplied, token):
            raise Http404
    elif not settings.DEBUG:
        raise Http404
    return ExportToDjangoView(request)