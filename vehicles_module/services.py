import logging

from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, models
from django.utils import timezone as django_timezone

from .models import OBU, Driver, Vehicle

audit_logger = logging.getLogger('audit')

VEHICLE_STATUS_CACHE_KEY = 'fleet:vehicle:{id}:status'
VEHICLE_STATUS_CACHE_TTL_SECONDS = 60

VEHICLE_TELEMETRY_CACHE_KEY = 'fleet:vehicle:{id}:telemetry'

DASHBOARD_STATS_CACHE_KEY = 'fleet:dashboard:stats'
DASHBOARD_STATS_CACHE_TTL_SECONDS = 30


def _not_found(detail='Vehicle not found'):
    raise ValidationError({'detail': detail})


class VehicleService:

    @staticmethod
    def list_vehicles(user):
        queryset = Vehicle.objects.select_related('driver__user', 'assigned_manager', 'obu')
        if user.role == 'admin':
            return queryset
        if user.role == 'fleet_manager':
            return queryset.filter(assigned_manager=user)
        raise PermissionDenied('Drivers must use /api/v1/vehicles/me/')

    @staticmethod
    def get_vehicle_for_user(user, vehicle_id):
        try:
            vehicle = Vehicle.objects.select_related('driver__user', 'assigned_manager', 'obu').get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            _not_found()
            return

        if user.role == 'admin':
            return vehicle
        if user.role == 'fleet_manager' and vehicle.assigned_manager_id == user.id:
            return vehicle
        if user.role == 'driver' and vehicle.driver_id and vehicle.driver.user_id == user.id:
            return vehicle

        raise PermissionDenied('You do not have access to this vehicle')

    @staticmethod
    def get_vehicles_for_driver(user):
        try:
            driver = Driver.objects.get(user=user)
        except Driver.DoesNotExist:
            return Vehicle.objects.none()
        return Vehicle.objects.filter(driver=driver).select_related('assigned_manager', 'obu')


    @staticmethod
    def create_vehicle(actor, data):
        data = dict(data)
        obu_serial = data.pop('obu_serial_number', None)
        obu_firmware = data.pop('obu_firmware_version', '')

        if actor.role == 'fleet_manager':
            data['assigned_manager'] = actor

        vehicle = Vehicle(**data)
        try:
            vehicle.full_clean()
            vehicle.save()
        except IntegrityError as exc:
            raise _integrity_error_to_validation(exc)

        if obu_serial:
            obu = OBU(vehicle=vehicle, serial_number=obu_serial, firmware_version=obu_firmware)
            obu.full_clean()
            obu.save()

        audit_logger.info(
            'vehicle_created', extra={'actor': actor.id, 'action': 'create_vehicle', 'target': vehicle.id}
        )
        return vehicle

    @staticmethod
    def update_vehicle(actor, vehicle_id, data):
        vehicle = VehicleService.get_vehicle_for_user(actor, vehicle_id)

        data = dict(data)
        obu_serial = data.pop('obu_serial_number', None)
        obu_firmware = data.pop('obu_firmware_version', None)

        if actor.role == 'fleet_manager':
            data.pop('assigned_manager', None)

        for field, value in data.items():
            setattr(vehicle, field, value)

        try:
            vehicle.full_clean()
            vehicle.save()
        except IntegrityError as exc:
            raise _integrity_error_to_validation(exc)

        if obu_serial is not None or obu_firmware is not None:
            obu = getattr(vehicle, 'obu', None)
            if obu is None:
                obu = OBU(vehicle=vehicle, serial_number=obu_serial or '')
            if obu_serial is not None:
                obu.serial_number = obu_serial
            if obu_firmware is not None:
                obu.firmware_version = obu_firmware
            obu.full_clean()
            obu.save()

        VehicleService._invalidate_status_cache(vehicle.id)
        audit_logger.info(
            'vehicle_updated', extra={'actor': actor.id, 'action': 'update_vehicle', 'target': vehicle.id}
        )
        return vehicle

    @staticmethod
    def delete_vehicle(actor, vehicle_id):
        if actor.role != 'admin':
            raise PermissionDenied('Only admin can delete vehicles')

        deleted, _ = Vehicle.objects.filter(id=vehicle_id).delete()
        if not deleted:
            _not_found()

        VehicleService._invalidate_status_cache(vehicle_id)
        audit_logger.info(
            'vehicle_deleted', extra={'actor': actor.id, 'action': 'delete_vehicle', 'target': vehicle_id}
        )


    @staticmethod
    def get_vehicle_status(user, vehicle_id):
        vehicle = VehicleService.get_vehicle_for_user(user, vehicle_id)
        cache_key = VEHICLE_STATUS_CACHE_KEY.format(id=vehicle.id)
        cached = cache.get(cache_key)
        if cached is None:
            cached = {
                'vehicle_id': vehicle.id,
                'vehicle_identifier': vehicle.vehicle_id,
                'status': vehicle.status,
                'updated_at': vehicle.updated_at.isoformat(),
            }
            cache.set(cache_key, cached, timeout=VEHICLE_STATUS_CACHE_TTL_SECONDS)

        payload = dict(cached)
        live_telemetry = cache.get(VEHICLE_TELEMETRY_CACHE_KEY.format(id=vehicle.id))
        if live_telemetry:
            payload['live_telemetry'] = live_telemetry
        return payload

    @staticmethod
    def _invalidate_status_cache(vehicle_id):
        cache.delete(VEHICLE_STATUS_CACHE_KEY.format(id=vehicle_id))
        cache.delete(DASHBOARD_STATS_CACHE_KEY)

    @staticmethod
    def get_dashboard_stats(user):
        if user.role not in ('admin', 'fleet_manager'):
            raise PermissionDenied('Only admin and fleet_manager may view dashboard stats')

        cache_key = DASHBOARD_STATS_CACHE_KEY if user.role == 'admin' else f'{DASHBOARD_STATS_CACHE_KEY}:{user.id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        queryset = Vehicle.objects.all() if user.role == 'admin' else Vehicle.objects.filter(assigned_manager=user)

        from alerts_module.models import Alert
        alerts_qs = Alert.objects.filter(acknowledged=False)
        if user.role != 'admin':
            alerts_qs = alerts_qs.filter(vehicle__assigned_manager=user)

        by_status = {choice.value: 0 for choice in Vehicle.Status}
        for row in queryset.values('status').annotate(count=models.Count('id')):
            by_status[row['status']] = row['count']

        payload = {
            'total_vehicles': queryset.count(),
            'vehicles_by_status': by_status,
            'unacknowledged_alerts': alerts_qs.count(),
            'generated_at': django_timezone.now().isoformat(),
        }
        cache.set(cache_key, payload, timeout=DASHBOARD_STATS_CACHE_TTL_SECONDS)
        return payload


class DriverService:

    @staticmethod
    def list_drivers(user):
        queryset = Driver.objects.select_related('user')
        if user.role == 'admin':
            return queryset
        if user.role == 'fleet_manager':
            return queryset.filter(vehicles__assigned_manager=user).distinct()
        raise PermissionDenied('Drivers do not have access to the drivers list')

    @staticmethod
    def get_driver(user, driver_id):
        try:
            return DriverService.list_drivers(user).get(id=driver_id)
        except Driver.DoesNotExist:
            _not_found('Driver not found')

    @staticmethod
    def create_driver(actor, data):
        driver = Driver(**data)
        try:
            driver.full_clean()
            driver.save()
        except IntegrityError as exc:
            raise _integrity_error_to_validation(exc)

        audit_logger.info(
            'driver_created', extra={'actor': actor.id, 'action': 'create_driver', 'target': driver.id}
        )
        return driver

    @staticmethod
    def update_driver(actor, driver_id, data):
        driver = DriverService.get_driver(actor, driver_id)
        for field, value in data.items():
            setattr(driver, field, value)

        try:
            driver.full_clean()
            driver.save()
        except IntegrityError as exc:
            raise _integrity_error_to_validation(exc)

        audit_logger.info(
            'driver_updated', extra={'actor': actor.id, 'action': 'update_driver', 'target': driver.id}
        )
        return driver

    @staticmethod
    def delete_driver(actor, driver_id):
        if actor.role != 'admin':
            raise PermissionDenied('Only admin can delete driver profiles')

        deleted, _ = Driver.objects.filter(id=driver_id).delete()
        if not deleted:
            _not_found('Driver not found')

        audit_logger.info(
            'driver_deleted', extra={'actor': actor.id, 'action': 'delete_driver', 'target': driver_id}
        )


def _integrity_error_to_validation(exc):
    message = str(exc).lower()
    for field in ('license_plate', 'vin', 'vehicle_id', 'serial_number', 'license_number'):
        if field in message:
            return ValidationError({field: f'{field} already exists'})
    return ValidationError({'detail': 'Could not save record due to a conflicting record'})