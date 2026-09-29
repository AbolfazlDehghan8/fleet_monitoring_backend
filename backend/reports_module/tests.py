from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from alerts_module.services import AlertService
from auth_module.models import User
from rules_module.models import Rule
from telemetry_module.models import TelemetryLog
from vehicles_module.models import Company, Vehicle

from .models import Report
from .services import ReportService
from .tasks import generate_report_task, generate_scheduled_fleet_report


LOCMEM_CACHE = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


@override_settings(CACHES=LOCMEM_CACHE)
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
        self.company = Company.objects.create(name='Reports Test Co')
        self.vehicle1 = Vehicle.objects.create(
            vehicle_id='veh_r1', license_plate='12ب11111', assigned_manager=self.manager,
            company=self.company,
        )
        self.vehicle2 = Vehicle.objects.create(
            vehicle_id='veh_r2', license_plate='12ب22222', assigned_manager=self.other_manager,
            company=self.company,
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
            vehicle=self.vehicle1, obu_serial='OBU-2026-0001', timestamp=now - timedelta(days=1),
            speed=60, engine_temperature=90, battery_voltage=12.5, fuel_level=80,
            latitude=0, longitude=0, odometer=1000, raw_payload={},
        )
        TelemetryLog.objects.create(
            vehicle=self.vehicle1, obu_serial='OBU-2026-0001', timestamp=now,
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
            'vehicle_pk': self.vehicle1.id, 'vehicle_id': 'veh_r1', 'telemetry_log_id': None,
        }
        with patch('alerts_module.tasks.dispatch_alert_notification.apply_async'):
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
        AlertService.acknowledge(self.admin, self.alert.id)
        report = ReportService.generate_fleet_summary(self.admin, vehicle_id='veh_r1')
        self.assertEqual(report['alerts']['acknowledged'], 1)
        self.assertIsNotNone(report['alerts']['avg_acknowledgment_time_seconds'])
        self.assertGreaterEqual(report['alerts']['avg_acknowledgment_time_seconds'], 0)

    def test_acknowledgments_are_counted_per_requesting_user(self):
        AlertService.acknowledge(self.manager, self.alert.id)
        admin_report = ReportService.generate_fleet_summary(self.admin, vehicle_id='veh_r1')
        manager_report = ReportService.generate_fleet_summary(self.manager, vehicle_id='veh_r1')
        self.assertEqual(admin_report['alerts']['acknowledged'], 0)
        self.assertEqual(admin_report['alerts']['unacknowledged'], 1)
        self.assertEqual(manager_report['alerts']['acknowledged'], 1)
        self.assertEqual(manager_report['alerts']['unacknowledged'], 0)

    def test_date_range_excludes_out_of_window_data(self):
        old_start = timezone.now() - timedelta(days=100)
        old_end = timezone.now() - timedelta(days=90)
        report = ReportService.generate_fleet_summary(
            self.admin, start_date=old_start, end_date=old_end, vehicle_id='veh_r1',
        )
        self.assertEqual(report['telemetry']['total_readings'], 0)
        self.assertEqual(report['alerts']['total'], 0)


class AsyncReportGenerationTests(ReportsTestBase):
    def test_generate_queues_report_and_completes_synchronously_in_eager_mode(self):
        self._auth_as('admin')
        response = self.client.post(reverse('report-generate'), {})
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        report_id = response.data['id']

        detail = self.client.get(reverse('report-detail', args=[report_id]))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data['status'], 'completed')
        self.assertIn('vehicles_by_status', detail.data['result'])

    def test_manager_cannot_view_another_managers_requested_report(self):
        self._auth_as('manager')
        response = self.client.post(reverse('report-generate'), {})
        report_id = response.data['id']

        self._auth_as('manager2')
        detail = self.client.get(reverse('report-detail', args=[report_id]))
        self.assertEqual(detail.status_code, status.HTTP_403_FORBIDDEN)

    def test_export_returns_csv_for_completed_report(self):
        self._auth_as('admin')
        response = self.client.post(reverse('report-generate'), {})
        report_id = response.data['id']

        export = self.client.get(reverse('report-export', args=[report_id]))
        self.assertEqual(export.status_code, status.HTTP_200_OK)
        self.assertEqual(export['Content-Type'], 'text/csv')
        self.assertIn(b'vehicle_count', export.content)

    def test_export_rejected_when_report_not_yet_completed(self):
        report = Report.objects.create(requested_by=self.admin, status=Report.Status.PENDING)
        self._auth_as('admin')
        export = self.client.get(reverse('report-export', args=[report.id]))
        self.assertEqual(export.status_code, status.HTTP_400_BAD_REQUEST)

    def test_scheduled_report_task_creates_system_wide_report(self):
        generate_scheduled_fleet_report()
        report = Report.objects.latest('created_at')
        self.assertIsNone(report.requested_by)
        self.assertEqual(report.status, Report.Status.COMPLETED)
        self.assertEqual(report.result['vehicle_count'], 2)

    def test_scheduled_report_result_shape_matches_user_generated_report(self):
        generate_scheduled_fleet_report()
        report = Report.objects.latest('created_at')

        self.assertIn('telemetry', report.result)
        for key in ('total_readings', 'avg_speed', 'avg_fuel_level', 'distance_traveled_km'):
            self.assertIn(key, report.result['telemetry'])

        for key in ('total', 'by_severity', 'acknowledged', 'unacknowledged', 'avg_acknowledgment_time_seconds'):
            self.assertIn(key, report.result['alerts'])


class ReportDeletionTests(ReportsTestBase):
    def test_owner_can_delete_own_report(self):
        self._auth_as('manager')
        create = self.client.post(reverse('report-generate'), {})
        report_id = create.data['id']

        delete = self.client.delete(reverse('report-detail', args=[report_id]))
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)

        detail = self.client.get(reverse('report-detail', args=[report_id]))
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_manager_cannot_delete_another_managers_report(self):
        self._auth_as('manager')
        create = self.client.post(reverse('report-generate'), {})
        report_id = create.data['id']

        self._auth_as('manager2')
        delete = self.client.delete(reverse('report-detail', args=[report_id]))
        self.assertEqual(delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_delete_any_report(self):
        self._auth_as('manager')
        create = self.client.post(reverse('report-generate'), {})
        report_id = create.data['id']

        self._auth_as('admin')
        delete = self.client.delete(reverse('report-detail', args=[report_id]))
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)

    def test_deleting_missing_report_returns_404(self):
        self._auth_as('admin')
        delete = self.client.delete(reverse('report-detail', args=[999999]))
        self.assertEqual(delete.status_code, status.HTTP_404_NOT_FOUND)

    def test_deleted_report_disappears_from_list(self):
        self._auth_as('manager')
        create = self.client.post(reverse('report-generate'), {})
        report_id = create.data['id']
        self.client.delete(reverse('report-detail', args=[report_id]))

        listing = self.client.get(reverse('report-list'))
        self.assertNotIn(report_id, [r['id'] for r in listing.data])


class ReportSequenceNumberTests(ReportsTestBase):
    def test_sequence_numbers_are_gap_free_after_deleting_a_middle_report(self):
        self._auth_as('manager')

        ids = []
        for _ in range(3):
            response = self.client.post(reverse('report-generate'), {})
            ids.append(response.data['id'])
        first_id, second_id, third_id = ids

        listing = self.client.get(reverse('report-list'))
        by_id = {row['id']: row['sequence_number'] for row in listing.data}
        self.assertEqual(by_id[first_id], 1)
        self.assertEqual(by_id[second_id], 2)
        self.assertEqual(by_id[third_id], 3)

        self.client.delete(reverse('report-detail', args=[second_id]))

        listing = self.client.get(reverse('report-list'))
        by_id = {row['id']: row['sequence_number'] for row in listing.data}
        self.assertEqual(by_id[first_id], 1)
        self.assertEqual(by_id[third_id], 2)
        self.assertEqual(sorted(by_id.values()), [1, 2])

        detail = self.client.get(reverse('report-detail', args=[third_id]))
        self.assertEqual(detail.data['sequence_number'], 2)

    def test_sequence_numbers_are_scoped_per_user(self):
        self._auth_as('manager')
        self.client.post(reverse('report-generate'), {})
        self.client.post(reverse('report-generate'), {})

        self._auth_as('manager2')
        response = self.client.post(reverse('report-generate'), {})
        self.assertEqual(response.data['sequence_number'], 1)


class ReportRequesterVisibilityTests(ReportsTestBase):
    def test_admin_list_shows_who_requested_each_report(self):
        self._auth_as('manager')
        self.client.post(reverse('report-generate'), {})

        self._auth_as('admin')
        own = self.client.post(reverse('report-generate'), {})

        listing = self.client.get(reverse('report-list'))
        by_id = {row['id']: row for row in listing.data}

        self.assertEqual(by_id[own.data['id']]['requested_by_username'], 'admin')
        self.assertEqual(by_id[own.data['id']]['requested_by_role'], 'admin')

        manager_report = next(row for row in listing.data if row['requested_by_role'] == 'fleet_manager')
        self.assertEqual(manager_report['requested_by_username'], 'manager')

        detail = self.client.get(reverse('report-detail', args=[manager_report['id']]))
        self.assertEqual(detail.data['requested_by_username'], 'manager')
        self.assertEqual(detail.data['requested_by_role'], 'fleet_manager')

    def test_system_wide_scheduled_report_has_no_requester(self):
        generate_scheduled_fleet_report()

        self._auth_as('admin')
        listing = self.client.get(reverse('report-list'))
        system_report = next(row for row in listing.data if row['requested_by'] is None)
        self.assertIsNone(system_report['requested_by_username'])
        self.assertIsNone(system_report['requested_by_role'])


class ReportWindowLimitTests(ReportsTestBase):
    def test_window_over_the_limit_is_rejected(self):
        self._auth_as('admin')
        end = timezone.now()
        start = end - timedelta(days=400)
        response = self.client.get(reverse('report-fleet-summary'), {
            'start_date': start.isoformat(), 'end_date': end.isoformat(),
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('end_date', response.data)

    def test_window_at_the_limit_is_accepted(self):
        self._auth_as('admin')
        end = timezone.now()
        start = end - timedelta(days=366)
        response = self.client.get(reverse('report-fleet-summary'), {
            'start_date': start.isoformat(), 'end_date': end.isoformat(),
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_window_limit_also_applies_to_async_generation(self):
        self._auth_as('admin')
        end = timezone.now()
        start = end - timedelta(days=400)
        response = self.client.post(reverse('report-generate'), {
            'start_date': start.isoformat(), 'end_date': end.isoformat(),
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_open_ended_range_is_not_limited(self):
        self._auth_as('admin')
        very_old = timezone.now() - timedelta(days=2000)
        response = self.client.get(reverse('report-fleet-summary'), {'start_date': very_old.isoformat()})
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ReportAggregationCorrectnessTests(ReportsTestBase):
    def setUp(self):
        super().setUp()
        for vehicle, status_value in (
            (self.vehicle1, 'active'), (self.vehicle2, 'active'),
        ):
            Vehicle.objects.filter(pk=vehicle.pk).update(status=status_value)
        self.vehicle3 = Vehicle.objects.create(
            vehicle_id='veh_r3', license_plate='12ب33333', company=self.company, status='maintenance',
        )
        self.rule = Rule.objects.create(
            name='Low fuel', metric='fuel_level', operator='lt', threshold=10, severity='medium',
        )
        for severity, count in (('high', 2), ('critical', 1), ('low', 3)):
            for n in range(count):
                with patch('alerts_module.tasks.dispatch_alert_notification.apply_async'):
                    AlertService.create_from_violation({
                        'rule_id': self.rule.id, 'rule_name': 'x', 'metric': 'fuel_level',
                        'operator': 'lt', 'threshold': 10, 'value': 5, 'severity': severity,
                        'vehicle_pk': self.vehicle1.id if n == 0 else self.vehicle2.id,
                        'vehicle_id': 'veh_r1' if n == 0 else 'veh_r2',
                        'telemetry_log_id': None,
                    })

    def test_vehicles_by_status_matches_actual_counts(self):
        self._auth_as('admin')
        response = self.client.get(reverse('report-fleet-summary'))
        self.assertEqual(response.data['vehicles_by_status'], {'active': 2, 'maintenance': 1})
        self.assertEqual(response.data['vehicle_count'], 3)

    def test_alerts_by_severity_matches_actual_counts(self):
        self._auth_as('admin')
        response = self.client.get(reverse('report-fleet-summary'))
        by_severity = response.data['alerts']['by_severity']
        self.assertEqual(sum(by_severity.values()), response.data['alerts']['total'])
        self.assertEqual(
            response.data['alerts']['total'],
            response.data['alerts']['acknowledged'] + response.data['alerts']['unacknowledged'],
        )


class ReportTaskFailureHandlingTests(ReportsTestBase):
    def test_deleted_report_is_not_retried(self):
        report = Report.objects.create(requested_by=self.admin, status=Report.Status.PENDING)
        report_id = report.id
        report.delete()

        with self.assertLogs('audit', level='WARNING') as captured:
            generate_report_task.apply(args=[report_id])
        self.assertTrue(any('report_run_skipped_not_found' in line for line in captured.output))

    def test_permanent_failure_marks_report_failed_and_stores_message(self):
        report = Report.objects.create(requested_by=self.admin, status=Report.Status.PENDING)
        with patch(
            'reports_module.services.ReportService.generate_fleet_summary',
            side_effect=ValueError('boom'),
        ):
            with self.assertRaises(ValueError):
                generate_report_task.apply(args=[report.id], retries=3)
        report.refresh_from_db()
        self.assertEqual(report.status, Report.Status.FAILED)
        self.assertIn('boom', report.error_message)