from django.db import models

from rules_module.models import RULE_SEVERITY_CHOICES


class Alert(models.Model):
    vehicle = models.ForeignKey('vehicles_module.Vehicle', on_delete=models.CASCADE, related_name='alerts')

    rule = models.ForeignKey('rules_module.Rule', on_delete=models.SET_NULL, null=True, related_name='alerts')
    telemetry_log = models.ForeignKey(
        'telemetry_module.TelemetryLog', on_delete=models.SET_NULL, null=True, related_name='alerts',
    )

    rule_name = models.CharField(max_length=100)
    metric = models.CharField(max_length=30)
    threshold = models.FloatField()
    value = models.FloatField()
    severity = models.CharField(max_length=10, choices=RULE_SEVERITY_CHOICES)

    acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(
        'auth_module.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='acknowledged_alerts',
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'alerts'
        indexes = [
            models.Index(fields=['vehicle', '-created_at']),
            models.Index(fields=['acknowledged']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.rule_name} on {self.vehicle.vehicle_id} @ {self.created_at.isoformat()}"