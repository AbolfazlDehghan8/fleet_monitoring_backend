from rest_framework import serializers

from .models import Alert


class AlertSerializer(serializers.ModelSerializer):
    vehicle_id = serializers.CharField(source='vehicle.vehicle_id', read_only=True)
    acknowledged_by_username = serializers.CharField(source='acknowledged_by.username', read_only=True)

    class Meta:
        model = Alert
        fields = [
            'id', 'vehicle_id', 'rule_name', 'metric', 'threshold', 'value', 'severity',
            'acknowledged', 'acknowledged_by_username', 'acknowledged_at', 'created_at',
        ]
        read_only_fields = fields