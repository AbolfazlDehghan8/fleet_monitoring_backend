from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from auth_module.models import User
from vehicles_module.models import Driver, Vehicle

from .models import TelemetryLog
from .services import TelemetryService

VALID_PACKET = {
    'vehicle_id': 'veh_8a3f2b1c',
    'obu_serial': 'OBU-2024-0001',
    'timestamp': '2025-07-11T14:32:01.234Z',
    'speed': 72.5,
    'engine_temperature': 91.2,
    'battery_voltage': 12.8,
    'fuel_level': 67.3,
    'latitude': 40.7128,
    'longitude': -74.0060,
    'odometer': 145230.7,
}


class TelemetryTestBase(APITestCase):
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
            vehicle_id='veh_8a3f2b1c', license_plate='ABC-123', assigned_manager=self.manager, driver=self.driver
        )

    def _auth_as(self, username, password='StrongPass123'):
        login = self.client.post(reverse('login'), {'username': username, 'password': password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access_token']}")


class TelemetryIngestTests(TelemetryTestBase):
    def test_driver_can_ingest_own_vehicle_packet(self):
        self._auth_as('driveruser')
        response = self.client.post(reverse('telemetry-ingest-list'), VALID_PACKET, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('dispatch_id', response.data)

    def test_fleet_manager_can_ingest_assigned_vehicle_packet(self):
        self._auth_as('manager')
        response = self.client.post(reverse('telemetry-ingest-list'), VALID_PACKET, format='json')
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    def test_fleet_manager_cannot_ingest_unassigned_vehicle_packet(self):
        self._auth_as('manager2')
        response = self.client.post(reverse('telemetry-ingest-list'), VALID_PACKET, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_vehicle_id_rejected(self):
        self._auth_as('admin')
        packet = dict(VALID_PACKET, vehicle_id='veh_does_not_exist')
        response = self.client.post(reverse('telemetry-ingest-list'), packet, format='json')
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_out_of_range_battery_voltage_rejected(self):
        self._auth_as('admin')
        packet = dict(VALID_PACKET, battery_voltage=999)
        response = self.client.post(reverse('telemetry-ingest-list'), packet, format='json')
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_out_of_range_fuel_level_rejected(self):
        self._auth_as('admin')
        packet = dict(VALID_PACKET, fuel_level=150)
        response = self.client.post(reverse('telemetry-ingest-list'), packet, format='json')
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_missing_field_rejected(self):
        self._auth_as('admin')
        packet = dict(VALID_PACKET)
        del packet['speed']
        response = self.client.post(reverse('telemetry-ingest-list'), packet, format='json')
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_oversized_packet_rejected(self):
        self._auth_as('admin')
        packet = dict(VALID_PACKET, obu_serial='X' * 3000)
        response = self.client.post(reverse('telemetry-ingest-list'), packet, format='json')
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_unauthenticated_request_rejected(self):
        response = self.client.post(reverse('telemetry-ingest-list'), VALID_PACKET, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TelemetryPersistenceTests(TelemetryTestBase):
    def test_persist_creates_log_and_cache_entry(self):
        TelemetryService.persist_packet(VALID_PACKET)
        self.assertEqual(TelemetryLog.objects.count(), 1)
        cached = cache.get(f'fleet:vehicle:{self.vehicle.id}:telemetry')
        self.assertIsNotNone(cached)
        self.assertEqual(cached['vehicle_id'], 'veh_8a3f2b1c')

    def test_duplicate_packet_is_idempotent_noop(self):
        TelemetryService.persist_packet(VALID_PACKET)
        TelemetryService.persist_packet(VALID_PACKET)
        self.assertEqual(TelemetryLog.objects.count(), 1)

    def test_persist_triggers_rule_evaluation(self):
        with patch('rules_module.services.RuleService.evaluate') as mock_evaluate:
            TelemetryService.persist_packet(VALID_PACKET)
            self.assertTrue(mock_evaluate.called)
            log_arg = mock_evaluate.call_args[0][0]
            self.assertEqual(log_arg.vehicle.vehicle_id, VALID_PACKET['vehicle_id'])

    def test_telemetry_log_cannot_be_updated(self):
        TelemetryService.persist_packet(VALID_PACKET)
        log = TelemetryLog.objects.first()
        log.speed = 999
        with self.assertRaises(Exception):
            log.save()

    def test_telemetry_log_cannot_be_deleted(self):
        TelemetryService.persist_packet(VALID_PACKET)
        log = TelemetryLog.objects.first()
        with self.assertRaises(Exception):
            log.delete()


class TelemetryReadTests(TelemetryTestBase):
    def setUp(self):
        super().setUp()
        TelemetryService.persist_packet(VALID_PACKET)

    def test_admin_can_list_all_telemetry(self):
        self._auth_as('admin')
        response = self.client.get(reverse('telemetry-ingest-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_fleet_manager_sees_only_assigned_vehicle_telemetry(self):
        self._auth_as('manager2')
        response = self.client.get(reverse('telemetry-ingest-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_driver_cannot_use_general_list_endpoint(self):
        self._auth_as('driveruser')
        response = self.client.get(reverse('telemetry-ingest-list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_driver_sees_own_vehicle_via_me_endpoint(self):
        self._auth_as('driveruser')
        response = self.client.get(reverse('telemetry-me'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class TelemetryRetentionAndHealthCheckTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.manager = User.objects.create_user(
            username='fm_ret', email='fm_ret@example.com', password='StrongPass123', role='fleet_manager'
        )
        self.vehicle = Vehicle.objects.create(
            vehicle_id='veh_retention', license_plate='RET-001', assigned_manager=self.manager,
        )

    def test_cleanup_old_telemetry_deletes_only_expired_rows(self):
        from datetime import timedelta

        from django.utils import timezone

        from .tasks import cleanup_old_telemetry

        old_log = TelemetryLog.objects.create(
            vehicle=self.vehicle, obu_serial='OBU-OLD',
            timestamp=timezone.now() - timedelta(days=400),
            speed=10, engine_temperature=80, battery_voltage=12, fuel_level=50,
            latitude=0, longitude=0, odometer=1, raw_payload={},
        )
        recent_log = TelemetryLog.objects.create(
            vehicle=self.vehicle, obu_serial='OBU-NEW',
            timestamp=timezone.now(),
            speed=10, engine_temperature=80, battery_voltage=12, fuel_level=50,
            latitude=0, longitude=0, odometer=2, raw_payload={},
        )

        deleted_count = cleanup_old_telemetry()

        self.assertEqual(deleted_count, 1)
        self.assertFalse(TelemetryLog.objects.filter(id=old_log.id).exists())
        self.assertTrue(TelemetryLog.objects.filter(id=recent_log.id).exists())

    def test_system_health_check_reports_database_and_cache_ok(self):
        from .tasks import system_health_check

        health = system_health_check()
        self.assertTrue(health['database'])
        self.assertTrue(health['cache'])