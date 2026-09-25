from rest_framework import serializers

from .models import Rule, validate_threshold_for_metric
from .services import DUPLICATE_RULE_MESSAGE


class RuleSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default=None)

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
        validators = []

    def validate(self, data):
        metric = data.get('metric', getattr(self.instance, 'metric', None))
        operator = data.get('operator', getattr(self.instance, 'operator', None))
        threshold = data.get('threshold', getattr(self.instance, 'threshold', None))

        message = validate_threshold_for_metric(metric, threshold)
        if message:
            raise serializers.ValidationError({'threshold': message})

        duplicate_qs = Rule.objects.filter(metric=metric, operator=operator, threshold=threshold)
        if self.instance is not None:
            duplicate_qs = duplicate_qs.exclude(pk=self.instance.pk)

        if duplicate_qs.exists():
            raise serializers.ValidationError(DUPLICATE_RULE_MESSAGE)

        return data


class RuleListQuerySerializer(serializers.Serializer):
    is_active = serializers.BooleanField(allow_null=True, default=None)