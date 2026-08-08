from django.db import models

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


class Rule(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    metric = models.CharField(max_length=30, choices=RULE_METRIC_CHOICES)
    operator = models.CharField(max_length=3, choices=RULE_OPERATOR_CHOICES)
    threshold = models.FloatField()
    severity = models.CharField(max_length=10, choices=RULE_SEVERITY_CHOICES, default='medium')

    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        'auth_module.User', on_delete=models.SET_NULL, null=True, related_name='created_rules',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'rules'
        indexes = [
            models.Index(fields=['metric', 'is_active']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.metric} {self.get_operator_display()} {self.threshold})"

    def evaluate(self, value):
        if self.operator == 'gt':
            return value > self.threshold
        if self.operator == 'gte':
            return value >= self.threshold
        if self.operator == 'lt':
            return value < self.threshold
        if self.operator == 'lte':
            return value <= self.threshold
        if self.operator == 'eq':
            return value == self.threshold
        return False