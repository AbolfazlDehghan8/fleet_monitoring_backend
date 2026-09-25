import logging
import random

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound

from fleet_monitoring.dead_letter import publish_to_dead_letter
from fleet_monitoring.tracing import trace_span

from .models import Rule, rule_matches

audit_logger = logging.getLogger('audit')
degradation_logger = logging.getLogger('fleet_monitoring.cache_degradation')

ACTIVE_RULES_CACHE_KEY = 'fleet:rules:active'
ACTIVE_RULES_CACHE_TTL_SECONDS = 300

DUPLICATE_RULE_MESSAGE = 'A rule with the same metric, operator, and threshold already exists.'
RULE_FIELDS = ('id', 'name', 'metric', 'operator', 'threshold', 'severity')


def invalidate_active_rules_cache():
    try:
        cache.delete(ACTIVE_RULES_CACHE_KEY)
    except Exception:
        degradation_logger.warning(
            'rules_cache_invalidate_failed',
            extra={'actor': 'api', 'action': 'invalidate_rules_cache', 'target': ACTIVE_RULES_CACHE_KEY},
            exc_info=True,
        )


class RuleService:

    @staticmethod
    def list_rules(is_active=None):
        queryset = Rule.objects.select_related('created_by')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        return queryset.order_by('-created_at', '-id')

    @staticmethod
    def get_rule(rule_id):
        try:
            return Rule.objects.select_related('created_by').get(id=rule_id)
        except Rule.DoesNotExist:
            raise NotFound('Rule not found')

    @staticmethod
    def _save(rule):
        try:
            with transaction.atomic():
                rule.full_clean(exclude=['created_by'])
                rule.save()
        except IntegrityError:
            raise ValidationError({'non_field_errors': DUPLICATE_RULE_MESSAGE})
        invalidate_active_rules_cache()

    @staticmethod
    def create_rule(actor, data):
        rule = Rule(created_by=actor, **data)
        RuleService._save(rule)
        audit_logger.info('rule_created', extra={'actor': actor.id, 'action': 'create_rule', 'target': rule.id})
        return rule

    @staticmethod
    def update_rule(actor, rule, data):
        for field, value in data.items():
            setattr(rule, field, value)
        RuleService._save(rule)
        audit_logger.info('rule_updated', extra={'actor': actor.id, 'action': 'update_rule', 'target': rule.id})
        return rule

    @staticmethod
    def delete_rule(actor, rule_id):
        rule = RuleService.get_rule(rule_id)
        audit_logger.info('rule_deleted', extra={'actor': actor.id, 'action': 'delete_rule', 'target': rule_id})
        rule.delete()
        invalidate_active_rules_cache()

    @staticmethod
    def get_active_rules():
        try:
            cached = cache.get(ACTIVE_RULES_CACHE_KEY)
        except Exception:
            cached = None
        if cached is not None:
            return cached

        rules = list(Rule.objects.filter(is_active=True).order_by('id').values(*RULE_FIELDS))
        try:
            ttl = ACTIVE_RULES_CACHE_TTL_SECONDS
            cache.set(ACTIVE_RULES_CACHE_KEY, rules, timeout=ttl + random.randint(-ttl // 10, ttl // 10))
        except Exception:
            degradation_logger.warning(
                'rules_cache_write_failed',
                extra={'actor': 'rule_engine', 'action': 'cache_set_rules', 'target': ACTIVE_RULES_CACHE_KEY},
                exc_info=True,
            )
        return rules

    @staticmethod
    def evaluate(telemetry_log, vehicle_public_id=None):
        with trace_span('rules.evaluate', vehicle_pk=telemetry_log.vehicle_id):
            violations = []
            for rule in RuleService.get_active_rules():
                value = getattr(telemetry_log, rule['metric'], None)
                if value is None:
                    continue
                if rule_matches(rule['operator'], value, rule['threshold']):
                    violations.append({
                        'rule_id': rule['id'],
                        'rule_name': rule['name'],
                        'metric': rule['metric'],
                        'operator': rule['operator'],
                        'threshold': rule['threshold'],
                        'value': value,
                        'severity': rule['severity'],
                        'vehicle_pk': telemetry_log.vehicle_id,
                        'vehicle_id': vehicle_public_id or telemetry_log.vehicle.vehicle_id,
                        'telemetry_log_id': telemetry_log.id,
                    })

        if not violations:
            return violations

        audit_logger.info(
            'rule_violations_detected',
            extra={
                'actor': 'rule_engine', 'action': 'evaluate', 'target': violations[0]['vehicle_id'],
                'violations': len(violations),
            },
        )

        from alerts_module.services import AlertService
        for violation in violations:
            try:
                AlertService.create_from_violation(violation)
            except Exception as exc:
                audit_logger.exception(
                    'alert_creation_failed',
                    extra={
                        'actor': 'rule_engine', 'action': 'create_alert',
                        'target': violation['vehicle_id'], 'rule_id': violation['rule_id'],
                    },
                )
                publish_to_dead_letter(
                    source_queue='alerts.trigger.notify',
                    task_name='alerts_module.services.AlertService.create_from_violation',
                    payload={'violation': violation},
                    reason=f'Alert creation failed: {exc!r}',
                )
        return violations