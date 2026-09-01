from rest_framework import serializers

from .models import Rule


class RuleSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = Rule
        fields = [
            'id', 'name', 'description', 'metric', 'operator', 'threshold',
            'severity', 'is_active', 'created_by_username', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by_username', 'created_at', 'updated_at']


class RuleWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rule
        fields = ['name', 'description', 'metric', 'operator', 'threshold', 'severity', 'is_active']
