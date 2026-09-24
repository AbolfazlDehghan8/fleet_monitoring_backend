import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import APIException, PermissionDenied

from fleet_monitoring.tracing import trace_span
from vehicles_module.models import Vehicle
from vehicles_module.services import VehicleService

from .models import TelemetryLog

audit_logger = logging.getLogger('audit')
degradation_logger = logging.getLogger('fleet_monitoring.cache_degradation')

TELEMETRY_CACHE_KEY = 'fleet:vehicle:{id}:telemetry'

INSERT_SQL = '''
INSERT INTO telemetry_logs
    (vehicle_id, obu_serial, "timestamp", speed, engine_temperature, battery_voltage,
     fuel_level, latitude, longitude, odometer, raw_payload, received_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
ON CONFLICT (vehicle_id, "timestamp") DO NOTHING
RETURNING id
'''


class QueueUnavailable(APIException):
    status_code = 503
    default_detail = 'Queue temporarily unavailable, please retry'
    default_code = 'queue_unavailable'
    wait = 5


class PacketRejected(Exception):
    pass


class VehicleNotFound(PacketRejected):
    pass


class TelemetryService:

    @staticmethod
    def _check_scope(actor, target):
        if actor.is_admin:
            return
        if actor.is_fleet_manager:
            if target['assigned_manager_id'] != actor.id:
                raise PermissionDenied('This vehicle is not assigned to you')
            return
        if actor.is_driver:
            if target['driver_user_id'] != actor.id or not target['driver_active']:
                raise PermissionDenied('This vehicle is not assigned to you')
            return
        raise PermissionDenied('Unknown role')

    @staticmethod
    def dispatch_packet(actor, validated_data):
        target = VehicleService.get_ingest_target(validated_data['vehicle_id'])
        if target is None:
            raise ValidationError({'vehicle_id': 'No vehicle found with this vehicle_id'})

        TelemetryService._check_scope(actor, target)

        if target['status'] == Vehicle.Status.DECOMMISSIONED:
            raise ValidationError({'vehicle_id': 'Vehicle is decommissioned and no longer accepts telemetry'})
        if target['obu_serial'] and target['obu_serial'] != validated_data['obu_serial']:
            raise ValidationError({'obu_serial': 'OBU serial does not match the OBU registered for this vehicle'})

        from fleet_monitoring.middleware import get_correlation_id

        from .tasks import process_telemetry_packet

        packet = dict(validated_data)
        packet['timestamp'] = packet['timestamp'].isoformat()
        packet['correlation_id'] = get_correlation_id()

        with trace_span('queue.dispatch_telemetry', vehicle_id=validated_data['vehicle_id']):
            try:
                result = process_telemetry_packet.apply_async(
                    args=[packet], queue='telemetry.raw.process',
                )
            except Exception:
                degradation_logger.exception(
                    'telemetry_queue_publish_failed',
                    extra={'actor': 'api', 'action': 'dispatch_packet', 'target': validated_data['vehicle_id']},
                )
                raise QueueUnavailable()

        return result.id

    @staticmethod
    def persist_packet(packet_data):
        target = VehicleService.get_ingest_target(packet_data['vehicle_id'])
        if target is None:
            raise VehicleNotFound(f"No vehicle found with vehicle_id {packet_data['vehicle_id']!r}")

        timestamp = packet_data['timestamp']
        if isinstance(timestamp, str):
            timestamp = parse_datetime(timestamp)
        if timestamp is None or timezone.is_naive(timestamp):
            raise PacketRejected('Packet timestamp is missing, malformed or has no timezone')

        received_at = timezone.now()
        with trace_span('db.persist_telemetry', vehicle_id=packet_data['vehicle_id']):
            with connection.cursor() as cursor:
                cursor.execute(INSERT_SQL, [
                    target['pk'], packet_data['obu_serial'], timestamp,
                    packet_data['speed'], packet_data['engine_temperature'], packet_data['battery_voltage'],
                    packet_data['fuel_level'], packet_data['latitude'], packet_data['longitude'],
                    packet_data['odometer'],
                    json.dumps(packet_data, allow_nan=False, default=str), received_at,
                ])
                row = cursor.fetchone()

        if row is None:
            audit_logger.info(
                'telemetry_duplicate_ignored',
                extra={'actor': 'obu', 'action': 'ingest_duplicate', 'target': packet_data['vehicle_id']},
            )
            return None

        log = TelemetryLog(
            id=row[0], vehicle_id=target['pk'], obu_serial=packet_data['obu_serial'], timestamp=timestamp,
            speed=packet_data['speed'], engine_temperature=packet_data['engine_temperature'],
            battery_voltage=packet_data['battery_voltage'], fuel_level=packet_data['fuel_level'],
            latitude=packet_data['latitude'], longitude=packet_data['longitude'],
            odometer=packet_data['odometer'], raw_payload=packet_data, received_at=received_at,
        )

        TelemetryService._update_live_cache(target, packet_data, timestamp)

        audit_logger.info(
            'telemetry_ingested',
            extra={'actor': 'obu', 'action': 'ingest', 'target': packet_data['vehicle_id']},
        )

        TelemetryService._evaluate_rules(log, packet_data['vehicle_id'])
        return log

    @staticmethod
    def _update_live_cache(target, packet_data, timestamp):
        key = TELEMETRY_CACHE_KEY.format(id=target['pk'])
        try:
            current = cache.get(key)
            if current and current.get('last_seen'):
                last_seen = parse_datetime(current['last_seen'])
                if last_seen is not None and last_seen >= timestamp:
                    return
            cache.set(
                key,
                {
                    'vehicle_id': packet_data['vehicle_id'],
                    'status': target['status'],
                    'speed': packet_data['speed'],
                    'engine_temperature': packet_data['engine_temperature'],
                    'battery_voltage': packet_data['battery_voltage'],
                    'fuel_level': packet_data['fuel_level'],
                    'latitude': packet_data['latitude'],
                    'longitude': packet_data['longitude'],
                    'odometer': packet_data['odometer'],
                    'last_seen': timestamp.isoformat(),
                },
                timeout=settings.TELEMETRY_CACHE_TTL_SECONDS,
            )
        except Exception:
            degradation_logger.warning(
                'telemetry_cache_update_failed',
                extra={'actor': 'worker', 'action': 'cache_set_telemetry', 'target': packet_data['vehicle_id']},
                exc_info=True,
            )

    @staticmethod
    def _evaluate_rules(log, vehicle_public_id):
        from rules_module.services import RuleService
        try:
            RuleService.evaluate(log, vehicle_public_id=vehicle_public_id)
        except Exception:
            audit_logger.exception(
                'rule_evaluation_failed',
                extra={'actor': 'rule_engine', 'action': 'evaluate', 'target': log.vehicle_id},
            )

    @staticmethod
    def list_telemetry(user, vehicle_id=None, start=None, end=None, limit=500):
        if user.is_admin:
            queryset = TelemetryLog.objects.all()
        elif user.is_fleet_manager:
            vehicle_pks = list(Vehicle.objects.filter(assigned_manager=user).values_list('id', flat=True))
            queryset = TelemetryLog.objects.filter(vehicle_id__in=vehicle_pks)
        else:
            queryset = TelemetryLog.objects.none()

        if vehicle_id:
            queryset = queryset.filter(vehicle__vehicle_id=vehicle_id)
        if start:
            queryset = queryset.filter(timestamp__gte=start)
        if end:
            queryset = queryset.filter(timestamp__lte=end)

        return queryset.select_related('vehicle').order_by('-timestamp', '-id')[:limit]

    @staticmethod
    def list_telemetry_for_driver(user, limit=500):
        driver_profile = getattr(user, 'driver_profile', None)
        if driver_profile is None or not driver_profile.is_active:
            return TelemetryLog.objects.none()
        vehicle_pks = list(driver_profile.vehicles.values_list('id', flat=True))
        return (
            TelemetryLog.objects.filter(vehicle_id__in=vehicle_pks)
            .select_related('vehicle').order_by('-timestamp', '-id')[:limit]
        )