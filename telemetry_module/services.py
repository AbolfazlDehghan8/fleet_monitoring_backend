import logging

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from rest_framework.exceptions import PermissionDenied

from vehicles_module.models import Vehicle

from .models import TelemetryLog

audit_logger = logging.getLogger('audit')


class QueueUnavailable(Exception):
    pass


class TelemetryService:

    @staticmethod
    def _check_scope(actor, vehicle):
        if actor.role == 'admin':
            return
        if actor.role == 'fleet_manager':
            if vehicle.assigned_manager_id != actor.id:
                raise PermissionDenied('This vehicle is not assigned to you')
            return
        if actor.role == 'driver':
            driver_profile = getattr(actor, 'driver_profile', None)
            if driver_profile is None or vehicle.driver_id != driver_profile.id:
                raise PermissionDenied('This vehicle is not assigned to you')
            return
        raise PermissionDenied('Unknown role')

    @staticmethod
    def dispatch_packet(actor, validated_data):
        try:
            vehicle = Vehicle.objects.get(vehicle_id=validated_data['vehicle_id'])
        except Vehicle.DoesNotExist:
            raise ValidationError({'vehicle_id': 'No vehicle found with this vehicle_id'})

        TelemetryService._check_scope(actor, vehicle)

        from .tasks import process_telemetry_packet

        packet = dict(validated_data)
        packet['timestamp'] = packet['timestamp'].isoformat()

        try:
            result = process_telemetry_packet.apply_async(
                args=[packet], queue='telemetry.raw.process',
            )
        except Exception as exc:
            raise QueueUnavailable(str(exc))

        return result.id

    @staticmethod
    def persist_packet(packet_data):
        vehicle = Vehicle.objects.get(vehicle_id=packet_data['vehicle_id'])

        log = TelemetryLog(
            vehicle=vehicle,
            obu_serial=packet_data['obu_serial'],
            timestamp=packet_data['timestamp'],
            speed=packet_data['speed'],
            engine_temperature=packet_data['engine_temperature'],
            battery_voltage=packet_data['battery_voltage'],
            fuel_level=packet_data['fuel_level'],
            latitude=packet_data['latitude'],
            longitude=packet_data['longitude'],
            odometer=packet_data['odometer'],
            raw_payload=packet_data,
        )

        try:
            with transaction.atomic():
                log.save()
        except IntegrityError:
            audit_logger.info(
                'telemetry_duplicate_ignored',
                extra={'actor': 'obu', 'action': 'ingest_duplicate', 'target': vehicle.vehicle_id},
            )
            return

        cache.set(
            f'fleet:vehicle:{vehicle.id}:telemetry',
            {
                'vehicle_id': vehicle.vehicle_id,
                'status': vehicle.status,
                'speed': packet_data['speed'],
                'engine_temperature': packet_data['engine_temperature'],
                'battery_voltage': packet_data['battery_voltage'],
                'fuel_level': packet_data['fuel_level'],
                'latitude': packet_data['latitude'],
                'longitude': packet_data['longitude'],
                'odometer': packet_data['odometer'],
                'last_seen': packet_data['timestamp'],
            },
            timeout=None,
        )

        audit_logger.info(
            'telemetry_ingested',
            extra={'actor': 'obu', 'action': 'ingest', 'target': vehicle.vehicle_id},
        )

    @staticmethod
    def list_telemetry(user, vehicle_id=None):
        if user.role == 'admin':
            queryset = TelemetryLog.objects.all()
        elif user.role == 'fleet_manager':
            queryset = TelemetryLog.objects.filter(vehicle__assigned_manager=user)
        else:
            queryset = TelemetryLog.objects.none()

        if vehicle_id:
            queryset = queryset.filter(vehicle__vehicle_id=vehicle_id)

        return queryset.select_related('vehicle')[:500]

    @staticmethod
    def list_telemetry_for_driver(user):
        driver_profile = getattr(user, 'driver_profile', None)
        if driver_profile is None:
            return TelemetryLog.objects.none()
        return TelemetryLog.objects.filter(vehicle__driver=driver_profile).select_related('vehicle')[:500]