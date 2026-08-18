from rest_framework import serializers


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