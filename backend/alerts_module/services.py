import logging

from django.conf import settings
from django.core.cache import cache
from django.db.models import OuterRef, Subquery
from rest_framework.exceptions import NotFound, PermissionDenied

from .models import Alert, AlertAcknowledgment, AlertDismissal
from .tasks import dispatch_alert_notification

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

        dispatch_alert_notification.apply_async(args=[alert.id], queue='alerts.trigger.notify')

        return alert

    @staticmethod
    def _raised_after(alert, assigned_at):
        return assigned_at is not None and alert.created_at >= assigned_at

    @staticmethod
    def _check_scope(actor, alert):
        if actor.is_admin:
            return
        vehicle = alert.vehicle
        if actor.is_fleet_manager:
            if vehicle.assigned_manager_id != actor.id:
                raise PermissionDenied('This alert is not on a vehicle assigned to you')
            if not AlertService._raised_after(alert, vehicle.manager_assigned_at):
                raise PermissionDenied('This alert was raised before you were assigned to this vehicle')
            return
        if actor.is_driver:
            driver_profile = getattr(actor, 'driver_profile', None)
            if (
                driver_profile is None or not driver_profile.is_active
                or vehicle.driver_id != driver_profile.id
            ):
                raise PermissionDenied('This alert is not on your vehicle')
            if not AlertService._raised_after(alert, vehicle.driver_assigned_at):
                raise PermissionDenied('This alert was raised before you were assigned to this vehicle')
            return
        raise PermissionDenied('Unknown role')

    @staticmethod
    def _with_ack_state(queryset, user):
        own_ack = AlertAcknowledgment.objects.filter(alert=OuterRef('pk'), user=user)
        return queryset.annotate(my_ack_at=Subquery(own_ack.values('created_at')[:1]))

    @staticmethod
    def list_alerts(user):
        if not (user.is_admin or user.is_fleet_manager):
            return Alert.objects.none()
        queryset = Alert.objects.visible_to(user).exclude(dismissals__user=user).select_related('vehicle')
        return AlertService._with_ack_state(queryset, user)[:500]

    @staticmethod
    def list_alerts_for_driver(user):
        if not user.is_driver:
            return Alert.objects.none()
        queryset = Alert.objects.visible_to(user).exclude(dismissals__user=user).select_related('vehicle')
        return AlertService._with_ack_state(queryset, user)[:500]

    @staticmethod
    def get_alert(actor, alert_id):
        queryset = AlertService._with_ack_state(Alert.objects.select_related('vehicle'), actor)
        try:
            alert = queryset.get(id=alert_id)
        except Alert.DoesNotExist:
            raise NotFound('Alert not found')
        AlertService._check_scope(actor, alert)
        return alert

    @staticmethod
    def acknowledge(actor, alert_id):
        alert = AlertService.get_alert(actor, alert_id)
        acknowledgment, created = AlertAcknowledgment.objects.get_or_create(alert=alert, user=actor)
        alert.my_ack_at = acknowledgment.created_at
        if created:
            audit_logger.info(
                'alert_acknowledged',
                extra={'actor': actor.id, 'action': 'acknowledge_alert', 'target': alert.id},
            )
        return alert

    @staticmethod
    def dismiss(actor, alert_id):
        alert = AlertService.get_alert(actor, alert_id)
        _, created = AlertDismissal.objects.get_or_create(alert=alert, user=actor)
        if created:
            audit_logger.info(
                'alert_dismissed',
                extra={'actor': actor.id, 'action': 'dismiss_alert', 'target': alert.id},
            )