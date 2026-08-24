import logging

from django.utils import timezone as django_timezone
from rest_framework.exceptions import PermissionDenied

from vehicles_module.models import Vehicle

from .models import Alert

audit_logger = logging.getLogger('audit')


class AlertService:

    @staticmethod
    def create_from_violation(violation):
        vehicle = Vehicle.objects.get(vehicle_id=violation['vehicle_id'])

        alert = Alert.objects.create(
            vehicle=vehicle,
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
            extra={'actor': 'alert_engine', 'action': 'create_alert', 'target': vehicle.vehicle_id},
        )

        from .tasks import dispatch_alert_notification
        dispatch_alert_notification.apply_async(args=[alert.id], queue='alerts.trigger.notify')

        return alert

    @staticmethod
    def _check_scope(actor, alert):
        if actor.role == 'admin':
            return
        if actor.role == 'fleet_manager':
            if alert.vehicle.assigned_manager_id != actor.id:
                raise PermissionDenied('This alert is not on a vehicle assigned to you')
            return
        if actor.role == 'driver':
            driver_profile = getattr(actor, 'driver_profile', None)
            if driver_profile is None or alert.vehicle.driver_id != driver_profile.id:
                raise PermissionDenied('This alert is not on your vehicle')
            return
        raise PermissionDenied('Unknown role')

    @staticmethod
    def list_alerts(user):
        if user.role == 'admin':
            queryset = Alert.objects.all()
        elif user.role == 'fleet_manager':
            queryset = Alert.objects.filter(vehicle__assigned_manager=user)
        else:
            queryset = Alert.objects.none()
        return queryset.select_related('vehicle')[:500]

    @staticmethod
    def list_alerts_for_driver(user):
        driver_profile = getattr(user, 'driver_profile', None)
        if driver_profile is None:
            return Alert.objects.none()
        return Alert.objects.filter(vehicle__driver=driver_profile).select_related('vehicle')[:500]

    @staticmethod
    def get_alert(actor, alert_id):
        try:
            alert = Alert.objects.select_related('vehicle').get(id=alert_id)
        except Alert.DoesNotExist:
            return None
        AlertService._check_scope(actor, alert)
        return alert

    @staticmethod
    def acknowledge(actor, alert_id):
        alert = AlertService.get_alert(actor, alert_id)
        if alert is None:
            return None

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