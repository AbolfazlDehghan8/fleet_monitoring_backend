from celery import shared_task
from django.db import DatabaseError

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
    try:
        TelemetryService.persist_packet(packet_data)
    except DatabaseError as exc:
        raise self.retry(exc=exc)