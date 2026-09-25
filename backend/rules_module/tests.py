from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib import admin as django_admin
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import SimpleTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from auth_module.models import User
from telemetry_module.models import TelemetryLog
from vehicles_module.models import Company, Vehicle

from .models import Rule, rule_matches
from .services import ACTIVE_RULES_CACHE_KEY, RuleService

LOCMEM_CACHE = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


@override_settings(CACHES=LOCMEM_CACHE)
class RulesTestBase(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(
            username='admin', email='admin@example.com', password='StrongPass123', role='admin'
        )
        self.manager = User.objects.create_user(
            username='manager', email='m@example.com', password='StrongPass123', role='fleet_manager'
        )
        self.driver_user = User.objects.create_user(
            username='driveruser', email='d@example.com', password='StrongPass123', role='driver'
        )

    def _auth_as(self, username, password='StrongPass123'):
        login = self.client.post(reverse('login'), {'username': username, 'password': password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access_token']}")


class RuleAccessTests(RulesTestBase):
    def test_admin_can_create_rule(self):
        self._auth_as('admin')
        response = self.client.post(reverse('rule-list-create'), {
            'name': 'High engine temperature',
            'metric': 'engine_temperature',
            'operator': 'gt',
            'threshold': 110,
            'severity': 'high',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Rule.objects.count(), 1)

    def test_fleet_manager_cannot_access_rules(self):
        self._auth_as('manager')
        response = self.client.get(reverse('rule-list-create'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_driver_cannot_access_rules(self):
        self._auth_as('driveruser')
        response = self.client.get(reverse('rule-list-create'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_fleet_manager_cannot_create_rule(self):
        self._auth_as('manager')
        response = self.client.post(reverse('rule-list-create'), {
            'name': 'Speeding', 'metric': 'speed', 'operator': 'gt', 'threshold': 120,
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_request_rejected(self):
        response = self.client.get(reverse('rule-list-create'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class RuleCrudTests(RulesTestBase):
    def setUp(self):
        super().setUp()
        self.rule = Rule.objects.create(
            name='Low battery', metric='battery_voltage', operator='lt', threshold=11.5,
            severity='critical', created_by=self.admin,
        )

    def test_admin_can_list_rules(self):
        self._auth_as('admin')
        response = self.client.get(reverse('rule-list-create'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_admin_can_filter_by_active(self):
        Rule.objects.create(
            name='Inactive rule', metric='speed', operator='gt', threshold=999,
            is_active=False, created_by=self.admin,
        )
        self._auth_as('admin')
        response = self.client.get(reverse('rule-list-create'), {'is_active': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_admin_can_update_rule(self):
        self._auth_as('admin')
        response = self.client.patch(reverse('rule-detail', args=[self.rule.id]), {'threshold': 11.0})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.threshold, 11.0)

    def test_admin_can_deactivate_rule(self):
        self._auth_as('admin')
        response = self.client.patch(reverse('rule-detail', args=[self.rule.id]), {'is_active': False})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.rule.refresh_from_db()
        self.assertFalse(self.rule.is_active)

    def test_admin_can_delete_rule(self):
        self._auth_as('admin')
        response = self.client.delete(reverse('rule-detail', args=[self.rule.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Rule.objects.filter(id=self.rule.id).exists())

    def test_invalid_metric_rejected(self):
        self._auth_as('admin')
        response = self.client.post(reverse('rule-list-create'), {
            'name': 'Bad rule', 'metric': 'not_a_real_metric', 'operator': 'gt', 'threshold': 1,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class RuleEvaluationTests(RulesTestBase):

    def setUp(self):
        super().setUp()
        self.company = Company.objects.create(name='Rules Test Co')
        self.vehicle = Vehicle.objects.create(
            vehicle_id='veh_rule_1', license_plate='12ب67890', company=self.company
        )

    def test_rule_evaluate_gt_operator(self):
        rule = Rule(metric='engine_temperature', operator='gt', threshold=100)
        self.assertTrue(rule.evaluate(101))
        self.assertFalse(rule.evaluate(100))
        self.assertFalse(rule.evaluate(99))

    def test_rule_evaluate_lt_operator(self):
        rule = Rule(metric='battery_voltage', operator='lt', threshold=11.5)
        self.assertTrue(rule.evaluate(11.0))
        self.assertFalse(rule.evaluate(11.5))

    def test_evaluate_returns_violations_for_active_rules(self):
        Rule.objects.create(
            name='High temp', metric='engine_temperature', operator='gt', threshold=100,
            severity='high', created_by=self.admin,
        )
        Rule.objects.create(
            name='Low fuel', metric='fuel_level', operator='lt', threshold=10,
            severity='low', created_by=self.admin,
        )

        from telemetry_module.models import TelemetryLog
        log = TelemetryLog.objects.create(
            vehicle=self.vehicle, obu_serial='OBU-2026-0001', timestamp='2025-07-11T14:32:01.234Z',
            speed=60, engine_temperature=115, battery_voltage=12.5, fuel_level=50,
            latitude=0, longitude=0, odometer=1000, raw_payload={},
        )

        violations = RuleService.evaluate(log)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]['metric'], 'engine_temperature')
        self.assertEqual(violations[0]['severity'], 'high')

    def test_inactive_rule_not_evaluated(self):
        Rule.objects.create(
            name='High temp (off)', metric='engine_temperature', operator='gt', threshold=100,
            is_active=False, created_by=self.admin,
        )

        from telemetry_module.models import TelemetryLog
        log = TelemetryLog.objects.create(
            vehicle=self.vehicle, obu_serial='OBU-2026-0001', timestamp='2025-07-11T14:32:01.234Z',
            speed=60, engine_temperature=200, battery_voltage=12.5, fuel_level=50,
            latitude=0, longitude=0, odometer=1000, raw_payload={},
        )

        violations = RuleService.evaluate(log)
        self.assertEqual(len(violations), 0)

    def test_evaluate_triggers_alert_creation_on_violation(self):
        Rule.objects.create(
            name='High temp', metric='engine_temperature', operator='gt', threshold=100,
            severity='high', created_by=self.admin,
        )

        from telemetry_module.models import TelemetryLog
        log = TelemetryLog.objects.create(
            vehicle=self.vehicle, obu_serial='OBU-2026-0001', timestamp='2025-07-11T14:32:01.234Z',
            speed=60, engine_temperature=115, battery_voltage=12.5, fuel_level=50,
            latitude=0, longitude=0, odometer=1000, raw_payload={},
        )

        with patch('alerts_module.services.AlertService.create_from_violation') as mock_create:
            RuleService.evaluate(log)
            self.assertEqual(mock_create.call_count, 1)
            self.assertEqual(mock_create.call_args[0][0]['metric'], 'engine_temperature')

    def test_no_violation_means_no_alert_call(self):
        Rule.objects.create(
            name='High temp', metric='engine_temperature', operator='gt', threshold=999,
            severity='high', created_by=self.admin,
        )

        from telemetry_module.models import TelemetryLog
        log = TelemetryLog.objects.create(
            vehicle=self.vehicle, obu_serial='OBU-2026-0001', timestamp='2025-07-11T14:32:01.234Z',
            speed=60, engine_temperature=115, battery_voltage=12.5, fuel_level=50,
            latitude=0, longitude=0, odometer=1000, raw_payload={},
        )

        with patch('alerts_module.services.AlertService.create_from_violation') as mock_create:
            RuleService.evaluate(log)
            self.assertEqual(mock_create.call_count, 0)


def _log(vehicle, **overrides):
    fields = dict(
        vehicle=vehicle, obu_serial='OBU-2026-0001', timestamp=timezone.now(),
        speed=60, engine_temperature=115, battery_voltage=12.5, fuel_level=50,
        latitude=0, longitude=0, odometer=1000, raw_payload={},
    )
    fields.update(overrides)
    return TelemetryLog.objects.create(**fields)


class RuleMatchingTests(SimpleTestCase):
    def test_all_operators(self):
        self.assertTrue(rule_matches('gt', 101, 100))
        self.assertFalse(rule_matches('gt', 100, 100))
        self.assertTrue(rule_matches('gte', 100, 100))
        self.assertTrue(rule_matches('lt', 11, 11.5))
        self.assertFalse(rule_matches('lt', 11.5, 11.5))
        self.assertTrue(rule_matches('lte', 11.5, 11.5))

    def test_unknown_operator_never_matches(self):
        self.assertFalse(rule_matches('bogus', 1, 1))

    def test_eq_tolerates_float_noise(self):
        self.assertTrue(rule_matches('eq', 0.1 + 0.2, 0.3))
        self.assertFalse(rule_matches('eq', 0.31, 0.3))
        self.assertTrue(Rule(metric='speed', operator='eq', threshold=0.3).evaluate(0.1 + 0.2))


class RuleValidationTests(RulesTestBase):
    def setUp(self):
        super().setUp()
        self._auth_as('admin')
        self.url = reverse('rule-list-create')

    def _post(self, **overrides):
        payload = {'name': 'R', 'metric': 'battery_voltage', 'operator': 'lt', 'threshold': 11.5}
        payload.update(overrides)
        return self.client.post(self.url, payload, format='json')

    def test_non_finite_thresholds_rejected(self):
        for bad in ('nan', 'NaN', 'inf', '-Infinity'):
            response = self._post(threshold=bad)
            self.assertEqual(response.status_code, 400, bad)
            self.assertIn('threshold', response.data)

    def test_threshold_must_be_inside_the_metric_range(self):
        self.assertEqual(self._post(metric='battery_voltage', threshold=60).status_code, 400)
        self.assertEqual(self._post(metric='fuel_level', threshold=-5, operator='lt').status_code, 400)
        self.assertEqual(self._post(metric='speed', threshold=99999).status_code, 400)
        self.assertEqual(Rule.objects.count(), 0)

    def test_threshold_at_the_range_boundary_is_accepted(self):
        self.assertEqual(self._post(metric='battery_voltage', threshold=50, operator='gt').status_code, 201)

    def test_range_is_checked_on_update_too(self):
        rule = Rule.objects.create(name='x', metric='fuel_level', operator='lt', threshold=10, created_by=self.admin)
        response = self.client.patch(reverse('rule-detail', args=[rule.id]), {'threshold': 500}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(reverse('rule-detail', args=[rule.id]), {'metric': 'battery_voltage', 'threshold': 40}, format='json')
        self.assertEqual(response.status_code, 200, response.data)

    def test_duplicate_condition_rejected_with_the_message_the_frontend_maps(self):
        self.assertEqual(self._post().status_code, 201)
        response = self._post(name='Another name', severity='critical')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data['non_field_errors'],
            ['A rule with the same metric, operator, and threshold already exists.'],
        )

    def test_database_enforces_unique_condition(self):
        Rule.objects.create(name='a', metric='speed', operator='gt', threshold=100)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Rule.objects.create(name='b', metric='speed', operator='gt', threshold=100)

    def test_race_on_duplicate_creation_becomes_a_validation_error_not_a_500(self):
        Rule.objects.create(name='a', metric='speed', operator='gt', threshold=100)
        with patch.object(Rule, 'validate_constraints'), patch.object(Rule, 'validate_unique'):
            with self.assertRaises(ValidationError) as ctx:
                RuleService.create_rule(self.admin, {
                    'name': 'b', 'metric': 'speed', 'operator': 'gt', 'threshold': 100, 'severity': 'low',
                })
        self.assertIn('non_field_errors', ctx.exception.message_dict)

    def test_unknown_rule_is_404_for_get_patch_delete(self):
        url = reverse('rule-detail', args=[999999])
        for response in (self.client.get(url), self.client.patch(url, {'name': 'x'}, format='json'), self.client.delete(url)):
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.data['detail'], 'Rule not found')

    def test_is_active_filter(self):
        Rule.objects.create(name='on', metric='speed', operator='gt', threshold=100, is_active=True)
        Rule.objects.create(name='off', metric='speed', operator='gt', threshold=110, is_active=False)
        self.assertEqual([r['name'] for r in self.client.get(self.url, {'is_active': 'true'}).data], ['on'])
        self.assertEqual([r['name'] for r in self.client.get(self.url, {'is_active': 'false'}).data], ['off'])
        self.assertEqual(len(self.client.get(self.url).data), 2)
        self.assertEqual(self.client.get(self.url, {'is_active': 'maybe'}).status_code, 400)

    def test_rule_without_creator_is_listed(self):
        Rule.objects.create(name='orphan', metric='speed', operator='gt', threshold=100, created_by=None)
        response = self.client.get(self.url)
        self.assertIsNone(response.data[0]['created_by_username'])


class RuleCacheTests(RulesTestBase):
    def setUp(self):
        super().setUp()
        self.company = Company.objects.create(name='Rules Cache Co')
        self.vehicle = Vehicle.objects.create(vehicle_id='veh_cache_1', license_plate='12ب11111', company=self.company)
        self.log = _log(self.vehicle)

    def _evaluate(self):
        with patch('alerts_module.services.AlertService.create_from_violation'):
            return RuleService.evaluate(self.log, vehicle_public_id='veh_cache_1')

    def test_rules_are_read_from_the_database_only_once(self):
        Rule.objects.create(name='hot', metric='engine_temperature', operator='gt', threshold=100)
        self._evaluate()
        with CaptureQueriesContext(connection) as queries:
            violations = self._evaluate()
        self.assertEqual(len(violations), 1)
        self.assertEqual(len(queries), 0, [q['sql'] for q in queries])

    def test_an_empty_rule_set_is_cached_too(self):
        self.assertEqual(self._evaluate(), [])
        with CaptureQueriesContext(connection) as queries:
            self._evaluate()
        self.assertEqual(len(queries), 0)

    def test_creating_a_rule_through_the_api_takes_effect_immediately(self):
        self.assertEqual(self._evaluate(), [])
        self._auth_as('admin')
        response = self.client.post(reverse('rule-list-create'), {
            'name': 'hot', 'metric': 'engine_temperature', 'operator': 'gt', 'threshold': 100,
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(self._evaluate()), 1)

    def test_update_deactivate_and_delete_invalidate_the_cache(self):
        rule = Rule.objects.create(name='hot', metric='engine_temperature', operator='gt', threshold=100)
        self.assertEqual(len(self._evaluate()), 1)
        self._auth_as('admin')
        url = reverse('rule-detail', args=[rule.id])

        self.client.patch(url, {'threshold': 200}, format='json')
        self.assertEqual(self._evaluate(), [])

        self.client.patch(url, {'threshold': 100}, format='json')
        self.assertEqual(len(self._evaluate()), 1)

        self.client.patch(url, {'is_active': False}, format='json')
        self.assertEqual(self._evaluate(), [])

        self.client.patch(url, {'is_active': True}, format='json')
        self.assertEqual(len(self._evaluate()), 1)

        self.client.delete(url)
        self.assertEqual(self._evaluate(), [])

    def test_admin_site_changes_invalidate_the_cache_too(self):
        self.assertEqual(self._evaluate(), [])
        model_admin = django_admin.site._registry[Rule]
        rule = Rule(name='hot', metric='engine_temperature', operator='gt', threshold=100)
        model_admin.save_model(SimpleNamespace(user=self.admin), rule, None, False)
        self.assertEqual(len(self._evaluate()), 1)
        model_admin.delete_model(SimpleNamespace(user=self.admin), rule)
        self.assertEqual(self._evaluate(), [])

    def test_evaluation_keeps_working_when_the_cache_is_down(self):
        Rule.objects.create(name='hot', metric='engine_temperature', operator='gt', threshold=100)
        with patch('rules_module.services.cache') as broken_cache:
            broken_cache.get.side_effect = ConnectionError('redis down')
            broken_cache.set.side_effect = ConnectionError('redis down')
            with self.assertLogs('fleet_monitoring.cache_degradation', level='WARNING'):
                violations = self._evaluate()
        self.assertEqual(len(violations), 1)

    def test_rules_are_stored_in_the_cache(self):
        Rule.objects.create(name='hot', metric='engine_temperature', operator='gt', threshold=100)
        self._evaluate()
        self.assertIsNotNone(cache.get(ACTIVE_RULES_CACHE_KEY))


class RuleEvaluationContractTests(RulesTestBase):
    def setUp(self):
        super().setUp()
        self.company = Company.objects.create(name='Rules Contract Co')
        self.vehicle = Vehicle.objects.create(vehicle_id='veh_contract', license_plate='12ب22222', company=self.company)
        Rule.objects.create(name='hot', metric='engine_temperature', operator='gt', threshold=100, severity='high')
        Rule.objects.create(name='fast', metric='speed', operator='gt', threshold=50, severity='low')
        self.log = _log(self.vehicle)

    def test_violation_carries_ids_needed_by_the_alert_service(self):
        with patch('alerts_module.services.AlertService.create_from_violation'):
            violations = RuleService.evaluate(self.log, vehicle_public_id='veh_contract')
        self.assertEqual({v['metric'] for v in violations}, {'engine_temperature', 'speed'})
        for violation in violations:
            self.assertEqual(violation['vehicle_pk'], self.vehicle.id)
            self.assertEqual(violation['vehicle_id'], 'veh_contract')
            self.assertEqual(violation['telemetry_log_id'], self.log.id)

    def test_public_vehicle_id_is_looked_up_lazily_when_not_supplied(self):
        with patch('alerts_module.services.AlertService.create_from_violation'):
            violations = RuleService.evaluate(TelemetryLog.objects.get(pk=self.log.pk))
        self.assertEqual(violations[0]['vehicle_id'], 'veh_contract')

    def test_no_query_for_the_vehicle_when_its_id_is_supplied(self):
        with patch('alerts_module.services.AlertService.create_from_violation'):
            RuleService.evaluate(self.log, vehicle_public_id='veh_contract')
            with CaptureQueriesContext(connection) as queries:
                RuleService.evaluate(self.log, vehicle_public_id='veh_contract')
        self.assertEqual(len(queries), 0)

    def test_one_failing_alert_does_not_stop_the_others(self):
        with patch('alerts_module.services.AlertService.create_from_violation',
                   side_effect=[RuntimeError('db hiccup'), None]) as create, \
                patch('rules_module.services.publish_to_dead_letter') as dlq:
            with self.assertLogs('audit', level='ERROR') as captured:
                violations = RuleService.evaluate(self.log, vehicle_public_id='veh_contract')
        self.assertEqual(create.call_count, 2)
        self.assertEqual(len(violations), 2)
        self.assertTrue(any('alert_creation_failed' in line for line in captured.output))
        dlq.assert_called_once()
        self.assertEqual(dlq.call_args.kwargs['payload']['violation']['metric'], violations[0]['metric'])

    def test_a_value_exactly_at_the_threshold_does_not_trigger_gt(self):
        log = _log(self.vehicle, timestamp=timezone.now() + timedelta(seconds=1), engine_temperature=100, speed=50)
        with patch('alerts_module.services.AlertService.create_from_violation') as create:
            self.assertEqual(RuleService.evaluate(log, vehicle_public_id='veh_contract'), [])
        create.assert_not_called()