from celery import shared_task
from django.db import DatabaseError

from fleet_monitoring.middleware import reset_correlation_id, set_correlation_id

from .services import TelemetryService


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
        raise self.retry(exc=exc)
    finally:
        reset_correlation_id(token)