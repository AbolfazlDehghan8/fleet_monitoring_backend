import logging

from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, models, transaction
from django.utils import timezone as django_timezone

from auth_module.models import User

from .models import OBU, Company, Driver, Vehicle

audit_logger = logging.getLogger('audit')
degradation_logger = logging.getLogger('fleet_monitoring.cache_degradation')

VEHICLE_STATUS_CACHE_KEY = 'fleet:vehicle:{id}:status'
VEHICLE_STATUS_CACHE_TTL_SECONDS = 60

VEHICLE_TELEMETRY_CACHE_KEY = 'fleet:vehicle:{id}:telemetry'

DASHBOARD_STATS_CACHE_KEY = 'fleet:dashboard:stats'
DASHBOARD_STATS_CACHE_TTL_SECONDS = 30


def _not_found(detail='Vehicle not found'):
    raise ValidationError({'detail': detail})


def _safe_cache_get(key, action):
    try:
        return cache.get(key)
    except Exception:
        degradation_logger.warning(
            'cache_read_failed',
            extra={'actor': 'api', 'action': action, 'target': key},
            exc_info=True,
        )
        return None


def _safe_cache_set(key, value, timeout, action):
    try:
        cache.set(key, value, timeout=timeout)
    except Exception:
        degradation_logger.warning(
            'cache_write_failed',
            extra={'actor': 'api', 'action': action, 'target': key},
            exc_info=True,
        )


def _safe_cache_delete(key, action):
    try:
        cache.delete(key)
    except Exception:
        degradation_logger.warning(
            'cache_delete_failed',
            extra={'actor': 'api', 'action': action, 'target': key},
            exc_info=True,
        )


class VehicleService:

    @staticmethod
    def list_vehicles(user):
        queryset = Vehicle.objects.select_related('driver__user', 'assigned_manager', 'obu')
        if user.is_admin:
            return queryset
        if user.is_fleet_manager:
            return queryset.filter(assigned_manager=user)
        raise PermissionDenied('Drivers must use /api/v1/vehicles/me/')

    @staticmethod
    def get_vehicle_for_user(user, vehicle_id):
        try:
            vehicle = Vehicle.objects.select_related('driver__user', 'assigned_manager', 'obu').get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            _not_found()
            return

        if user.is_admin:
            return vehicle
        if user.is_fleet_manager and vehicle.assigned_manager_id == user.id:
            return vehicle
        if user.is_driver and vehicle.driver_id and vehicle.driver.user_id == user.id:
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

        if actor.is_fleet_manager:
            data['assigned_manager'] = actor

        data['company'] = CompanyService.get_company()

        try:
            with transaction.atomic():
                vehicle = Vehicle(**data)
                vehicle.full_clean()
                vehicle.save()

                if obu_serial:
                    obu = OBU(vehicle=vehicle, serial_number=obu_serial, firmware_version=obu_firmware)
                    obu.full_clean()
                    obu.save()
        except IntegrityError as exc:
            raise _integrity_error_to_validation(exc)

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

        if actor.is_fleet_manager:
            data.pop('assigned_manager', None)

        for field, value in data.items():
            setattr(vehicle, field, value)

        try:
            with transaction.atomic():
                vehicle.full_clean()
                vehicle.save()

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
        except IntegrityError as exc:
            raise _integrity_error_to_validation(exc)

        VehicleService._invalidate_status_cache(vehicle.id)
        audit_logger.info(
            'vehicle_updated', extra={'actor': actor.id, 'action': 'update_vehicle', 'target': vehicle.id}
        )
        return vehicle

    @staticmethod
    def delete_vehicle(actor, vehicle_id):
        if not actor.is_admin:
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
        cached = _safe_cache_get(cache_key, 'get_vehicle_status')
        if cached is None:
            cached = {
                'vehicle_id': vehicle.id,
                'vehicle_identifier': vehicle.vehicle_id,
                'status': vehicle.status,
                'updated_at': vehicle.updated_at.isoformat(),
            }
            _safe_cache_set(cache_key, cached, VEHICLE_STATUS_CACHE_TTL_SECONDS, 'get_vehicle_status')

        payload = dict(cached)
        live_telemetry = _safe_cache_get(
            VEHICLE_TELEMETRY_CACHE_KEY.format(id=vehicle.id), 'get_vehicle_status_live_telemetry'
        )
        if live_telemetry:
            payload['live_telemetry'] = live_telemetry
        return payload

    @staticmethod
    def _invalidate_status_cache(vehicle_id):
        _safe_cache_delete(VEHICLE_STATUS_CACHE_KEY.format(id=vehicle_id), 'invalidate_status_cache')
        _safe_cache_delete(DASHBOARD_STATS_CACHE_KEY, 'invalidate_status_cache')

    @staticmethod
    def get_dashboard_stats(user):
        if not (user.is_admin or user.is_fleet_manager):
            raise PermissionDenied('Only admin and fleet_manager may view dashboard stats')

        cache_key = DASHBOARD_STATS_CACHE_KEY if user.is_admin else f'{DASHBOARD_STATS_CACHE_KEY}:{user.id}'
        cached = _safe_cache_get(cache_key, 'get_dashboard_stats')
        if cached is not None:
            return cached

        queryset = Vehicle.objects.all() if user.is_admin else Vehicle.objects.filter(assigned_manager=user)

        from alerts_module.models import Alert
        alerts_qs = Alert.objects.filter(acknowledged=False)
        if not user.is_admin:
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
        _safe_cache_set(cache_key, payload, DASHBOARD_STATS_CACHE_TTL_SECONDS, 'get_dashboard_stats')
        return payload


class DriverService:

    @staticmethod
    def list_drivers(user):
        queryset = Driver.objects.select_related('user')
        if user.is_admin:
            return queryset
        if user.is_fleet_manager:
            return queryset.filter(vehicles__assigned_manager=user).distinct()
        raise PermissionDenied('Drivers do not have access to the drivers list')

    @staticmethod
    def get_driver(user, driver_id):
        try:
            return DriverService.list_drivers(user).get(id=driver_id)
        except Driver.DoesNotExist:
            _not_found('Driver not found')

    @staticmethod
    def list_linkable_users(user):
        if not (user.is_admin or user.is_fleet_manager):
            raise PermissionDenied('Only admin and fleet_manager may browse driver-role users')
        return User.objects.filter(
            role=User.Role.DRIVER, driver_profile__isnull=True
        ).order_by('username')

    @staticmethod
    def list_assignable(user):
        queryset = Driver.objects.select_related('user')
        if user.is_admin:
            return queryset
        if user.is_fleet_manager:
            return queryset.filter(
                models.Q(vehicles__assigned_manager=user) | models.Q(vehicles__isnull=True)
            ).distinct()
        raise PermissionDenied('Drivers do not have access to the drivers list')

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
        if not actor.is_admin:
            raise PermissionDenied('Only admin can delete driver profiles')

        deleted, _ = Driver.objects.filter(id=driver_id).delete()
        if not deleted:
            _not_found('Driver not found')

        audit_logger.info(
            'driver_deleted', extra={'actor': actor.id, 'action': 'delete_driver', 'target': driver_id}
        )

class CompanyService:

    @staticmethod
    def get_company():
        company = Company.objects.first()
        if company is None:
            raise ValidationError({'detail': 'Company not found'})
        return company

    @staticmethod
    def update_company(actor, data):
        if not actor.is_admin:
            raise PermissionDenied('Only admin can update company information')

        company = CompanyService.get_company()

        for field, value in data.items():
            setattr(company, field, value)

        try:
            company.full_clean()
            company.save()
        except IntegrityError as exc:
            raise _integrity_error_to_validation(exc)

        audit_logger.info(
            'company_updated', extra={'actor': actor.id, 'action': 'update_company', 'target': company.id}
        )
        return company


def _integrity_error_to_validation(exc):
    message = str(exc).lower()
    for field in ('license_plate', 'vin', 'vehicle_id', 'serial_number', 'license_number'):
        if field in message:
            return ValidationError({field: f'{field} already exists'})
    return ValidationError({'detail': 'Could not save record due to a conflicting record'})