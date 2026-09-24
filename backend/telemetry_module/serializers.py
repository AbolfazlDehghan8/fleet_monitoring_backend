import math
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from fleet_monitoring.fields import NormalizedCharField
from fleet_monitoring.metrics import METRIC_RANGES
from fleet_monitoring.validators import obu_serial_validator, validate_vehicle_id

from .models import TelemetryLog


class FiniteFloatField(serializers.FloatField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not math.isfinite(value):
            self.fail('invalid')
        return value


class TelemetryIngestSerializer(serializers.Serializer):

    vehicle_id = serializers.CharField(max_length=50, validators=[validate_vehicle_id])
    obu_serial = NormalizedCharField(max_length=50, validators=[obu_serial_validator])
    timestamp = serializers.DateTimeField()
    speed = FiniteFloatField(min_value=METRIC_RANGES['speed'][0], max_value=METRIC_RANGES['speed'][1])
    engine_temperature = FiniteFloatField(
        min_value=METRIC_RANGES['engine_temperature'][0], max_value=METRIC_RANGES['engine_temperature'][1]
    )
    battery_voltage = FiniteFloatField(
        min_value=METRIC_RANGES['battery_voltage'][0], max_value=METRIC_RANGES['battery_voltage'][1]
    )
    fuel_level = FiniteFloatField(min_value=METRIC_RANGES['fuel_level'][0], max_value=METRIC_RANGES['fuel_level'][1])
    latitude = FiniteFloatField(min_value=-90, max_value=90)
    longitude = FiniteFloatField(min_value=-180, max_value=180)
    odometer = FiniteFloatField(min_value=METRIC_RANGES['odometer'][0], max_value=METRIC_RANGES['odometer'][1])

    def validate_obu_serial(self, value):
        return value.upper()

    def validate_timestamp(self, value):
        now = timezone.now()
        if value > now + timedelta(seconds=settings.TELEMETRY_MAX_FUTURE_SECONDS):
            raise serializers.ValidationError('timestamp is in the future')
        if value < now - timedelta(days=settings.TELEMETRY_RETENTION_DAYS):
            raise serializers.ValidationError('timestamp is older than the retention period')
        return value


class TelemetryQuerySerializer(serializers.Serializer):
    vehicle_id = serializers.CharField(max_length=50, required=False)
    start = serializers.DateTimeField(required=False)
    end = serializers.DateTimeField(required=False)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=500, default=500)

    def validate(self, data):
        if data.get('start') and data.get('end') and data['start'] > data['end']:
            raise serializers.ValidationError({'end': 'end must not be before start'})
        return data


class TelemetryLogSerializer(serializers.ModelSerializer):
    vehicle_id = serializers.CharField(source='vehicle.vehicle_id', read_only=True)

    class Meta:
        model = TelemetryLog
        fields = [
            'id', 'vehicle_id', 'obu_serial', 'timestamp', 'speed', 'engine_temperature',
            'battery_voltage', 'fuel_level', 'latitude', 'longitude', 'odometer', 'received_at',
        ]
        read_only_fields = fields