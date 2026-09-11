from rest_framework import serializers

from .models import Report


class ReportQuerySerializer(serializers.Serializer):
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    vehicle_id = serializers.CharField(required=False)

    def validate(self, data):
        start = data.get('start_date')
        end = data.get('end_date')
        if start and end and start > end:
            raise serializers.ValidationError({'start_date': 'start_date must be before end_date'})
        return data


class ReportSerializer(serializers.ModelSerializer):
    sequence_number = serializers.IntegerField(read_only=True)
    requested_by_username = serializers.SerializerMethodField()
    requested_by_role = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = (
            'id', 'sequence_number', 'requested_by', 'requested_by_username', 'requested_by_role',
            'vehicle_id', 'period_start', 'period_end',
            'status', 'result', 'error_message', 'created_at', 'completed_at',
        )
        read_only_fields = fields

    def get_requested_by_username(self, obj):
        return obj.requested_by.username if obj.requested_by_id else None

    def get_requested_by_role(self, obj):
        return obj.requested_by.role if obj.requested_by_id else None