from django.urls import path

from .views import (
    FleetSummaryReportView,
    ReportDetailView,
    ReportExportView,
    ReportGenerateView,
    ReportListView,
)

urlpatterns = [
    path('fleet-summary/', FleetSummaryReportView.as_view(), name='report-fleet-summary'),
    path('generate/', ReportGenerateView.as_view(), name='report-generate'),
    path('', ReportListView.as_view(), name='report-list'),
    path('<int:report_id>/', ReportDetailView.as_view(), name='report-detail'),
    path('<int:report_id>/export/', ReportExportView.as_view(), name='report-export'),
]