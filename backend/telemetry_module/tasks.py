import logging
import random
import re
from datetime import datetime, timedelta, timezone as dt_timezone

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError, InterfaceError, OperationalError, connection, transaction
from django.utils import timezone

from fleet_monitoring.dead_letter import publish_to_dead_letter
from fleet_monitoring.middleware import reset_correlation_id, set_correlation_id
from fleet_monitoring.tracing import trace_span

from .services import TelemetryService

logger = logging.getLogger('audit')

TRANSIENT_ERRORS = (OperationalError, InterfaceError, SoftTimeLimitExceeded)

PARTITION_NAME_RE = re.compile(r'^telemetry_logs_(\d{4})_(\d{2})$')
DELETE_BATCH_SIZE = 10_000
MAX_DELETE_BATCHES_PER_RUN = 500


def _backoff_seconds(retries):
    return min(300, 5 * 2 ** retries) + random.uniform(0, 5)


def _dead_letter(task, packet_data, reason):
    publish_to_dead_letter(
        source_queue='telemetry.raw.process',
        task_name=task.name,
        payload={'packet_data': packet_data, 'retries': task.request.retries},
        reason=reason,
    )


@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=5,
    queue='telemetry.raw.process',
    ignore_result=True,
    soft_time_limit=20,
    time_limit=30,
)
def process_telemetry_packet(self, packet_data):
    packet_data = dict(packet_data)
    correlation_id = packet_data.pop('correlation_id', '-')
    token = set_correlation_id(correlation_id)

    try:
        with trace_span('worker.process_telemetry', vehicle_id=packet_data.get('vehicle_id')):
            TelemetryService.persist_packet(packet_data)

    except TRANSIENT_ERRORS as exc:
        if self.request.retries >= self.max_retries:
            logger.error(
                'telemetry_retries_exhausted',
                extra={'actor': 'worker', 'action': 'dead_letter', 'target': packet_data.get('vehicle_id')},
            )
            _dead_letter(self, packet_data, f'Retries exhausted: {exc!r}')
            raise
        raise self.retry(exc=exc, countdown=_backoff_seconds(self.request.retries))

    except Exception as exc:
        logger.exception(
            'telemetry_packet_rejected',
            extra={'actor': 'worker', 'action': 'dead_letter', 'target': packet_data.get('vehicle_id')},
        )
        _dead_letter(self, packet_data, f'Non-retryable error: {exc!r}')
        raise

    finally:
        reset_correlation_id(token)


def _list_partitions(cursor):
    cursor.execute("""
        SELECT c.relname
        FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid
        WHERE i.inhparent = 'telemetry_logs'::regclass
    """)
    return {row[0] for row in cursor.fetchall()}


def _month_bounds(year, month):
    start = datetime(year, month, 1, tzinfo=dt_timezone.utc)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=dt_timezone.utc)
    return start, end


def _drop_expired_partitions(cutoff):
    dropped = []
    with connection.cursor() as cursor:
        for name in sorted(_list_partitions(cursor)):
            match = PARTITION_NAME_RE.match(name)
            if not match:
                continue
            _, month_end = _month_bounds(int(match.group(1)), int(match.group(2)))
            if month_end > cutoff:
                continue
            try:
                with transaction.atomic():
                    cursor.execute("SET LOCAL lock_timeout = '5s'")
                    cursor.execute(
                        f'UPDATE alerts SET telemetry_log_id = NULL '
                        f'WHERE telemetry_log_id IN (SELECT id FROM "{name}")'
                    )
                    cursor.execute(f'DROP TABLE "{name}"')
                dropped.append(name)
            except DatabaseError:
                logger.exception(
                    'telemetry_partition_drop_failed',
                    extra={'actor': 'system', 'action': 'drop_partition', 'target': name},
                )
    return dropped


def _delete_expired_rows(cutoff):
    sql = '''
        WITH doomed AS (
            SELECT id, "timestamp" FROM telemetry_logs WHERE "timestamp" < %s LIMIT %s
        ), unlinked AS (
            UPDATE alerts SET telemetry_log_id = NULL WHERE telemetry_log_id IN (SELECT id FROM doomed)
        )
        DELETE FROM telemetry_logs t USING doomed d WHERE t.id = d.id AND t."timestamp" = d."timestamp"
    '''
    total = 0
    for _ in range(MAX_DELETE_BATCHES_PER_RUN):
        with connection.cursor() as cursor:
            cursor.execute(sql, [cutoff, DELETE_BATCH_SIZE])
            deleted = cursor.rowcount
        total += deleted
        if deleted < DELETE_BATCH_SIZE:
            break
    return total


@shared_task(queue='telemetry.raw.process', ignore_result=True, soft_time_limit=3300, time_limit=3600)
def cleanup_old_telemetry():
    cutoff = timezone.now() - timedelta(days=settings.TELEMETRY_RETENTION_DAYS)

    dropped = _drop_expired_partitions(cutoff)
    deleted = _delete_expired_rows(cutoff)

    logger.info(
        'telemetry_retention_cleanup',
        extra={
            'actor': 'system', 'action': 'cleanup_telemetry', 'target': deleted,
            'dropped_partitions': dropped, 'cutoff': cutoff.isoformat(),
        },
    )
    return deleted


@shared_task(queue='telemetry.raw.process', ignore_result=True, soft_time_limit=300, time_limit=360)
def ensure_future_telemetry_partitions(months_ahead=3):
    now = timezone.now()
    year, month = now.year, now.month
    ensured = []

    with connection.cursor() as cursor:
        existing = _list_partitions(cursor)

        for _ in range(months_ahead + 1):
            name = f'telemetry_logs_{year:04d}_{month:02d}'
            if name not in existing:
                start, end = _month_bounds(year, month)
                try:
                    with transaction.atomic():
                        cursor.execute(
                            f'CREATE TABLE IF NOT EXISTS "{name}" PARTITION OF telemetry_logs '
                            f'FOR VALUES FROM (%s) TO (%s)',
                            [start, end],
                        )
                except DatabaseError:
                    logger.exception(
                        'telemetry_partition_create_failed',
                        extra={'actor': 'system', 'action': 'ensure_partition', 'target': name},
                    )
                else:
                    ensured.append(name)
            else:
                ensured.append(name)
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)

        cursor.execute('SELECT EXISTS (SELECT 1 FROM telemetry_logs_default)')
        if cursor.fetchone()[0]:
            logger.warning(
                'telemetry_default_partition_has_rows',
                extra={'actor': 'system', 'action': 'ensure_partition', 'target': 'telemetry_logs_default'},
            )

    logger.info(
        'telemetry_partitions_ensured',
        extra={'actor': 'system', 'action': 'ensure_partition', 'target': len(ensured)},
    )
    return ensured


@shared_task(queue='telemetry.raw.process', ignore_result=True, soft_time_limit=30, time_limit=60)
def system_health_check():
    health = {'database': False, 'cache': False}

    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
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