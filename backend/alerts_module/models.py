from django.db import models
from django.db.models import F

from rules_module.models import RULE_SEVERITY_CHOICES


class AlertQuerySet(models.QuerySet):

    def visible_to(self, user):
        if user.is_admin:
            return self
        if user.is_fleet_manager:
            return self.filter(
                vehicle__assigned_manager=user,
                created_at__gte=F('vehicle__manager_assigned_at'),
            )
        if user.is_driver:
            driver_profile = getattr(user, 'driver_profile', None)
            if driver_profile is None or not driver_profile.is_active:
                return self.none()
            return self.filter(
                vehicle__driver=driver_profile,
                created_at__gte=F('vehicle__driver_assigned_at'),
            )
        return self.none()


class Alert(models.Model):
    vehicle = models.ForeignKey('vehicles_module.Vehicle', on_delete=models.CASCADE, related_name='alerts')

    rule = models.ForeignKey('rules_module.Rule', on_delete=models.SET_NULL, null=True, related_name='alerts')
    telemetry_log = models.ForeignKey(
        'telemetry_module.TelemetryLog', on_delete=models.SET_NULL, null=True, related_name='alerts',
        db_constraint=False,
    )

    rule_name = models.CharField(max_length=100)
    metric = models.CharField(max_length=30)
    threshold = models.FloatField()
    value = models.FloatField()
    severity = models.CharField(max_length=10, choices=RULE_SEVERITY_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = AlertQuerySet.as_manager()

    class Meta:
        db_table = 'alerts'
        indexes = [
            models.Index(fields=['vehicle', '-created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.rule_name} on {self.vehicle.vehicle_id} @ {self.created_at.isoformat()}"


class AlertDismissal(models.Model):
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name='dismissals')
    user = models.ForeignKey('auth_module.User', on_delete=models.CASCADE, related_name='dismissed_alerts')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'alert_dismissals'
        constraints = [
            models.UniqueConstraint(fields=['alert', 'user'], name='alert_dismissal_unique_alert_user'),
        ]
        indexes = [models.Index(fields=['user'], name='alert_dismissal_user_idx')]


class AlertAcknowledgment(models.Model):
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name='acknowledgments')
    user = models.ForeignKey('auth_module.User', on_delete=models.CASCADE, related_name='alert_acknowledgments')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'alert_acknowledgments'
        constraints = [
            models.UniqueConstraint(fields=['alert', 'user'], name='alert_ack_unique_alert_user'),
        ]
        indexes = [models.Index(fields=['user'], name='alert_ack_user_idx')]