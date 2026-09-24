import math
import operator as op

from django.core.exceptions import ValidationError
from django.db import models

from fleet_monitoring.metrics import METRIC_RANGES

RULE_METRIC_CHOICES = [
    ('speed', 'Speed (km/h)'),
    ('engine_temperature', 'Engine Temperature (°C)'),
    ('battery_voltage', 'Battery Voltage (V)'),
    ('fuel_level', 'Fuel Level (%)'),
    ('odometer', 'Odometer (km)'),
]

RULE_OPERATOR_CHOICES = [
    ('gt', '>'),
    ('gte', '>='),
    ('lt', '<'),
    ('lte', '<='),
    ('eq', '=='),
]

RULE_SEVERITY_CHOICES = [
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
    ('critical', 'Critical'),
]

_COMPARATORS = {
    'gt': op.gt,
    'gte': op.ge,
    'lt': op.lt,
    'lte': op.le,
}


def rule_matches(operator, value, threshold):
    if operator == 'eq':
        return math.isclose(value, threshold, rel_tol=1e-9, abs_tol=1e-9)
    comparator = _COMPARATORS.get(operator)
    return bool(comparator and comparator(value, threshold))


def validate_threshold_for_metric(metric, threshold):
    if threshold is None:
        return None
    if not math.isfinite(threshold):
        return 'Threshold must be a finite number.'
    limits = METRIC_RANGES.get(metric)
    if limits and not limits[0] <= threshold <= limits[1]:
        return f'Threshold for {metric} must be between {limits[0]} and {limits[1]}.'
    return None


class Rule(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    metric = models.CharField(max_length=30, choices=RULE_METRIC_CHOICES)
    operator = models.CharField(max_length=3, choices=RULE_OPERATOR_CHOICES)
    threshold = models.FloatField()
    severity = models.CharField(max_length=10, choices=RULE_SEVERITY_CHOICES, default='medium')

    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        'auth_module.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_rules',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'rules'
        indexes = [
            models.Index(fields=['metric', 'is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['metric', 'operator', 'threshold'], name='uniq_rule_metric_operator_threshold',
            ),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.metric} {self.get_operator_display()} {self.threshold})"

    def clean(self):
        message = validate_threshold_for_metric(self.metric, self.threshold)
        if message:
            raise ValidationError({'threshold': message})

    def evaluate(self, value):
        return rule_matches(self.operator, value, self.threshold)