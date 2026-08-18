from django.urls import path

from .views import FleetSummaryReportView

urlpatterns = [
    path('fleet-summary/', FleetSummaryReportView.as_view(), name='report-fleet-summary'),
]
