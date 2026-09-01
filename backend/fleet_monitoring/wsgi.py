"""
WSGI config for fleet_monitoring project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fleet_monitoring.settings')

from fleet_monitoring.otel import setup_tracing

setup_tracing(service_name=os.getenv('OTEL_SERVICE_NAME', 'fleet-monitoring-api'))

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()