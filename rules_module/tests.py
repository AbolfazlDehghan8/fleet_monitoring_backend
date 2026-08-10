from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from auth_module.models import User
from vehicles_module.models import Vehicle

from .models import Rule
from .services import RuleService


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
        self.vehicle = Vehicle.objects.create(vehicle_id='veh_rule_1', license_plate='RULE-001')

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
            vehicle=self.vehicle, obu_serial='OBU-TEST', timestamp='2025-07-11T14:32:01.234Z',
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
            vehicle=self.vehicle, obu_serial='OBU-TEST', timestamp='2025-07-11T14:32:01.234Z',
            speed=60, engine_temperature=200, battery_voltage=12.5, fuel_level=50,
            latitude=0, longitude=0, odometer=1000, raw_payload={},
        )

        violations = RuleService.evaluate(log)
        self.assertEqual(len(violations), 0)