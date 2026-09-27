import logging

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone as django_timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from .models import Alert

audit_logger = logging.getLogger('audit')
degradation_logger = logging.getLogger('fleet_monitoring.cache_degradation')

ALERT_COOLDOWN_CACHE_KEY = 'fleet:alert:cooldown:{vehicle_pk}:{rule_id}'


class AlertService:

    @staticmethod
    def _acquire_cooldown_lock(vehicle_pk, rule_id):
        key = ALERT_COOLDOWN_CACHE_KEY.format(vehicle_pk=vehicle_pk, rule_id=rule_id)
        try:
            return cache.add(key, 1, timeout=settings.ALERT_COOLDOWN_SECONDS)
        except Exception:
            degradation_logger.warning(
                'alert_cooldown_check_failed',
                extra={'actor': 'alert_engine', 'action': 'cooldown_check', 'target': key},
                exc_info=True,
            )
            return True

    @staticmethod
    def create_from_violation(violation):
        if not AlertService._acquire_cooldown_lock(violation['vehicle_pk'], violation['rule_id']):
            audit_logger.info(
                'alert_suppressed_cooldown',
                extra={'actor': 'alert_engine', 'action': 'suppress_alert', 'target': violation['vehicle_id']},
            )
            return None

        alert = Alert.objects.create(
            vehicle_id=violation['vehicle_pk'],
            rule_id=violation['rule_id'],
            telemetry_log_id=violation['telemetry_log_id'],
            rule_name=violation['rule_name'],
            metric=violation['metric'],
            threshold=violation['threshold'],
            value=violation['value'],
            severity=violation['severity'],
        )

        audit_logger.info(
            'alert_created',
            extra={'actor': 'alert_engine', 'action': 'create_alert', 'target': violation['vehicle_id']},
        )

        from .tasks import dispatch_alert_notification
        dispatch_alert_notification.apply_async(args=[alert.id], queue='alerts.trigger.notify')

        return alert

    @staticmethod
    def _check_scope(actor, alert):
        if actor.is_admin:
            return
        if actor.is_fleet_manager:
            if alert.vehicle.assigned_manager_id != actor.id:
                raise PermissionDenied('This alert is not on a vehicle assigned to you')
            return
        if actor.is_driver:
            driver_profile = getattr(actor, 'driver_profile', None)
            if (
                driver_profile is None or not driver_profile.is_active
                or alert.vehicle.driver_id != driver_profile.id
            ):
                raise PermissionDenied('This alert is not on your vehicle')
            return
        raise PermissionDenied('Unknown role')

    @staticmethod
    def list_alerts(user):
        if user.is_admin:
            queryset = Alert.objects.all()
        elif user.is_fleet_manager:
            queryset = Alert.objects.filter(vehicle__assigned_manager=user)
        else:
            queryset = Alert.objects.none()
        return queryset.select_related('vehicle', 'acknowledged_by')[:500]

    @staticmethod
    def list_alerts_for_driver(user):
        driver_profile = getattr(user, 'driver_profile', None)
        if driver_profile is None or not driver_profile.is_active:
            return Alert.objects.none()
        return (
            Alert.objects.filter(vehicle__driver=driver_profile)
            .select_related('vehicle', 'acknowledged_by')[:500]
        )

    @staticmethod
    def get_alert(actor, alert_id):
        try:
            alert = Alert.objects.select_related('vehicle', 'acknowledged_by').get(id=alert_id)
        except Alert.DoesNotExist:
            raise NotFound('Alert not found')
        AlertService._check_scope(actor, alert)
        return alert

    @staticmethod
    def acknowledge(actor, alert_id):
        with transaction.atomic():
            try:
                alert = (
                    Alert.objects.select_for_update()
                    .select_related('vehicle', 'acknowledged_by')
                    .get(id=alert_id)
                )
            except Alert.DoesNotExist:
                raise NotFound('Alert not found')

            AlertService._check_scope(actor, alert)

            if not alert.acknowledged:
                alert.acknowledged = True
                alert.acknowledged_by = actor
                alert.acknowledged_at = django_timezone.now()
                alert.save(update_fields=['acknowledged', 'acknowledged_by', 'acknowledged_at'])

                audit_logger.info(
                    'alert_acknowledged',
                    extra={'actor': actor.id, 'action': 'acknowledge_alert', 'target': alert.id},
                )

        return alert