from datetime import timedelta

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from alerts_module.services import AlertService
from auth_module.models import User
from rules_module.models import Rule
from telemetry_module.models import TelemetryLog
from vehicles_module.models import Vehicle

from .services import ReportService


class ReportsTestBase(APITestCase):
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
        self.vehicle1 = Vehicle.objects.create(
            vehicle_id='veh_r1', license_plate='R-001', assigned_manager=self.manager,
        )
        self.vehicle2 = Vehicle.objects.create(
            vehicle_id='veh_r2', license_plate='R-002', assigned_manager=self.other_manager,
        )

    def _auth_as(self, username, password='StrongPass123'):
        login = self.client.post(reverse('login'), {'username': username, 'password': password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access_token']}")


class ReportAccessTests(ReportsTestBase):
    def test_admin_can_generate_report(self):
        self._auth_as('admin')
        response = self.client.get(reverse('report-fleet-summary'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_fleet_manager_can_generate_report(self):
        self._auth_as('manager')
        response = self.client.get(reverse('report-fleet-summary'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_driver_cannot_generate_report(self):
        self._auth_as('driveruser')
        response = self.client.get(reverse('report-fleet-summary'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_rejected(self):
        response = self.client.get(reverse('report-fleet-summary'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_date_range_rejected(self):
        self._auth_as('admin')
        response = self.client.get(reverse('report-fleet-summary'), {
            'start_date': '2026-02-01T00:00:00Z', 'end_date': '2026-01-01T00:00:00Z',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ReportScopingTests(ReportsTestBase):
    def test_admin_sees_all_vehicles_in_scope(self):
        self._auth_as('admin')
        response = self.client.get(reverse('report-fleet-summary'))
        self.assertEqual(response.data['vehicle_count'], 2)

    def test_fleet_manager_sees_only_assigned_vehicles(self):
        self._auth_as('manager')
        response = self.client.get(reverse('report-fleet-summary'))
        self.assertEqual(response.data['vehicle_count'], 1)

    def test_vehicle_id_filter_narrows_scope(self):
        self._auth_as('admin')
        response = self.client.get(reverse('report-fleet-summary'), {'vehicle_id': 'veh_r1'})
        self.assertEqual(response.data['vehicle_count'], 1)

    def test_fleet_manager_cannot_see_others_vehicle_via_filter(self):
        self._auth_as('manager')
        response = self.client.get(reverse('report-fleet-summary'), {'vehicle_id': 'veh_r2'})
        self.assertEqual(response.data['vehicle_count'], 0)


class ReportAggregationTests(ReportsTestBase):
    def setUp(self):
        super().setUp()
        now = timezone.now()
        TelemetryLog.objects.create(
            vehicle=self.vehicle1, obu_serial='OBU-1', timestamp=now - timedelta(days=1),
            speed=60, engine_temperature=90, battery_voltage=12.5, fuel_level=80,
            latitude=0, longitude=0, odometer=1000, raw_payload={},
        )
        TelemetryLog.objects.create(
            vehicle=self.vehicle1, obu_serial='OBU-1', timestamp=now,
            speed=80, engine_temperature=95, battery_voltage=12.5, fuel_level=70,
            latitude=0, longitude=0, odometer=1050, raw_payload={},
        )

        self.rule = Rule.objects.create(
            name='High temp', metric='engine_temperature', operator='gt', threshold=999,
            severity='high', created_by=self.admin,
        )
        violation = {
            'rule_id': self.rule.id, 'rule_name': self.rule.name, 'metric': 'engine_temperature',
            'operator': 'gt', 'threshold': 999, 'value': 1000, 'severity': 'critical',
            'vehicle_id': 'veh_r1', 'telemetry_log_id': None,
        }
        self.alert = AlertService.create_from_violation(violation)

    def test_telemetry_aggregation(self):
        report = ReportService.generate_fleet_summary(self.admin, vehicle_id='veh_r1')
        self.assertEqual(report['telemetry']['total_readings'], 2)
        self.assertEqual(report['telemetry']['avg_speed'], 70.0)
        self.assertEqual(report['telemetry']['distance_traveled_km'], 50.0)

    def test_alert_aggregation(self):
        report = ReportService.generate_fleet_summary(self.admin, vehicle_id='veh_r1')
        self.assertEqual(report['alerts']['total'], 1)
        self.assertEqual(report['alerts']['by_severity'], {'critical': 1})
        self.assertEqual(report['alerts']['unacknowledged'], 1)
        self.assertIsNone(report['alerts']['avg_acknowledgment_time_seconds'])

    def test_acknowledgment_time_measured(self):
        AlertService.acknowledge(self.manager, self.alert.id)
        report = ReportService.generate_fleet_summary(self.admin, vehicle_id='veh_r1')
        self.assertEqual(report['alerts']['acknowledged'], 1)
        self.assertIsNotNone(report['alerts']['avg_acknowledgment_time_seconds'])
        self.assertGreaterEqual(report['alerts']['avg_acknowledgment_time_seconds'], 0)

    def test_date_range_excludes_out_of_window_data(self):
        old_start = timezone.now() - timedelta(days=100)
        old_end = timezone.now() - timedelta(days=90)
        report = ReportService.generate_fleet_summary(
            self.admin, start_date=old_start, end_date=old_end, vehicle_id='veh_r1',
        )
        self.assertEqual(report['telemetry']['total_readings'], 0)
        self.assertEqual(report['alerts']['total'], 0)