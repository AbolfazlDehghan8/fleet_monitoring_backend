from django.urls import path

from .views import TelemetryIngestView, TelemetryMeView

urlpatterns = [
    path('', TelemetryIngestView.as_view(), name='telemetry-ingest-list'),
    path('me/', TelemetryMeView.as_view(), name='telemetry-me'),
]