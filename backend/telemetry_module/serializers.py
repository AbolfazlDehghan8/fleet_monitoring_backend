from rest_framework import serializers
from .models import TelemetryLog


class TelemetryIngestSerializer(serializers.Serializer):

    vehicle_id = serializers.CharField(max_length=50)
    obu_serial = serializers.CharField(max_length=50)
    timestamp = serializers.DateTimeField()
    speed = serializers.FloatField(min_value=0)
    engine_temperature = serializers.FloatField()
    battery_voltage = serializers.FloatField(min_value=0, max_value=50)
    fuel_level = serializers.FloatField(min_value=0, max_value=100)
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    odometer = serializers.FloatField(min_value=0)


class TelemetryLogSerializer(serializers.ModelSerializer):
    vehicle_id = serializers.CharField(source='vehicle.vehicle_id', read_only=True)

    class Meta:
        model = TelemetryLog
        fields = [
            'id', 'vehicle_id', 'obu_serial', 'timestamp', 'speed', 'engine_temperature',
            'battery_voltage', 'fuel_level', 'latitude', 'longitude', 'odometer', 'received_at',
        ]
        read_only_fields = fields