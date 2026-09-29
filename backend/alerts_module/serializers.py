from rest_framework import serializers

from .models import Alert


class AlertSerializer(serializers.ModelSerializer):
    vehicle_id = serializers.CharField(source='vehicle.vehicle_id', read_only=True)
    acknowledged = serializers.SerializerMethodField()
    acknowledged_by_username = serializers.SerializerMethodField()
    acknowledged_at = serializers.DateTimeField(source='my_ack_at', read_only=True, default=None)

    class Meta:
        model = Alert
        fields = [
            'id', 'vehicle_id', 'rule_name', 'metric', 'threshold', 'value', 'severity',
            'acknowledged', 'acknowledged_by_username', 'acknowledged_at', 'created_at',
        ]
        read_only_fields = fields

    def get_acknowledged(self, obj) -> bool:
        return getattr(obj, 'my_ack_at', None) is not None

    def get_acknowledged_by_username(self, obj) -> str | None:
        if getattr(obj, 'my_ack_at', None) is None:
            return None
        return self.context['request'].user.username


class AcknowledgeOwnAlertSerializer(serializers.Serializer):
    alert_id = serializers.IntegerField(min_value=1)