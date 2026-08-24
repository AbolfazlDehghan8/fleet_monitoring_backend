from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from auth_module.models import User
from rules_module.models import Rule
from telemetry_module.models import TelemetryLog
from vehicles_module.models import Driver, Vehicle

from .models import Alert
from .services import AlertService

VIOLATION = {
    'rule_id': None,
    'rule_name': 'High engine temperature',
    'metric': 'engine_temperature',
    'operator': 'gt',
    'threshold': 100,
    'value': 115,
    'severity': 'high',
    'vehicle_id': 'veh_alert_1',
    'telemetry_log_id': None,
}


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
        self.vehicle = Vehicle.objects.create(
            vehicle_id='veh_alert_1', license_plate='ABC-123', assigned_manager=self.manager, driver=self.driver
        )
        self.rule = Rule.objects.create(
            name='High engine temperature', metric='engine_temperature', operator='gt',
            threshold=100, severity='high', created_by=self.admin,
        )
        self.log = TelemetryLog.objects.create(
            vehicle=self.vehicle, obu_serial='OBU-TEST', timestamp='2025-07-11T14:32:01.234Z',
            speed=60, engine_temperature=115, battery_voltage=12.5, fuel_level=50,
            latitude=0, longitude=0, odometer=1000, raw_payload={},
        )
        violation = dict(VIOLATION, rule_id=self.rule.id, telemetry_log_id=self.log.id)
        self.alert = AlertService.create_from_violation(violation)

    def _auth_as(self, username, password='StrongPass123'):
        login = self.client.post(reverse('login'), {'username': username, 'password': password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access_token']}")


class AlertCreationTests(AlertsTestBase):
    def test_create_from_violation_creates_alert(self):
        self.assertEqual(Alert.objects.count(), 1)
        self.assertEqual(self.alert.severity, 'high')
        self.assertFalse(self.alert.acknowledged)

    def test_alert_survives_rule_deletion(self):
        self.rule.delete()
        self.alert.refresh_from_db()
        self.assertIsNone(self.alert.rule_id)
        self.assertEqual(self.alert.rule_name, 'High engine temperature')


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

    def test_driver_cannot_read_other_vehicle_alert_detail(self):
        other_driver_user = User.objects.create_user(
            username='otherdriver', email='od@example.com', password='StrongPass123', role='driver'
        )
        Driver.objects.create(user=other_driver_user, license_number='LIC-002')
        self._auth_as('otherdriver')
        response = self.client.get(reverse('alert-detail', args=[self.alert.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


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
        self.alert.refresh_from_db()
        self.assertTrue(self.alert.acknowledged)
        self.assertEqual(self.alert.acknowledged_by_id, self.driver_user.id)

    def test_other_fleet_manager_cannot_acknowledge(self):
        self._auth_as('manager2')
        response = self.client.post(reverse('alert-acknowledge', args=[self.alert.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_acknowledge_is_idempotent(self):
        self._auth_as('admin')
        self.client.post(reverse('alert-acknowledge', args=[self.alert.id]))
        first_ack_time = Alert.objects.get(id=self.alert.id).acknowledged_at

        response = self.client.post(reverse('alert-acknowledge', args=[self.alert.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        second_ack_time = Alert.objects.get(id=self.alert.id).acknowledged_at
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
        self.alert.refresh_from_db()
        self.assertTrue(self.alert.acknowledged)

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

class AlertNotificationTests(AlertsTestBase):

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_notification_email_sent_to_assigned_manager_and_admins(self):
        from django.core import mail

        mail.outbox = []
        violation = dict(
            VIOLATION, rule_id=self.rule.id, telemetry_log_id=self.log.id, vehicle_id='veh_alert_1',
        )
        AlertService.create_from_violation(violation)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertIn(self.manager.email, sent.to)
        self.assertIn(self.admin.email, sent.to)
        self.assertIn('veh_alert_1', sent.subject)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_notification_skipped_gracefully_when_no_recipients(self):
        from django.core import mail

        User.objects.filter(role='admin').update(is_active=False)
        unassigned_vehicle = Vehicle.objects.create(vehicle_id='veh_alert_unassigned', license_plate='UNA-001')
        log = TelemetryLog.objects.create(
            vehicle=unassigned_vehicle, obu_serial='OBU-2', timestamp='2025-07-12T00:00:00Z',
            speed=10, engine_temperature=90, battery_voltage=12, fuel_level=50,
            latitude=0, longitude=0, odometer=10, raw_payload={},
        )
        mail.outbox = []
        violation = dict(
            VIOLATION, rule_id=self.rule.id, telemetry_log_id=log.id, vehicle_id='veh_alert_unassigned',
        )
        AlertService.create_from_violation(violation)
        self.assertEqual(len(mail.outbox), 0)


class DeadLetterQueueTests(AlertsTestBase):
    def test_publish_to_dead_letter_does_not_raise_when_broker_unreachable(self):
        from fleet_monitoring.dead_letter import publish_to_dead_letter

        with override_settings(CELERY_BROKER_URL='amqp://guest:guest@127.0.0.1:1/nonexistent'):
            try:
                publish_to_dead_letter(
                    source_queue='telemetry.raw.process',
                    task_name='telemetry_module.tasks.process_telemetry_packet',
                    payload={'vehicle_id': 'veh_x'},
                    reason='simulated failure',
                )
            except Exception as exc:
                self.fail(f'publish_to_dead_letter raised unexpectedly: {exc}')