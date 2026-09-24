from django.core.exceptions import ValidationError
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from auth_module.permissions import IsAdminOrFleetManager, IsDriver

from .serializers import (
    TelemetryIngestSerializer,
    TelemetryLogSerializer,
    TelemetryQuerySerializer,
)
from .services import TelemetryService

MAX_PACKET_BYTES = 2048


def _unprocessable(errors):
    return Response(errors, status=status.HTTP_422_UNPROCESSABLE_ENTITY)


class TelemetryIngestView(APIView):

    permission_classes = [IsAuthenticated]
    throttle_scope = 'ingestion'

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticated(), IsAdminOrFleetManager()]
        return [IsAuthenticated()]

    def get_throttles(self):
        if self.request.method == 'POST':
            return [ScopedRateThrottle()]
        return [UserRateThrottle()]

    @extend_schema(
        request=TelemetryIngestSerializer,
        responses={202: 'Accepted', 403: 'Forbidden', 422: 'Unprocessable Entity', 503: 'Queue unavailable'},
        summary='Ingest a telemetry packet',
        description=(
            'Validates the packet and queues it for asynchronous processing. Returns 202 as soon '
            'as RabbitMQ has confirmed the message. Duplicate (vehicle_id, timestamp) packets are '
            'accepted and ignored by the worker, so OBUs can safely retry. 503 carries a '
            'Retry-After header.'
        ),
    )
    def post(self, request):
        declared = request.META.get('CONTENT_LENGTH', '')
        if declared.isdigit() and int(declared) > MAX_PACKET_BYTES:
            return _unprocessable({'detail': f'Packet exceeds the {MAX_PACKET_BYTES}-byte limit'})
        if len(request.body) > MAX_PACKET_BYTES:
            return _unprocessable({'detail': f'Packet exceeds the {MAX_PACKET_BYTES}-byte limit'})

        serializer = TelemetryIngestSerializer(data=request.data)
        if not serializer.is_valid():
            return _unprocessable(serializer.errors)

        try:
            dispatch_id = TelemetryService.dispatch_packet(request.user, serializer.validated_data)
        except ValidationError as exc:
            return _unprocessable(exc.message_dict if hasattr(exc, 'message_dict') else {'detail': exc.messages})

        return Response({'status': 'accepted', 'dispatch_id': dispatch_id}, status=status.HTTP_202_ACCEPTED)

    @extend_schema(
        parameters=[
            OpenApiParameter('vehicle_id', str, description='Filter by public vehicle_id'),
            OpenApiParameter('start', str, description='Only records at/after this ISO-8601 time'),
            OpenApiParameter('end', str, description='Only records at/before this ISO-8601 time'),
            OpenApiParameter('limit', int, description='Max records, 1-500 (default 500)'),
        ],
        responses={200: TelemetryLogSerializer(many=True)},
        summary='List recent telemetry (newest first)',
        description=(
            'Admin: all vehicles. Fleet Manager: vehicles assigned to them. Use `start`/`end` (and '
            '`vehicle_id`) to keep queries on a small number of monthly partitions.'
        ),
    )
    def get(self, request):
        query = TelemetryQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data

        logs = TelemetryService.list_telemetry(
            request.user,
            vehicle_id=params.get('vehicle_id'),
            start=params.get('start'),
            end=params.get('end'),
            limit=params['limit'],
        )
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