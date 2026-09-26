from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auth_module.permissions import IsAdminOrFleetManager

from .models import Report
from .serializers import ReportQuerySerializer, ReportSerializer
from .services import ReportService


class FleetSummaryReportView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrFleetManager]

    @extend_schema(
        responses={200: 'Fleet summary report', 400: 'Bad Request'},
        summary='Generate a fleet summary report',
        description=(
            'Aggregates vehicle status, telemetry, and alert data over a date range '
            f'(computed synchronously; window capped, see ReportQuerySerializer). '
            'For long-running or repeated reports, prefer POST /reports/generate/.'
        ),
    )
    def get(self, request):
        serializer = ReportQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        report = ReportService.generate_fleet_summary(
            request.user,
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            vehicle_id=data.get('vehicle_id'),
        )
        return Response(report, status=status.HTTP_200_OK)


class ReportGenerateView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrFleetManager]

    @extend_schema(
        request=ReportQuerySerializer,
        responses={202: ReportSerializer, 400: 'Bad Request'},
        summary='Request an async fleet summary report',
        description='Queues report generation and returns immediately; poll GET /reports/{id}/ for the result.',
    )
    def post(self, request):
        serializer = ReportQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        report = ReportService.create_pending_report(
            request.user,
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            vehicle_id=data.get('vehicle_id'),
        )
        ReportService.attach_sequence_number(request.user, report)
        return Response(ReportSerializer(report).data, status=status.HTTP_202_ACCEPTED)


class ReportListView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrFleetManager]

    @extend_schema(responses={200: ReportSerializer(many=True)}, summary='List generated reports')
    def get(self, request):
        reports = ReportService.list_reports(request.user)
        reports = ReportService.attach_sequence_numbers(request.user, reports)
        return Response(ReportSerializer(reports, many=True).data, status=status.HTTP_200_OK)


class ReportDetailView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrFleetManager]

    @extend_schema(
        responses={200: ReportSerializer, 403: 'Forbidden', 404: 'Not Found'},
        summary='Get report status/result',
    )
    def get(self, request, report_id):
        report = ReportService.get_report(request.user, report_id)
        ReportService.attach_sequence_number(request.user, report)
        return Response(ReportSerializer(report).data, status=status.HTTP_200_OK)

    @extend_schema(
        responses={204: None, 403: 'Forbidden', 404: 'Not Found'},
        summary='Delete a report',
        description=(
            'Admins may delete any report; fleet managers may only delete reports they '
            'requested themselves. Remaining reports are renumbered so sequence_number '
            'stays gap-free.'
        ),
    )
    def delete(self, request, report_id):
        ReportService.delete_report(request.user, report_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReportExportView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrFleetManager]

    @extend_schema(
        responses={200: 'CSV file', 400: 'Not ready', 403: 'Forbidden', 404: 'Not Found'},
        summary='Export a completed report as CSV',
    )
    def get(self, request, report_id):
        report = ReportService.get_report(request.user, report_id)

        if report.status != Report.Status.COMPLETED:
            return Response(
                {'detail': f'Report is not ready for export (status={report.status})'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ReportService.attach_sequence_number(request.user, report)
        csv_bytes = ReportService.to_csv(report)
        response = HttpResponse(csv_bytes, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="report-{report.sequence_number}.csv"'
        return response