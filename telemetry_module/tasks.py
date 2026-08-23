import logging

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, connections
from django.utils import timezone

from fleet_monitoring.dead_letter import publish_to_dead_letter
from fleet_monitoring.middleware import reset_correlation_id, set_correlation_id

from .services import TelemetryService

logger = logging.getLogger('audit')


@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=5,
    retry_backoff=True,
    retry_backoff_max=300,
    queue='telemetry.raw.process',
)
def process_telemetry_packet(self, packet_data):
    packet_data = dict(packet_data)
    correlation_id = packet_data.pop('correlation_id', '-')
    token = set_correlation_id(correlation_id)

    try:
        TelemetryService.persist_packet(packet_data)
    except DatabaseError as exc:
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            publish_to_dead_letter(
                source_queue='telemetry.raw.process',
                task_name=self.name,
                payload=packet_data,
                reason=f'Retries exhausted: {exc}',
            )
            raise
    finally:
        reset_correlation_id(token)


@shared_task(queue='telemetry.raw.process')
def cleanup_old_telemetry():
    from datetime import timedelta

    from .models import TelemetryLog

    cutoff = timezone.now() - timedelta(days=settings.TELEMETRY_RETENTION_DAYS)
    deleted_count, _ = TelemetryLog.objects.filter(timestamp__lt=cutoff).delete()

    logger.info(
        'telemetry_retention_cleanup',
        extra={'actor': 'scheduler', 'action': 'cleanup_old_telemetry', 'target': str(deleted_count)},
    )
    return deleted_count


@shared_task(queue='telemetry.raw.process')
def system_health_check():
    health = {'database': False, 'cache': False}

    try:
        connections['default'].cursor().execute('SELECT 1')
        health['database'] = True
    except Exception:
        logger.exception('health_check_database_failed', extra={'actor': 'scheduler', 'action': 'health_check'})

    try:
        cache.set('fleet:system:health:heartbeat', timezone.now().isoformat(), timeout=600)
        health['cache'] = bool(cache.get('fleet:system:health:heartbeat'))
    except Exception:
        logger.exception('health_check_cache_failed', extra={'actor': 'scheduler', 'action': 'health_check'})

    logger.info(
        'system_health_check',
        extra={'actor': 'scheduler', 'action': 'health_check', 'target': str(health)},
    )
    return health