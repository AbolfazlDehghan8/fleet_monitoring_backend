import os

from celery import Celery
from celery.signals import beat_init, worker_process_init

from fleet_monitoring.otel import setup_tracing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fleet_monitoring.settings')

app = Celery('fleet_monitoring')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@worker_process_init.connect
def _init_worker_tracing(**kwargs):
    setup_tracing(service_name=os.getenv('OTEL_SERVICE_NAME', 'fleet-monitoring-worker'))


@beat_init.connect
def _init_beat_tracing(**kwargs):
    setup_tracing(service_name=os.getenv('OTEL_SERVICE_NAME', 'fleet-monitoring-beat'))