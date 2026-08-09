import logging

from django.core.exceptions import ValidationError

from .models import Rule

audit_logger = logging.getLogger('audit')


class RuleService:

    @staticmethod
    def list_rules(is_active=None):
        queryset = Rule.objects.all()
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        return queryset

    @staticmethod
    def get_rule(rule_id):
        return Rule.objects.get(id=rule_id)

    @staticmethod
    def create_rule(actor, data):
        rule = Rule(created_by=actor, **data)
        rule.full_clean(exclude=['created_by'])
        rule.save()
        audit_logger.info('rule_created', extra={'actor': actor.id, 'action': 'create_rule', 'target': rule.id})
        return rule

    @staticmethod
    def update_rule(actor, rule, data):
        for field, value in data.items():
            setattr(rule, field, value)
        rule.full_clean(exclude=['created_by'])
        rule.save()
        audit_logger.info('rule_updated', extra={'actor': actor.id, 'action': 'update_rule', 'target': rule.id})
        return rule

    @staticmethod
    def delete_rule(actor, rule_id):
        try:
            rule = Rule.objects.get(id=rule_id)
        except Rule.DoesNotExist:
            raise ValidationError({'detail': 'Rule not found'})
        audit_logger.info('rule_deleted', extra={'actor': actor.id, 'action': 'delete_rule', 'target': rule_id})
        rule.delete()

    @staticmethod
    def evaluate(telemetry_log):
        violations = []
        active_rules = Rule.objects.filter(is_active=True)

        for rule in active_rules:
            value = getattr(telemetry_log, rule.metric, None)
            if value is None:
                continue
            if rule.evaluate(value):
                violations.append({
                    'rule_id': rule.id,
                    'rule_name': rule.name,
                    'metric': rule.metric,
                    'operator': rule.operator,
                    'threshold': rule.threshold,
                    'value': value,
                    'severity': rule.severity,
                    'vehicle_id': telemetry_log.vehicle.vehicle_id,
                    'telemetry_log_id': telemetry_log.id,
                })

        if violations:
            audit_logger.info(
                'rule_violations_detected',
                extra={
                    'actor': 'rule_engine',
                    'action': 'evaluate',
                    'target': telemetry_log.vehicle.vehicle_id,
                },
            )

        return violations