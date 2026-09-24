import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import RefreshToken

logger = logging.getLogger('audit')

BATCH_SIZE = 5000


@shared_task(queue='telemetry.raw.process')
def cleanup_expired_refresh_tokens(retention_days=1):
    cutoff = timezone.now() - timedelta(days=retention_days)
    total = 0
    while True:
        ids = list(
            RefreshToken.objects.filter(expires_at__lt=cutoff).values_list('pk', flat=True)[:BATCH_SIZE]
        )
        if not ids:
            break
        deleted, _ = RefreshToken.objects.filter(pk__in=ids).delete()
        total += deleted

    logger.info(
        'expired_refresh_tokens_cleaned',
        extra={'actor': 'system', 'action': 'cleanup_refresh_tokens', 'target': total},
    )
    return total