from django.core.exceptions import ValidationError
from django.db import models

from vehicles_module.models import Vehicle


class TelemetryLog(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='telemetry_logs')
    obu_serial = models.CharField(max_length=50)

    timestamp = models.DateTimeField()
    speed = models.FloatField()
    engine_temperature = models.FloatField()
    battery_voltage = models.FloatField()
    fuel_level = models.FloatField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    odometer = models.FloatField()

    raw_payload = models.JSONField()

    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'telemetry_logs'
        constraints = [
            models.UniqueConstraint(fields=['vehicle', 'timestamp'], name='uniq_telemetry_vehicle_timestamp'),
        ]
        indexes = [
            models.Index(fields=['vehicle', '-timestamp']),
            models.Index(fields=['timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.vehicle.vehicle_id} @ {self.timestamp.isoformat()}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError('Telemetry logs are immutable and cannot be updated.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Telemetry logs are immutable and cannot be deleted.')