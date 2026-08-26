from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from auth_module.permissions import IsAdminOrFleetManager, IsDriver
from fleet_monitoring.error_utils import validation_error_response
from fleet_monitoring.tracing import trace_span

from .serializers import TelemetryIngestSerializer, TelemetryLogSerializer
from .services import QueueUnavailable, TelemetryService

MAX_PACKET_SIZE_BYTES = 2048


class TelemetryIngestView(APIView):

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ingestion'

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated(), IsAdminOrFleetManager()]
        return [IsAuthenticated()]

    @extend_schema(
        request=TelemetryIngestSerializer,
        responses={
            202: 'Accepted (queued)',
            422: 'Unprocessable Entity',
            503: 'Service Unavailable',
        },
        summary='Ingest a telemetry packet',
        description='Validates a packet and publishes it to RabbitMQ for async processing',
    )
    def post(self, request):
        with trace_span('api.telemetry_ingest'):
            if len(request.body) > MAX_PACKET_SIZE_BYTES:
                return Response(
                    {'detail': f'Packet exceeds maximum size of {MAX_PACKET_SIZE_BYTES} bytes'},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

            serializer = TelemetryIngestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

            try:
                dispatch_id = TelemetryService.dispatch_packet(request.user, serializer.validated_data)
            except ValidationError as exc:
                return validation_error_response(exc, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
            except PermissionDenied as exc:
                return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
            except QueueUnavailable:
                return Response(
                    {'detail': 'Queue temporarily unavailable, please retry'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    headers={'Retry-After': '5'},
                )

            return Response({'dispatch_id': dispatch_id}, status=status.HTTP_202_ACCEPTED)

    @extend_schema(
        responses={200: TelemetryLogSerializer(many=True)},
        summary='List telemetry logs',
        description='Admin sees all; Fleet Manager sees telemetry for assigned vehicles',
    )
    def get(self, request):
        vehicle_id = request.query_params.get('vehicle_id')
        logs = TelemetryService.list_telemetry(request.user, vehicle_id=vehicle_id)
        return Response(TelemetryLogSerializer(logs, many=True).data, status=status.HTTP_200_OK)


class TelemetryMeView(APIView):

    permission_classes = [IsAuthenticated, IsDriver]

    @extend_schema(
        responses={200: TelemetryLogSerializer(many=True)},
        summary="Get the driver's own vehicle telemetry",
    )
    def get(self, request):
        logs = TelemetryService.list_telemetry_for_driver(request.user)
        return Response(TelemetryLogSerializer(logs, many=True).data, status=status.HTTP_200_OK)