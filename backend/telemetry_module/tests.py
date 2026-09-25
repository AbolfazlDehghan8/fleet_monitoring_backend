from datetime import datetime, timedelta, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.db import OperationalError, connection
from django.db.models import ProtectedError
from django.test import SimpleTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase

from auth_module.models import User
from vehicles_module.models import OBU, Company, Driver, Vehicle

from .models import TelemetryLog
from .services import PacketRejected, TelemetryService, VehicleNotFound
from .tasks import (
    _backoff_seconds,
    _list_partitions,
    cleanup_old_telemetry,
    ensure_future_telemetry_partitions,
    process_telemetry_packet,
    system_health_check,
)
from .views import TelemetryIngestView

LOCMEM_CACHE = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


def valid_packet(seconds_ago=30, **overrides):
    packet = {
        'vehicle_id': 'veh_8a3f2b1c',
        'obu_serial': 'OBU-2024-0001',
        'timestamp': (timezone.now() - timedelta(seconds=seconds_ago)).isoformat(),
        'speed': 72.5,
        'engine_temperature': 91.2,
        'battery_voltage': 12.8,
        'fuel_level': 67.3,
        'latitude': 40.7128,
        'longitude': -74.0060,
        'odometer': 145230.7,
    }
    packet.update(overrides)
    return packet


def _log_kwargs(vehicle, when, **extra):
    fields = dict(
        vehicle=vehicle, obu_serial='OBU-2020-0001', timestamp=when, speed=10, engine_temperature=80,
        battery_voltage=12, fuel_level=50, latitude=0, longitude=0, odometer=1, raw_payload={},
    )
    fields.update(extra)
    return fields


@override_settings(CACHES=LOCMEM_CACHE)
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
        self.company = Company.objects.create(name='Telemetry Test Co')
        self.vehicle = Vehicle.objects.create(
            vehicle_id='veh_8a3f2b1c', license_plate='12ب12345', assigned_manager=self.manager,
            driver=self.driver, company=self.company,
        )

    def _auth_as(self, username, password='StrongPass123'):
        login = self.client.post(reverse('login'), {'username': username, 'password': password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access_token']}")


class TelemetryIngestTests(TelemetryTestBase):
    def setUp(self):
        super().setUp()
        patcher = patch(
            'telemetry_module.tasks.process_telemetry_packet.apply_async',
            return_value=SimpleNamespace(id='task-123'),
        )
        self.mock_dispatch = patcher.start()
        self.addCleanup(patcher.stop)
        self.url = reverse('telemetry-ingest-list')

    def _post(self, packet=None):
        return self.client.post(self.url, packet or valid_packet(), format='json')

    def test_driver_can_ingest_own_vehicle_packet(self):
        self._auth_as('driveruser')
        response = self._post()
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['dispatch_id'], 'task-123')

    def test_fleet_manager_can_ingest_assigned_vehicle_packet(self):
        self._auth_as('manager')
        self.assertEqual(self._post().status_code, status.HTTP_202_ACCEPTED)

    def test_fleet_manager_cannot_ingest_unassigned_vehicle_packet(self):
        self._auth_as('manager2')
        self.assertEqual(self._post().status_code, status.HTTP_403_FORBIDDEN)
        self.mock_dispatch.assert_not_called()

    def test_deactivated_driver_cannot_ingest(self):
        Driver.objects.filter(pk=self.driver.pk).update(is_active=False)
        self._auth_as('driveruser')
        self.assertEqual(self._post().status_code, status.HTTP_403_FORBIDDEN)

    def test_unknown_vehicle_id_rejected(self):
        self._auth_as('admin')
        response = self._post(valid_packet(vehicle_id='veh_does_not_exist'))
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn('vehicle_id', response.data)

    def test_decommissioned_vehicle_rejected(self):
        Vehicle.objects.filter(pk=self.vehicle.pk).update(status='decommissioned')
        self._auth_as('admin')
        self.assertEqual(self._post().status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_out_of_range_battery_voltage_rejected(self):
        self._auth_as('admin')
        self.assertEqual(self._post(valid_packet(battery_voltage=999)).status_code, 422)

    def test_out_of_range_fuel_level_rejected(self):
        self._auth_as('admin')
        self.assertEqual(self._post(valid_packet(fuel_level=150)).status_code, 422)

    def test_missing_field_rejected(self):
        self._auth_as('admin')
        packet = valid_packet()
        del packet['speed']
        self.assertEqual(self._post(packet).status_code, 422)

    def test_oversized_packet_rejected(self):
        self._auth_as('admin')
        response = self._post(valid_packet(obu_serial='X' * 3000))
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.mock_dispatch.assert_not_called()

    def test_unauthenticated_request_rejected(self):
        self.assertEqual(self._post().status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nan_and_infinity_are_rejected(self):
        self._auth_as('admin')
        for bad in ('nan', 'NaN', 'inf', '-Infinity'):
            response = self._post(valid_packet(speed=bad))
            self.assertEqual(response.status_code, 422, bad)
            self.assertIn('speed', response.data)
        self.mock_dispatch.assert_not_called()

    def test_future_timestamp_rejected_but_small_clock_drift_tolerated(self):
        self._auth_as('admin')
        far_future = (timezone.now() + timedelta(days=30)).isoformat()
        response = self._post(valid_packet(timestamp=far_future))
        self.assertEqual(response.status_code, 422)
        self.assertIn('timestamp', response.data)

        drift = (timezone.now() + timedelta(seconds=2)).isoformat()
        self.assertEqual(self._post(valid_packet(timestamp=drift)).status_code, 202)

    def test_timestamp_older_than_retention_rejected(self):
        self._auth_as('admin')
        too_old = (timezone.now() - timedelta(days=400)).isoformat()
        self.assertEqual(self._post(valid_packet(timestamp=too_old)).status_code, 422)

    def test_obu_serial_must_match_registered_obu(self):
        OBU.objects.create(vehicle=self.vehicle, serial_number='OBU-2024-0001')
        self._auth_as('admin')
        response = self._post(valid_packet(obu_serial='OBU-2024-9999'))
        self.assertEqual(response.status_code, 422)
        self.assertIn('obu_serial', response.data)

    def test_obu_serial_is_matched_case_insensitively(self):
        OBU.objects.create(vehicle=self.vehicle, serial_number='OBU-2024-0001')
        self._auth_as('admin')
        self.assertEqual(self._post(valid_packet(obu_serial='obu-2024-0001')).status_code, 202)

    def test_queued_message_carries_iso_timestamp_and_correlation_id(self):
        self._auth_as('admin')
        self._post()
        kwargs = self.mock_dispatch.call_args.kwargs
        packet = kwargs['args'][0]
        self.assertEqual(kwargs['queue'], 'telemetry.raw.process')
        self.assertIsInstance(packet['timestamp'], str)
        self.assertIn('correlation_id', packet)

    def test_broker_outage_returns_503_with_retry_after(self):
        self.mock_dispatch.side_effect = ConnectionError('rabbitmq down')
        self._auth_as('admin')
        with self.assertLogs('fleet_monitoring.cache_degradation', level='ERROR'):
            response = self._post()
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response['Retry-After'], '5')

    def test_hot_path_does_not_query_vehicles_per_packet(self):
        self._auth_as('admin')
        self._post()
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self._post(valid_packet(seconds_ago=20)).status_code, 202)
        self.assertLessEqual(len(queries), 1, [q['sql'] for q in queries])

    def test_vehicle_cache_is_refreshed_when_vehicle_changes(self):
        self._auth_as('admin')
        self.assertEqual(self._post().status_code, 202)
        response = self.client.patch(
            reverse('vehicle-detail', args=[self.vehicle.id]), {'status': 'decommissioned'}, format='json'
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self._post().status_code, 422)

    def test_ingestion_throttle_applies_to_uploads_only(self):
        factory = APIRequestFactory()
        post_view, get_view = TelemetryIngestView(), TelemetryIngestView()
        post_view.request = factory.post('/x/')
        get_view.request = factory.get('/x/')
        self.assertEqual([type(t).__name__ for t in post_view.get_throttles()], ['ScopedRateThrottle'])
        self.assertEqual([type(t).__name__ for t in get_view.get_throttles()], ['UserRateThrottle'])


class TelemetryPersistenceTests(TelemetryTestBase):
    def test_persist_creates_log_and_cache_entry(self):
        packet = valid_packet()
        log = TelemetryService.persist_packet(packet)
        self.assertEqual(TelemetryLog.objects.count(), 1)
        self.assertIsInstance(log.timestamp, datetime)
        self.assertIsNotNone(log.id)
        cached = cache.get(f'fleet:vehicle:{self.vehicle.id}:telemetry')
        self.assertEqual(cached['vehicle_id'], 'veh_8a3f2b1c')

    def test_duplicate_packet_is_idempotent_noop(self):
        packet = valid_packet()
        self.assertIsNotNone(TelemetryService.persist_packet(packet))
        self.assertIsNone(TelemetryService.persist_packet(packet))
        self.assertEqual(TelemetryLog.objects.count(), 1)

    def test_duplicate_does_not_evaluate_rules_twice(self):
        packet = valid_packet()
        with patch('rules_module.services.RuleService.evaluate') as mock_evaluate:
            TelemetryService.persist_packet(packet)
            TelemetryService.persist_packet(packet)
        self.assertEqual(mock_evaluate.call_count, 1)

    def test_persist_triggers_rule_evaluation(self):
        with patch('rules_module.services.RuleService.evaluate') as mock_evaluate:
            TelemetryService.persist_packet(valid_packet())
            self.assertTrue(mock_evaluate.called)
            log_arg = mock_evaluate.call_args[0][0]
            self.assertEqual(log_arg.vehicle.vehicle_id, 'veh_8a3f2b1c')

    def test_rule_engine_failure_does_not_fail_or_lose_the_packet(self):
        with patch('rules_module.services.RuleService.evaluate', side_effect=RuntimeError('boom')):
            with self.assertLogs('audit', level='ERROR'):
                log = TelemetryService.persist_packet(valid_packet())
        self.assertIsNotNone(log)
        self.assertEqual(TelemetryLog.objects.count(), 1)

    def test_out_of_order_packet_does_not_overwrite_newer_live_data(self):
        newer = valid_packet(seconds_ago=10, speed=100)
        older = valid_packet(seconds_ago=60, speed=20)
        TelemetryService.persist_packet(newer)
        TelemetryService.persist_packet(older)
        self.assertEqual(TelemetryLog.objects.count(), 2)
        cached = cache.get(f'fleet:vehicle:{self.vehicle.id}:telemetry')
        self.assertEqual(cached['speed'], 100)

    def test_newer_packet_replaces_older_live_data(self):
        TelemetryService.persist_packet(valid_packet(seconds_ago=60, speed=20))
        TelemetryService.persist_packet(valid_packet(seconds_ago=10, speed=100))
        self.assertEqual(cache.get(f'fleet:vehicle:{self.vehicle.id}:telemetry')['speed'], 100)

    def test_persist_needs_one_query_once_the_vehicle_is_cached(self):
        with patch('rules_module.services.RuleService.evaluate'):
            TelemetryService.persist_packet(valid_packet(seconds_ago=60))
            with CaptureQueriesContext(connection) as queries:
                TelemetryService.persist_packet(valid_packet(seconds_ago=30))
        self.assertEqual(len(queries), 1, [q['sql'] for q in queries])

    def test_unknown_vehicle_is_a_permanent_failure(self):
        with self.assertRaises(VehicleNotFound):
            TelemetryService.persist_packet(valid_packet(vehicle_id='veh_gone'))

    def test_nan_payload_is_rejected_before_touching_the_database(self):
        with self.assertRaises(ValueError):
            TelemetryService.persist_packet(valid_packet(speed=float('nan')))
        self.assertEqual(TelemetryLog.objects.count(), 0)

    def test_naive_timestamp_is_rejected(self):
        with self.assertRaises(PacketRejected):
            TelemetryService.persist_packet(valid_packet(timestamp='2026-01-01T10:00:00'))

    def test_telemetry_log_cannot_be_updated(self):
        TelemetryService.persist_packet(valid_packet())
        log = TelemetryLog.objects.first()
        log.speed = 999
        with self.assertRaises(Exception):
            log.save()

    def test_telemetry_log_cannot_be_deleted(self):
        TelemetryService.persist_packet(valid_packet())
        with self.assertRaises(Exception):
            TelemetryLog.objects.first().delete()

    def test_bulk_update_and_delete_are_blocked_too(self):
        TelemetryService.persist_packet(valid_packet())
        with self.assertRaises(Exception):
            TelemetryLog.objects.all().update(speed=1)
        with self.assertRaises(Exception):
            TelemetryLog.objects.all().delete()
        self.assertEqual(TelemetryLog.objects.count(), 1)

    def test_vehicle_with_telemetry_cannot_be_deleted_even_from_the_orm(self):
        TelemetryService.persist_packet(valid_packet())
        with self.assertRaises(ProtectedError):
            self.vehicle.delete()


class TelemetryReadTests(TelemetryTestBase):
    def setUp(self):
        super().setUp()
        TelemetryService.persist_packet(valid_packet(seconds_ago=120))
        TelemetryService.persist_packet(valid_packet(seconds_ago=60))

    def test_admin_can_list_all_telemetry(self):
        self._auth_as('admin')
        response = self.client.get(reverse('telemetry-ingest-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        timestamps = [row['timestamp'] for row in response.data]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_fleet_manager_sees_only_assigned_vehicle_telemetry(self):
        self._auth_as('manager2')
        self.assertEqual(len(self.client.get(reverse('telemetry-ingest-list')).data), 0)
        self._auth_as('manager')
        self.assertEqual(len(self.client.get(reverse('telemetry-ingest-list')).data), 2)

    def test_driver_cannot_use_general_list_endpoint(self):
        self._auth_as('driveruser')
        self.assertEqual(self.client.get(reverse('telemetry-ingest-list')).status_code, 403)

    def test_driver_sees_own_vehicle_via_me_endpoint(self):
        self._auth_as('driveruser')
        response = self.client.get(reverse('telemetry-me'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_deactivated_driver_sees_nothing(self):
        Driver.objects.filter(pk=self.driver.pk).update(is_active=False)
        self._auth_as('driveruser')
        self.assertEqual(len(self.client.get(reverse('telemetry-me')).data), 0)

    def test_limit_and_time_window_filters(self):
        self._auth_as('admin')
        url = reverse('telemetry-ingest-list')
        self.assertEqual(len(self.client.get(url, {'limit': 1}).data), 1)
        recent = (timezone.now() - timedelta(seconds=90)).isoformat()
        self.assertEqual(len(self.client.get(url, {'start': recent}).data), 1)
        self.assertEqual(len(self.client.get(url, {'vehicle_id': 'nope'}).data), 0)

    def test_invalid_query_parameters_are_400(self):
        self._auth_as('admin')
        url = reverse('telemetry-ingest-list')
        self.assertEqual(self.client.get(url, {'limit': 0}).status_code, 400)
        self.assertEqual(self.client.get(url, {'limit': 9999}).status_code, 400)
        later, earlier = timezone.now().isoformat(), (timezone.now() - timedelta(hours=1)).isoformat()
        self.assertEqual(self.client.get(url, {'start': later, 'end': earlier}).status_code, 400)


class ProcessTelemetryTaskTests(TelemetryTestBase):
    def _packet(self):
        return dict(valid_packet(), correlation_id='corr-1')

    def test_permanent_failure_goes_to_dead_letter_and_is_not_retried(self):
        with patch('telemetry_module.tasks.publish_to_dead_letter') as dlq:
            with self.assertRaises(VehicleNotFound):
                process_telemetry_packet.apply(args=[dict(self._packet(), vehicle_id='veh_gone')])
        dlq.assert_called_once()
        self.assertIn('Non-retryable', dlq.call_args.kwargs['reason'])
        self.assertEqual(dlq.call_args.kwargs['source_queue'], 'telemetry.raw.process')

    def test_exhausted_retries_dead_letter_the_packet_instead_of_losing_it(self):
        with patch('telemetry_module.tasks.TelemetryService.persist_packet',
                   side_effect=OperationalError('db down')) as persist, \
                patch('telemetry_module.tasks.publish_to_dead_letter') as dlq:
            with self.assertRaises(OperationalError):
                process_telemetry_packet.apply(args=[self._packet()], retries=process_telemetry_packet.max_retries)
        self.assertEqual(persist.call_count, 1)
        dlq.assert_called_once()
        self.assertIn('Retries exhausted', dlq.call_args.kwargs['reason'])
        self.assertEqual(dlq.call_args.kwargs['payload']['packet_data']['vehicle_id'], 'veh_8a3f2b1c')

    def test_successful_processing_persists_the_packet(self):
        with patch('rules_module.services.RuleService.evaluate'):
            process_telemetry_packet.apply(args=[self._packet()])
        self.assertEqual(TelemetryLog.objects.count(), 1)

    def test_correlation_id_is_not_stored_in_the_payload(self):
        with patch('rules_module.services.RuleService.evaluate'):
            process_telemetry_packet.apply(args=[self._packet()])
        self.assertNotIn('correlation_id', TelemetryLog.objects.get().raw_payload)


class BackoffTests(SimpleTestCase):
    def test_backoff_grows_and_is_capped(self):
        delays = [_backoff_seconds(n) for n in range(0, 10)]
        self.assertTrue(5 <= delays[0] <= 10)
        self.assertTrue(10 <= delays[1] <= 15)
        self.assertTrue(all(d <= 305 for d in delays))


@override_settings(CACHES=LOCMEM_CACHE)
class TelemetryRetentionAndPartitionTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.manager = User.objects.create_user(
            username='fm_ret', email='fm_ret@example.com', password='StrongPass123', role='fleet_manager'
        )
        self.company = Company.objects.create(name='Retention Test Co')
        self.vehicle = Vehicle.objects.create(
            vehicle_id='veh_retention', license_plate='12ب54321', assigned_manager=self.manager,
            company=self.company,
        )

    def test_cleanup_old_telemetry_deletes_only_expired_rows(self):
        old_log = TelemetryLog.objects.create(**_log_kwargs(self.vehicle, timezone.now() - timedelta(days=400)))
        recent_log = TelemetryLog.objects.create(**_log_kwargs(self.vehicle, timezone.now(), odometer=2))

        deleted_count = cleanup_old_telemetry()

        self.assertEqual(deleted_count, 1)
        self.assertFalse(TelemetryLog.objects.filter(id=old_log.id).exists())
        self.assertTrue(TelemetryLog.objects.filter(id=recent_log.id).exists())

    def test_expired_monthly_partition_is_dropped_wholesale(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE telemetry_logs_2020_01 PARTITION OF telemetry_logs "
                "FOR VALUES FROM ('2020-01-01') TO ('2020-02-01')"
            )
        TelemetryLog.objects.create(**_log_kwargs(self.vehicle, datetime(2020, 1, 15, tzinfo=dt_timezone.utc)))
        self.assertEqual(TelemetryLog.objects.count(), 1)
        current = f'telemetry_logs_{timezone.now():%Y_%m}'

        cleanup_old_telemetry()

        with connection.cursor() as cursor:
            partitions = _list_partitions(cursor)
        self.assertNotIn('telemetry_logs_2020_01', partitions)
        self.assertIn(current, partitions)
        self.assertEqual(TelemetryLog.objects.count(), 0)

    def test_retention_always_keeps_at_least_the_configured_days(self):
        keep = TelemetryLog.objects.create(**_log_kwargs(self.vehicle, timezone.now() - timedelta(days=30)))
        cleanup_old_telemetry()
        self.assertTrue(TelemetryLog.objects.filter(id=keep.id).exists())

    def test_ensure_partitions_is_idempotent_and_creates_upcoming_months(self):
        first = ensure_future_telemetry_partitions(months_ahead=15)
        second = ensure_future_telemetry_partitions(months_ahead=15)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 16)
        with connection.cursor() as cursor:
            partitions = _list_partitions(cursor)
        self.assertTrue(set(first) <= partitions)

    def test_rows_stuck_in_default_partition_are_reported(self):
        TelemetryLog.objects.create(**_log_kwargs(self.vehicle, timezone.now() - timedelta(days=900)))
        with self.assertLogs('audit', level='WARNING') as captured:
            ensure_future_telemetry_partitions(months_ahead=1)
        self.assertTrue(any('telemetry_default_partition_has_rows' in line for line in captured.output))

    def test_system_health_check_reports_database_and_cache_ok(self):
        health = system_health_check()
        self.assertTrue(health['database'])
        self.assertTrue(health['cache'])