from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auth_module.permissions import IsAdminOrFleetManager

from .serializers import ReportQuerySerializer
from .services import ReportService


class FleetSummaryReportView(APIView):

    permission_classes = [IsAuthenticated, IsAdminOrFleetManager]

    @extend_schema(
        responses={200: 'Fleet summary report', 400: 'Bad Request'},
        summary='Generate a fleet summary report',
        description='Aggregates vehicle status, telemetry, and alert data over a date range',
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