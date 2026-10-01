from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.db import OperationalError, connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from auth_module.models import User
from rules_module.models import Rule
from telemetry_module.models import TelemetryLog
from vehicles_module.models import Company, Driver, Vehicle

from .models import Alert, AlertAcknowledgment
from .services import ALERT_COOLDOWN_CACHE_KEY, AlertService
from .tasks import dispatch_alert_notification

LOCMEM_CACHE = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


def _violation(**overrides):
    violation = {
        'rule_id': None,
        'rule_name': 'High engine temperature',
        'metric': 'engine_temperature',
        'operator': 'gt',
        'threshold': 100,
        'value': 115,
        'severity': 'high',
        'vehicle_pk': None,
        'vehicle_id': 'veh_alert_1',
        'telemetry_log_id': None,
    }
    violation.update(overrides)
    return violation


@override_settings(CACHES=LOCMEM_CACHE)
class AlertsTestBase(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(
            username='admin', email='admin@example.com', password='StrongPass123', role='admin'
        )
        self.manager = User.objects.create_user(
            username='manager', email='m@example.com', password='StrongPass123', role='fleet_manager'
        )
        self.other_manager = User.objects.create_user(
            username='manager2', email='m2@example.com', password='StrongPass123', role='fleet_manager'
        )
        self.driver_user = User.objects.create_user(
            username='driveruser', email='d@example.com', password='StrongPass123', role='driver'
        )
        self.driver = Driver.objects.create(user=self.driver_user, license_number='LIC-001')
        self.company = Company.objects.create(name='Alerts Test Co')
        self.vehicle = Vehicle.objects.create(
            vehicle_id='veh_alert_1', license_plate='12ب11111', assigned_manager=self.manager,
            driver=self.driver, company=self.company,
        )
        self.rule = Rule.objects.create(
            name='High engine temperature', metric='engine_temperature', operator='gt',
            threshold=100, severity='high', created_by=self.admin,
        )
        self.log = TelemetryLog.objects.create(
            vehicle=self.vehicle, obu_serial='OBU-2026-0001', timestamp='2025-07-11T14:32:01.234Z',
            speed=60, engine_temperature=115, battery_voltage=12.5, fuel_level=50,
            latitude=0, longitude=0, odometer=1000, raw_payload={},
        )
        self.alert = self._create_alert()

    def _create_alert(self, **overrides):
        violation = _violation(
            rule_id=self.rule.id, telemetry_log_id=self.log.id, vehicle_pk=self.vehicle.id,
        )
        violation.update(overrides)
        with patch('alerts_module.tasks.dispatch_alert_notification.apply_async'):
            return AlertService.create_from_violation(violation)

    def _auth_as(self, username, password='StrongPass123'):
        login = self.client.post(reverse('login'), {'username': username, 'password': password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access_token']}")


class AlertCreationTests(AlertsTestBase):
    def test_create_from_violation_creates_alert(self):
        self.assertEqual(Alert.objects.count(), 1)
        self.assertEqual(self.alert.severity, 'high')
        self.assertFalse(self.alert.acknowledgments.exists())

    def test_alert_survives_rule_deletion(self):
        self.rule.delete()
        self.alert.refresh_from_db()
        self.assertIsNone(self.alert.rule_id)
        self.assertEqual(self.alert.rule_name, 'High engine temperature')

    def test_creation_does_not_query_for_the_vehicle(self):
        with patch('alerts_module.tasks.dispatch_alert_notification.apply_async'):
            with CaptureQueriesContext(connection) as queries:
                AlertService.create_from_violation(_violation(
                    rule_id=self.rule.id, telemetry_log_id=self.log.id, vehicle_pk=self.vehicle.id,
                    metric='speed', value=200,
                ))
        vehicle_queries = [q for q in queries if 'vehicles' in q['sql'].lower()]
        self.assertEqual(vehicle_queries, [])

    def test_notification_is_dispatched_after_creation(self):
        cache.delete(ALERT_COOLDOWN_CACHE_KEY.format(vehicle_pk=self.vehicle.id, rule_id=self.rule.id))
        with patch('alerts_module.tasks.dispatch_alert_notification.apply_async') as dispatch:
            alert = AlertService.create_from_violation(_violation(
                rule_id=self.rule.id, telemetry_log_id=self.log.id, vehicle_pk=self.vehicle.id,
                metric='speed', value=200,
            ))
        dispatch.assert_called_once_with(args=[alert.id], queue='alerts.trigger.notify')


class AlertCooldownTests(AlertsTestBase):
    def test_repeat_violation_within_cooldown_is_suppressed(self):
        before = Alert.objects.count()
        with self.assertLogs('audit', level='INFO') as captured:
            result = self._create_alert()
        self.assertIsNone(result)
        self.assertEqual(Alert.objects.count(), before)
        self.assertTrue(any('alert_suppressed_cooldown' in line for line in captured.output))

    def test_different_rule_on_same_vehicle_is_not_suppressed(self):
        other_rule = Rule.objects.create(name='Overspeed', metric='speed', operator='gt', threshold=120)
        before = Alert.objects.count()
        result = self._create_alert(rule_id=other_rule.id, metric='speed', value=130)
        self.assertIsNotNone(result)
        self.assertEqual(Alert.objects.count(), before + 1)

    def test_same_rule_on_different_vehicle_is_not_suppressed(self):
        other_vehicle = Vehicle.objects.create(
            vehicle_id='veh_alert_2', license_plate='12ب22222', company=self.company,
        )
        before = Alert.objects.count()
        result = self._create_alert(vehicle_pk=other_vehicle.id, vehicle_id='veh_alert_2')
        self.assertIsNotNone(result)
        self.assertEqual(Alert.objects.count(), before + 1)

    def test_cooldown_expiring_allows_a_new_alert(self):
        cache.delete(ALERT_COOLDOWN_CACHE_KEY.format(vehicle_pk=self.vehicle.id, rule_id=self.rule.id))
        result = self._create_alert()
        self.assertIsNotNone(result)
        self.assertEqual(Alert.objects.count(), 2)

    def test_cache_outage_fails_open_instead_of_losing_the_alert(self):
        with patch('alerts_module.services.cache') as broken_cache:
            broken_cache.add.side_effect = ConnectionError('redis down')
            with self.assertLogs('fleet_monitoring.cache_degradation', level='WARNING'):
                result = self._create_alert()
        self.assertIsNotNone(result)

    def test_concurrent_creation_only_raises_one_alert(self):
        fresh_rule = Rule.objects.create(name='Fresh', metric='fuel_level', operator='lt', threshold=5)
        before = Alert.objects.count()
        first = self._create_alert(rule_id=fresh_rule.id, vehicle_pk=self.vehicle.id, metric='fuel_level', value=2)
        second = self._create_alert(rule_id=fresh_rule.id, vehicle_pk=self.vehicle.id, metric='fuel_level', value=2)
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(Alert.objects.count(), before + 1)


class AlertReadTests(AlertsTestBase):
    def test_admin_sees_all_alerts(self):
        self._auth_as('admin')
        response = self.client.get(reverse('alert-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_fleet_manager_sees_assigned_alerts(self):
        self._auth_as('manager')
        response = self.client.get(reverse('alert-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_other_fleet_manager_sees_no_alerts(self):
        self._auth_as('manager2')
        response = self.client.get(reverse('alert-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_driver_cannot_use_general_list_endpoint(self):
        self._auth_as('driveruser')
        response = self.client.get(reverse('alert-list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_driver_sees_own_alerts_via_me_endpoint(self):
        self._auth_as('driveruser')
        response = self.client.get(reverse('alert-me'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_deactivated_driver_sees_nothing_via_me_endpoint(self):
        Driver.objects.filter(pk=self.driver.pk).update(is_active=False)
        self._auth_as('driveruser')
        self.assertEqual(self.client.get(reverse('alert-me')).data, [])

    def test_driver_cannot_read_other_vehicle_alert_detail(self):
        other_driver_user = User.objects.create_user(
            username='otherdriver', email='od@example.com', password='StrongPass123', role='driver'
        )
        Driver.objects.create(user=other_driver_user, license_number='LIC-002')
        self._auth_as('otherdriver')
        response = self.client.get(reverse('alert-detail', args=[self.alert.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_deactivated_driver_cannot_read_own_alert_detail(self):
        Driver.objects.filter(pk=self.driver.pk).update(is_active=False)
        self._auth_as('driveruser')
        response = self.client.get(reverse('alert-detail', args=[self.alert.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_alert_is_404_with_detail(self):
        self._auth_as('admin')
        response = self.client.get(reverse('alert-detail', args=[999999]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['detail'], 'Alert not found')


class AlertSerializerShapeTests(AlertsTestBase):
    def test_unacknowledged_alert_reports_null_not_a_missing_key(self):
        self._auth_as('admin')
        data = self.client.get(reverse('alert-detail', args=[self.alert.id])).data
        self.assertIn('acknowledged_by_username', data)
        self.assertIsNone(data['acknowledged_by_username'])

    def test_acknowledged_alert_reports_the_username(self):
        self._auth_as('admin')
        self.client.post(reverse('alert-acknowledge', args=[self.alert.id]))
        data = self.client.get(reverse('alert-detail', args=[self.alert.id])).data
        self.assertEqual(data['acknowledged_by_username'], 'admin')


class AlertAcknowledgeTests(AlertsTestBase):
    def test_admin_can_acknowledge_any_alert(self):
        self._auth_as('admin')
        response = self.client.post(reverse('alert-acknowledge', args=[self.alert.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['acknowledged'])

    def test_driver_can_acknowledge_own_alert(self):
        self._auth_as('driveruser')
        response = self.client.post(reverse('alert-acknowledge', args=[self.alert.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            AlertAcknowledgment.objects.filter(alert=self.alert, user=self.driver_user).exists()
        )

    def test_deactivated_driver_cannot_acknowledge(self):
        Driver.objects.filter(pk=self.driver.pk).update(is_active=False)
        self._auth_as('driveruser')
        response = self.client.post(reverse('alert-acknowledge', args=[self.alert.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.alert.acknowledgments.exists())

    def test_other_fleet_manager_cannot_acknowledge(self):
        self._auth_as('manager2')
        response = self.client.post(reverse('alert-acknowledge', args=[self.alert.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_acknowledge_is_idempotent(self):
        self._auth_as('admin')
        self.client.post(reverse('alert-acknowledge', args=[self.alert.id]))
        first_ack_time = AlertAcknowledgment.objects.get(alert=self.alert, user=self.admin).created_at

        response = self.client.post(reverse('alert-acknowledge', args=[self.alert.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(AlertAcknowledgment.objects.filter(alert=self.alert, user=self.admin).count(), 1)
        second_ack_time = AlertAcknowledgment.objects.get(alert=self.alert, user=self.admin).created_at
        self.assertEqual(first_ack_time, second_ack_time)

    def test_acknowledge_nonexistent_alert_404(self):
        self._auth_as('admin')
        response = self.client.post(reverse('alert-acknowledge', args=[99999]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_cannot_acknowledge(self):
        response = self.client.post(reverse('alert-acknowledge', args=[self.alert.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AlertMeAcknowledgeTests(AlertsTestBase):

    def test_driver_can_acknowledge_own_alert_via_me_endpoint(self):
        self._auth_as('driveruser')
        response = self.client.post(reverse('alert-me-acknowledge'), {'alert_id': self.alert.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            AlertAcknowledgment.objects.filter(alert=self.alert, user=self.driver_user).exists()
        )

    def test_driver_cannot_acknowledge_other_vehicle_alert_via_me_endpoint(self):
        other_driver_user = User.objects.create_user(
            username='otherdriver', email='od@example.com', password='StrongPass123', role='driver'
        )
        Driver.objects.create(user=other_driver_user, license_number='LIC-002')
        self._auth_as('otherdriver')
        response = self.client.post(reverse('alert-me-acknowledge'), {'alert_id': self.alert.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_use_driver_me_endpoint(self):
        self._auth_as('admin')
        response = self.client.post(reverse('alert-me-acknowledge'), {'alert_id': self.alert.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_alert_id_rejected(self):
        self._auth_as('driveruser')
        response = self.client.post(reverse('alert-me-acknowledge'), {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_alert_id_rejected(self):
        self._auth_as('driveruser')
        response = self.client.post(reverse('alert-me-acknowledge'), {'alert_id': -1})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(CACHES=LOCMEM_CACHE, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AlertNotificationTests(AlertsTestBase):

    def test_notification_email_sent_to_assigned_manager_and_admins(self):
        mail.outbox = []
        dispatch_alert_notification.apply(args=[self.alert.id])

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn(self.manager.email, sent.to)
        self.assertIn(self.admin.email, sent.to)
        self.assertIn('veh_alert_1', sent.subject)

    def test_notification_skipped_gracefully_when_no_recipients(self):
        User.objects.filter(role='admin').update(is_active=False)
        unassigned_vehicle = Vehicle.objects.create(
            vehicle_id='veh_alert_unassigned', license_plate='12ب33333', company=self.company
        )
        alert = Alert.objects.create(
            vehicle=unassigned_vehicle, rule_id=self.rule.id, rule_name='x', metric='speed',
            threshold=100, value=120, severity='low',
        )
        mail.outbox = []
        dispatch_alert_notification.apply(args=[alert.id])
        self.assertEqual(len(mail.outbox), 0)

    def test_notification_skipped_gracefully_when_alert_was_deleted(self):
        mail.outbox = []
        with self.assertLogs('audit', level='WARNING'):
            dispatch_alert_notification.apply(args=[999999])
        self.assertEqual(len(mail.outbox), 0)

    def test_transient_send_failure_is_retried_then_dead_lettered_when_exhausted(self):
        with patch('alerts_module.tasks.send_mail', side_effect=OperationalError('smtp relay down')) as send, \
                patch('alerts_module.tasks.publish_to_dead_letter') as dlq:
            with self.assertRaises(OperationalError):
                dispatch_alert_notification.apply(
                    args=[self.alert.id], retries=dispatch_alert_notification.max_retries,
                )
        self.assertEqual(send.call_count, 1)
        dlq.assert_called_once()
        self.assertIn('Retries exhausted', dlq.call_args.kwargs['reason'])
        self.assertEqual(dlq.call_args.kwargs['payload']['alert_id'], self.alert.id)

    def test_send_failure_below_the_retry_limit_does_not_dead_letter(self):
        with patch('alerts_module.tasks.send_mail', side_effect=OperationalError('smtp relay down')), \
                patch('alerts_module.tasks.publish_to_dead_letter') as dlq:
            with self.assertRaises(Exception):
                dispatch_alert_notification.apply(args=[self.alert.id], retries=0)
        dlq.assert_not_called()


class AlertDismissTests(AlertsTestBase):
    def _delete(self, username, alert=None):
        self._auth_as(username)
        return self.client.delete(reverse('alert-detail', args=[(alert or self.alert).id]))

    def _ids(self, url_name):
        return [a['id'] for a in self.client.get(reverse(url_name)).data]

    def test_admin_dismiss_hides_from_own_list_only(self):
        self.assertEqual(self._delete('admin').status_code, status.HTTP_204_NO_CONTENT)
        self.assertNotIn(self.alert.id, self._ids('alert-list'))
        self._auth_as('manager')
        self.assertIn(self.alert.id, self._ids('alert-list'))
        self.assertTrue(Alert.objects.filter(id=self.alert.id).exists())

    def test_manager_can_dismiss_assigned_alert(self):
        self.assertEqual(self._delete('manager').status_code, status.HTTP_204_NO_CONTENT)
        self.assertNotIn(self.alert.id, self._ids('alert-list'))

    def test_driver_can_dismiss_own_alert(self):
        self.assertEqual(self._delete('driveruser').status_code, status.HTTP_204_NO_CONTENT)
        self.assertNotIn(self.alert.id, self._ids('alert-me'))
        self._auth_as('manager')
        self.assertIn(self.alert.id, self._ids('alert-list'))

    def test_other_manager_cannot_dismiss(self):
        self.assertEqual(self._delete('manager2').status_code, status.HTTP_403_FORBIDDEN)

    def test_dismiss_is_idempotent(self):
        self._delete('admin')
        self.assertEqual(self._delete('admin').status_code, status.HTTP_204_NO_CONTENT)

    def test_missing_alert_is_404(self):
        self._auth_as('admin')
        response = self.client.delete(reverse('alert-detail', args=[999999]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AlertRoleIndependenceTests(AlertsTestBase):
    def _ack(self, username):
        self._auth_as(username)
        return self.client.post(reverse('alert-acknowledge', args=[self.alert.id]))

    def _state(self, username, url_name='alert-list'):
        self._auth_as(username)
        rows = [a for a in self.client.get(reverse(url_name)).data if a['id'] == self.alert.id]
        return rows[0] if rows else None

    def test_admin_ack_does_not_acknowledge_for_manager_or_driver(self):
        self.assertEqual(self._ack('admin').status_code, status.HTTP_200_OK)
        self.assertTrue(self._state('admin')['acknowledged'])
        self.assertFalse(self._state('manager')['acknowledged'])
        self.assertFalse(self._state('driveruser', 'alert-me')['acknowledged'])

    def test_manager_ack_does_not_acknowledge_for_admin_or_driver(self):
        self._ack('manager')
        self.assertTrue(self._state('manager')['acknowledged'])
        self.assertFalse(self._state('admin')['acknowledged'])
        self.assertFalse(self._state('driveruser', 'alert-me')['acknowledged'])

    def test_driver_ack_does_not_acknowledge_for_admin_or_manager(self):
        self._ack('driveruser')
        self.assertTrue(self._state('driveruser', 'alert-me')['acknowledged'])
        self.assertFalse(self._state('admin')['acknowledged'])
        self.assertFalse(self._state('manager')['acknowledged'])

    def test_each_role_keeps_its_own_acknowledgment_details(self):
        self._ack('admin')
        self._ack('manager')
        admin_row = self._state('admin')
        manager_row = self._state('manager')
        self.assertEqual(admin_row['acknowledged_by_username'], 'admin')
        self.assertEqual(manager_row['acknowledged_by_username'], 'manager')
        self.assertIsNone(self._state('driveruser', 'alert-me')['acknowledged_by_username'])
        self.assertEqual(AlertAcknowledgment.objects.filter(alert=self.alert).count(), 2)

    def test_detail_endpoint_reflects_only_own_acknowledgment(self):
        self._ack('admin')
        self._auth_as('manager')
        data = self.client.get(reverse('alert-detail', args=[self.alert.id])).data
        self.assertFalse(data['acknowledged'])
        self.assertIsNone(data['acknowledged_at'])

    def test_dismiss_does_not_touch_acknowledgment_or_other_roles(self):
        self._ack('manager')
        self._auth_as('admin')
        self.client.delete(reverse('alert-detail', args=[self.alert.id]))
        self.assertIsNone(self._state('admin'))
        self.assertTrue(self._state('manager')['acknowledged'])
        self.assertFalse(self._state('driveruser', 'alert-me')['acknowledged'])

    def test_dismissing_one_role_keeps_alert_open_for_the_others(self):
        self._auth_as('driveruser')
        self.client.delete(reverse('alert-detail', args=[self.alert.id]))
        self.assertIsNone(self._state('driveruser', 'alert-me'))
        self.assertIsNotNone(self._state('admin'))
        self.assertIsNotNone(self._state('manager'))
        self.assertFalse(self._state('admin')['acknowledged'])


class AlertAssignmentWindowTests(AlertsTestBase):
    def _new_alert(self):
        cache.clear()
        return self._create_alert()

    def _ids(self, username, url_name='alert-list'):
        self._auth_as(username)
        return [a['id'] for a in self.client.get(reverse(url_name)).data]

    def _detail_status(self, username, alert):
        self._auth_as(username)
        return self.client.get(reverse('alert-detail', args=[alert.id])).status_code

    def _reassign_manager(self, manager):
        self.vehicle.refresh_from_db()
        self.vehicle.assigned_manager = manager
        self.vehicle.save()

    def _reassign_driver(self, driver):
        self.vehicle.refresh_from_db()
        self.vehicle.driver = driver
        self.vehicle.save()

    def _second_driver(self):
        user = User.objects.create_user(
            username='driveruser2', email='d2@example.com', password='StrongPass123', role='driver'
        )
        return Driver.objects.create(user=user, license_number='LIC-002')

    def test_new_manager_does_not_see_old_alerts_but_sees_new_ones(self):
        old_alert = self.alert
        self._reassign_manager(self.other_manager)
        self.assertEqual(self._ids('manager2'), [])
        self.assertEqual(self._detail_status('manager2', old_alert), status.HTTP_403_FORBIDDEN)

        new_alert = self._new_alert()
        self.assertEqual(self._ids('manager2'), [new_alert.id])
        self.assertEqual(self._detail_status('manager2', new_alert), status.HTTP_200_OK)

    def test_previous_manager_loses_the_vehicle_alerts(self):
        self._reassign_manager(self.other_manager)
        new_alert = self._new_alert()
        self.assertEqual(self._ids('manager'), [])
        self.assertEqual(self._detail_status('manager', self.alert), status.HTTP_403_FORBIDDEN)
        self.assertEqual(self._detail_status('manager', new_alert), status.HTTP_403_FORBIDDEN)

    def test_returning_manager_does_not_get_alerts_from_his_absence(self):
        self._reassign_manager(self.other_manager)
        absent_alert = self._new_alert()
        self._reassign_manager(self.manager)
        self.assertEqual(self._ids('manager'), [])
        self.assertEqual(self._detail_status('manager', absent_alert), status.HTTP_403_FORBIDDEN)
        fresh_alert = self._new_alert()
        self.assertEqual(self._ids('manager'), [fresh_alert.id])

    def test_new_driver_does_not_see_old_alerts_but_sees_new_ones(self):
        second_driver = self._second_driver()
        self._reassign_driver(second_driver)
        self.assertEqual(self._ids('driveruser2', 'alert-me'), [])
        self.assertEqual(self._detail_status('driveruser2', self.alert), status.HTTP_403_FORBIDDEN)

        new_alert = self._new_alert()
        self.assertEqual(self._ids('driveruser2', 'alert-me'), [new_alert.id])
        self.assertEqual(self._detail_status('driveruser2', new_alert), status.HTTP_200_OK)

    def test_previous_driver_loses_the_vehicle_alerts(self):
        self._reassign_driver(self._second_driver())
        new_alert = self._new_alert()
        self.assertEqual(self._ids('driveruser', 'alert-me'), [])
        self.assertEqual(self._detail_status('driveruser', self.alert), status.HTTP_403_FORBIDDEN)
        self.assertEqual(self._detail_status('driveruser', new_alert), status.HTTP_403_FORBIDDEN)

    def test_driver_change_does_not_affect_manager_window(self):
        self._reassign_driver(self._second_driver())
        self.assertEqual(self._ids('manager'), [self.alert.id])

    def test_manager_change_does_not_affect_driver_window(self):
        self._reassign_manager(self.other_manager)
        self.assertEqual(self._ids('driveruser', 'alert-me'), [self.alert.id])

    def test_admin_always_sees_every_alert(self):
        self._reassign_manager(self.other_manager)
        self._reassign_driver(self._second_driver())
        new_alert = self._new_alert()
        self.assertCountEqual(self._ids('admin'), [self.alert.id, new_alert.id])

    def test_unassigned_vehicle_clears_the_timestamps(self):
        self.vehicle.refresh_from_db()
        self.assertIsNotNone(self.vehicle.manager_assigned_at)
        self.assertIsNotNone(self.vehicle.driver_assigned_at)
        self.vehicle.assigned_manager = None
        self.vehicle.driver = None
        self.vehicle.save()
        self.vehicle.refresh_from_db()
        self.assertIsNone(self.vehicle.manager_assigned_at)
        self.assertIsNone(self.vehicle.driver_assigned_at)

    def test_saving_without_assignment_change_keeps_the_timestamps(self):
        self.vehicle.refresh_from_db()
        manager_at, driver_at = self.vehicle.manager_assigned_at, self.vehicle.driver_assigned_at
        self.vehicle.status = Vehicle.Status.MAINTENANCE
        self.vehicle.save()
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.manager_assigned_at, manager_at)
        self.assertEqual(self.vehicle.driver_assigned_at, driver_at)

    def test_update_fields_save_still_persists_the_new_timestamp(self):
        self.vehicle.refresh_from_db()
        old_at = self.vehicle.manager_assigned_at
        self.vehicle.assigned_manager = self.other_manager
        self.vehicle.save(update_fields=['assigned_manager'])
        self.vehicle.refresh_from_db()
        self.assertGreater(self.vehicle.manager_assigned_at, old_at)

    def test_dashboard_open_alert_count_only_counts_visible_alerts(self):
        from vehicles_module.services import VehicleService

        self._reassign_manager(self.other_manager)
        self.assertEqual(VehicleService._count_open_alerts(self.other_manager), 0)
        self._new_alert()
        self.assertEqual(VehicleService._count_open_alerts(self.other_manager), 1)
        self.assertEqual(VehicleService._count_open_alerts(self.manager), 0)
        self.assertEqual(VehicleService._count_open_alerts(self.admin), 2)

    def test_report_for_new_manager_excludes_pre_assignment_alerts(self):
        from datetime import timedelta

        from django.utils import timezone

        from reports_module.services import ReportService

        self._reassign_manager(self.other_manager)
        new_alert = self._new_alert()
        summary = ReportService.generate_fleet_summary(
            self.other_manager,
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(summary['alerts']['total'], 1)
        admin_summary = ReportService.generate_fleet_summary(
            self.admin,
            start_date=timezone.now() - timedelta(days=1),
            end_date=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(admin_summary['alerts']['total'], 2)
        self.assertIsNotNone(new_alert)