from django.db import connection
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    checks = {}

    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        checks['database'] = 'ok'
    except Exception as exc:
        checks['database'] = f'error: {exc}'

    try:
        cache.set('health_check_probe', '1', timeout=5)
        checks['cache'] = 'ok' if cache.get('health_check_probe') == '1' else 'error'
    except Exception as exc:
        checks['cache'] = f'error: {exc}'

    healthy = all(v == 'ok' for v in checks.values())
    return Response({'status': 'ok' if healthy else 'degraded', 'checks': checks}, status=200 if healthy else 503)