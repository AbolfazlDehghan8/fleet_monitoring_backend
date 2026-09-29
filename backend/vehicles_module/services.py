import logging
import random

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.utils import timezone as django_timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from alerts_module.models import Alert
from auth_module.models import User
from fleet_monitoring.error_utils import integrity_error_to_validation

from .models import OBU, Company, Driver, Vehicle

audit_logger = logging.getLogger('audit')
degradation_logger = logging.getLogger('fleet_monitoring.cache_degradation')

VEHICLE_STATUS_CACHE_KEY = 'fleet:vehicle:{id}:status'
VEHICLE_STATUS_CACHE_TTL_SECONDS = 60

VEHICLE_TELEMETRY_CACHE_KEY = 'fleet:vehicle:{id}:telemetry'

VEHICLE_LOOKUP_CACHE_KEY = 'fleet:vehicle:lookup:{public_id}'
VEHICLE_LOOKUP_CACHE_TTL_SECONDS = 60
VEHICLE_LOOKUP_MISSING_TTL_SECONDS = 10

DASHBOARD_STATS_CACHE_KEY = 'fleet:dashboard:stats'
DASHBOARD_STATS_CACHE_TTL_SECONDS = 30

VEHICLE_RELATED = ('driver__user', 'assigned_manager', 'obu')
UNIQUE_FIELDS = ('license_plate', 'vin', 'vehicle_id', 'serial_number', 'license_number', 'phone_number', 'user')
UNIQUE_ALIASES = {'user_id': 'user', 'vehicle_id': 'vehicle_id'}
UNIQUE_MESSAGES = {'user': 'This user already has a driver profile'}


def _integrity_error(exc):
    return integrity_error_to_validation(
        exc, UNIQUE_FIELDS, messages=UNIQUE_MESSAGES, aliases=UNIQUE_ALIASES,
    )


def _jittered(ttl):
    spread = max(1, ttl // 10)
    return ttl + random.randint(-spread, spread)


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
        cache.set(key, value, timeout=_jittered(timeout))
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
    def list_vehicles(user, filters=None):
        queryset = Vehicle.objects.select_related(*VEHICLE_RELATED)
        if user.is_fleet_manager:
            queryset = queryset.filter(assigned_manager=user)
        elif not user.is_admin:
            raise PermissionDenied('Drivers must use /api/v1/vehicles/me/')

        filters = filters or {}
        if filters.get('status'):
            queryset = queryset.filter(status=filters['status'])
        if filters.get('driver'):
            queryset = queryset.filter(driver_id=filters['driver'])
        if filters.get('assigned_manager') and user.is_admin:
            queryset = queryset.filter(assigned_manager_id=filters['assigned_manager'])
        search = filters.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(vehicle_id__icontains=search) | models.Q(license_plate__icontains=search)
                | models.Q(vin__icontains=search) | models.Q(make__icontains=search)
                | models.Q(model__icontains=search)
            )
        return queryset.order_by('-created_at', '-id')

    @staticmethod
    def get_vehicle_for_user(user, vehicle_id):
        try:
            vehicle = Vehicle.objects.select_related(*VEHICLE_RELATED).get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            raise NotFound('Vehicle not found')

        if user.is_admin:
            return vehicle
        if user.is_fleet_manager and vehicle.assigned_manager_id == user.id:
            return vehicle
        if (
            user.is_driver and vehicle.driver_id
            and vehicle.driver.user_id == user.id and vehicle.driver.is_active
        ):
            return vehicle

        raise PermissionDenied('You do not have access to this vehicle')

    @staticmethod
    def get_vehicles_for_driver(user):
        return (
            Vehicle.objects.filter(driver__user=user, driver__is_active=True)
            .select_related(*VEHICLE_RELATED)
            .order_by('-created_at', '-id')
        )

    @staticmethod
    def get_ingest_target(public_id):
        key = VEHICLE_LOOKUP_CACHE_KEY.format(public_id=public_id)
        cached = _safe_cache_get(key, 'get_ingest_target')
        if cached is not None:
            return None if cached.get('missing') else cached

        vehicle = Vehicle.objects.select_related('driver', 'obu').filter(vehicle_id=public_id).first()
        if vehicle is None:
            _safe_cache_set(key, {'missing': True}, VEHICLE_LOOKUP_MISSING_TTL_SECONDS, 'get_ingest_target')
            return None

        obu = getattr(vehicle, 'obu', None)
        snapshot = {
            'pk': vehicle.id,
            'public_id': vehicle.vehicle_id,
            'status': vehicle.status,
            'assigned_manager_id': vehicle.assigned_manager_id,
            'driver_id': vehicle.driver_id,
            'driver_user_id': vehicle.driver.user_id if vehicle.driver_id else None,
            'driver_active': bool(vehicle.driver_id and vehicle.driver.is_active),
            'obu_serial': obu.serial_number if obu else None,
        }
        _safe_cache_set(key, snapshot, VEHICLE_LOOKUP_CACHE_TTL_SECONDS, 'get_ingest_target')
        return snapshot

    @staticmethod
    def _assert_driver_assignable(actor, driver):
        if driver is None or not actor.is_fleet_manager:
            return
        if not DriverService.list_assignable(actor).filter(pk=driver.pk).exists():
            raise PermissionDenied('You do not have access to this driver')

    @staticmethod
    def create_vehicle(actor, data):
        data = dict(data)
        obu_serial = data.pop('obu_serial_number', None)
        obu_firmware = data.pop('obu_firmware_version', '')

        if actor.is_fleet_manager:
            data['assigned_manager'] = actor
        VehicleService._assert_driver_assignable(actor, data.get('driver'))

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
            raise _integrity_error(exc)

        VehicleService._invalidate_caches(vehicle.id, [vehicle.assigned_manager_id], vehicle.vehicle_id)
        audit_logger.info(
            'vehicle_created', extra={'actor': actor.id, 'action': 'create_vehicle', 'target': vehicle.id}
        )
        return vehicle

    @staticmethod
    def update_vehicle(actor, vehicle_id, data):
        vehicle = VehicleService.get_vehicle_for_user(actor, vehicle_id)
        previous_manager_id = vehicle.assigned_manager_id

        data = dict(data)
        obu_serial_provided = 'obu_serial_number' in data
        obu_serial = data.pop('obu_serial_number', None)
        obu_firmware = data.pop('obu_firmware_version', None)

        if actor.is_fleet_manager:
            data.pop('assigned_manager', None)
        if 'driver' in data and data['driver'] != vehicle.driver:
            VehicleService._assert_driver_assignable(actor, data['driver'])

        for field, value in data.items():
            setattr(vehicle, field, value)

        try:
            with transaction.atomic():
                vehicle.full_clean(exclude=['vehicle_id', 'company'])
                vehicle.save()

                obu = getattr(vehicle, 'obu', None)
                if obu_serial_provided and obu_serial is None:
                    if obu is not None:
                        obu.delete()
                elif obu is not None or obu_serial:
                    if obu is None:
                        obu = OBU(vehicle=vehicle, serial_number=obu_serial, firmware_version=obu_firmware or '')
                    if obu_serial:
                        obu.serial_number = obu_serial
                    if obu_firmware is not None:
                        obu.firmware_version = obu_firmware
                    obu.full_clean()
                    obu.save()
        except IntegrityError as exc:
            raise _integrity_error(exc)

        VehicleService._invalidate_caches(
            vehicle.id, [previous_manager_id, vehicle.assigned_manager_id], vehicle.vehicle_id,
        )
        audit_logger.info(
            'vehicle_updated', extra={'actor': actor.id, 'action': 'update_vehicle', 'target': vehicle.id}
        )
        return vehicle

    @staticmethod
    def delete_vehicle(actor, vehicle_id):
        if not actor.is_admin:
            raise PermissionDenied('Only admin can delete vehicles')

        try:
            vehicle = Vehicle.objects.get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            raise NotFound('Vehicle not found')

        if vehicle.telemetry_logs.exists() or vehicle.alerts.exists():
            raise ValidationError({
                'detail': 'Vehicle has recorded telemetry or alerts and cannot be deleted; '
                          'set its status to decommissioned instead',
            })

        manager_id, public_id = vehicle.assigned_manager_id, vehicle.vehicle_id
        vehicle.delete()

        VehicleService._invalidate_caches(vehicle_id, [manager_id], public_id)
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
    def _invalidate_caches(vehicle_id, manager_ids=(), public_id=None):
        _safe_cache_delete(VEHICLE_STATUS_CACHE_KEY.format(id=vehicle_id), 'invalidate_status_cache')
        if public_id:
            _safe_cache_delete(VEHICLE_LOOKUP_CACHE_KEY.format(public_id=public_id), 'invalidate_lookup_cache')
        _safe_cache_delete(DASHBOARD_STATS_CACHE_KEY, 'invalidate_dashboard_cache')
        for manager_id in {m for m in manager_ids if m}:
            _safe_cache_delete(f'{DASHBOARD_STATS_CACHE_KEY}:{manager_id}', 'invalidate_dashboard_cache')

    @staticmethod
    def _count_open_alerts(user):
        alerts_qs = Alert.objects.exclude(acknowledgments__user=user).exclude(dismissals__user=user)
        if not user.is_admin:
            alerts_qs = alerts_qs.filter(vehicle__assigned_manager=user)
        return alerts_qs.count()

    @staticmethod
    def get_dashboard_stats(user):
        if not (user.is_admin or user.is_fleet_manager):
            raise PermissionDenied('Only admin and fleet_manager may view dashboard stats')

        cache_key = DASHBOARD_STATS_CACHE_KEY if user.is_admin else f'{DASHBOARD_STATS_CACHE_KEY}:{user.id}'
        cached = _safe_cache_get(cache_key, 'get_dashboard_stats')
        if cached is None:
            queryset = Vehicle.objects.all() if user.is_admin else Vehicle.objects.filter(assigned_manager=user)

            by_status = {choice.value: 0 for choice in Vehicle.Status}
            for row in queryset.order_by().values('status').annotate(count=models.Count('id')):
                by_status[row['status']] = row['count']

            cached = {
                'total_vehicles': sum(by_status.values()),
                'vehicles_by_status': by_status,
                'generated_at': django_timezone.now().isoformat(),
            }
            _safe_cache_set(cache_key, cached, DASHBOARD_STATS_CACHE_TTL_SECONDS, 'get_dashboard_stats')

        return {**cached, 'unacknowledged_alerts': VehicleService._count_open_alerts(user)}


class DriverService:

    @staticmethod
    def list_drivers(user, search=None):
        queryset = Driver.objects.select_related('user')
        if user.is_fleet_manager:
            queryset = queryset.filter(vehicles__assigned_manager=user).distinct()
        elif not user.is_admin:
            raise PermissionDenied('Drivers do not have access to the drivers list')
        if search:
            queryset = queryset.filter(
                models.Q(license_number__icontains=search) | models.Q(user__username__icontains=search)
                | models.Q(user__first_name__icontains=search) | models.Q(user__last_name__icontains=search)
                | models.Q(phone_number__icontains=search)
            )
        return queryset.order_by('-created_at', '-id')

    @staticmethod
    def get_driver(user, driver_id):
        try:
            return DriverService.list_drivers(user).get(id=driver_id)
        except Driver.DoesNotExist:
            raise NotFound('Driver not found')

    @staticmethod
    def list_linkable_users(user):
        if not (user.is_admin or user.is_fleet_manager):
            raise PermissionDenied('Only admin and fleet_manager may browse driver-role users')
        return User.objects.filter(
            role=User.Role.DRIVER, driver_profile__isnull=True
        ).order_by('username')

    @staticmethod
    def list_assignable(user):
        queryset = Driver.objects.select_related('user').filter(is_active=True)
        if user.is_fleet_manager:
            queryset = queryset.filter(
                models.Q(vehicles__assigned_manager=user) | models.Q(vehicles__isnull=True)
            ).distinct()
        elif not user.is_admin:
            raise PermissionDenied('Drivers do not have access to the drivers list')
        return queryset.order_by('-created_at', '-id')

    @staticmethod
    def create_driver(actor, data):
        driver = Driver(**data)
        try:
            with transaction.atomic():
                driver.full_clean()
                driver.save()
        except IntegrityError as exc:
            raise _integrity_error(exc)

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
            with transaction.atomic():
                driver.full_clean()
                driver.save()
        except IntegrityError as exc:
            raise _integrity_error(exc)

        for public_id in driver.vehicles.values_list('vehicle_id', flat=True):
            _safe_cache_delete(VEHICLE_LOOKUP_CACHE_KEY.format(public_id=public_id), 'invalidate_lookup_cache')

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
            raise NotFound('Driver not found')

        audit_logger.info(
            'driver_deleted', extra={'actor': actor.id, 'action': 'delete_driver', 'target': driver_id}
        )


class CompanyService:

    @staticmethod
    def get_company():
        company = Company.objects.order_by('id').first()
        if company is None:
            raise NotFound('Company not found')
        return company

    @staticmethod
    def update_company(actor, data):
        if not actor.is_admin:
            raise PermissionDenied('Only admin can update company information')

        company = CompanyService.get_company()

        for field, value in data.items():
            setattr(company, field, value)

        try:
            with transaction.atomic():
                company.full_clean()
                company.save()
        except IntegrityError as exc:
            raise integrity_error_to_validation(exc, ('name',))

        audit_logger.info(
            'company_updated', extra={'actor': actor.id, 'action': 'update_company', 'target': company.id}
        )
        return company