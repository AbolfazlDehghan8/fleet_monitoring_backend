import logging
import uuid
from unittest import mock

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from fleet_monitoring.exceptions import CONFLICT_MESSAGE, api_exception_handler
from fleet_monitoring.persian import is_valid_iran_national_code, normalize_digits, normalize_persian_text
from fleet_monitoring.tracing import trace_span
from fleet_monitoring.validators import iran_national_code_validator

LOCMEM_CACHE = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


@override_settings(CACHES=LOCMEM_CACHE)
class HealthCheckTests(APITestCase):
    def test_health_check_returns_ok(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'ok')
        self.assertEqual(response.data['checks']['database'], 'ok')
        self.assertEqual(response.data['checks']['cache'], 'ok')

    def test_health_check_does_not_require_auth(self):
        response = self.client.get('/health/')
        self.assertNotEqual(response.status_code, 401)

    def test_health_check_does_not_leak_error_details(self):
        with mock.patch('fleet_monitoring.views.connection') as fake_connection:
            fake_connection.cursor.side_effect = Exception('password authentication failed for host db-secret')
            response = self.client.get('/health/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['checks']['database'], 'error')
        self.assertNotIn('db-secret', response.content.decode())


class CorrelationIdMiddlewareTests(APITestCase):
    def test_response_echoes_generated_correlation_id(self):
        response = self.client.get('/health/')
        self.assertIn('X-Request-ID', response)
        self.assertTrue(len(response['X-Request-ID']) > 0)

    def test_response_echoes_supplied_correlation_id(self):
        response = self.client.get('/health/', HTTP_X_REQUEST_ID='test-correlation-123')
        self.assertEqual(response['X-Request-ID'], 'test-correlation-123')

    def test_unsafe_correlation_id_is_replaced(self):
        for bad in ('has spaces', 'x' * 200, '<script>alert(1)</script>'):
            response = self.client.get('/health/', HTTP_X_REQUEST_ID=bad)
            self.assertNotEqual(response['X-Request-ID'], bad)
            uuid.UUID(response['X-Request-ID'])


class MetricsEndpointTests(APITestCase):
    def test_metrics_hidden_without_token_outside_debug(self):
        self.assertEqual(self.client.get('/metrics').status_code, 404)

    @override_settings(METRICS_TOKEN='s3cret')
    def test_metrics_requires_bearer_token(self):
        self.assertEqual(self.client.get('/metrics').status_code, 404)
        self.assertEqual(self.client.get('/metrics', HTTP_AUTHORIZATION='Bearer wrong').status_code, 404)
        self.assertEqual(self.client.get('/metrics', HTTP_AUTHORIZATION='Bearer s3cret').status_code, 200)


class ExceptionHandlerTests(SimpleTestCase):
    def test_django_validation_error_becomes_400_with_same_shape(self):
        response = api_exception_handler(DjangoValidationError({'detail': 'Vehicle not found'}), {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'detail': ['Vehicle not found']})

    def test_integrity_error_becomes_409_without_leaking_sql(self):
        response = api_exception_handler(IntegrityError('duplicate key value violates unique constraint "x"'), {})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data, {'detail': [CONFLICT_MESSAGE]})

    def test_unhandled_exception_is_json_500_in_production(self):
        with override_settings(DEBUG=False), self.assertLogs('audit', level='ERROR'):
            response = api_exception_handler(RuntimeError('boom: internal path /srv/app'), {})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data, {'detail': 'Internal server error'})

    def test_unhandled_exception_propagates_in_debug(self):
        with override_settings(DEBUG=True):
            self.assertIsNone(api_exception_handler(RuntimeError('boom'), {}))


class PersianHelpersTests(SimpleTestCase):
    def test_normalize_digits(self):
        self.assertEqual(normalize_digits('۰۹۱۲۳۴۵۶۷۸۹'), '09123456789')
        self.assertEqual(normalize_digits('٠٩١٢'), '0912')

    def test_normalize_text_fixes_arabic_letters_and_whitespace(self):
        self.assertEqual(normalize_persian_text('  كيان١ '), 'کیان1')

    def test_national_code_checksum(self):
        self.assertTrue(is_valid_iran_national_code('0499370899'))
        self.assertTrue(is_valid_iran_national_code('۰۴۹۹۳۷۰۸۹۹'))
        self.assertFalse(is_valid_iran_national_code('0499370898'))
        self.assertFalse(is_valid_iran_national_code('1111111111'))
        self.assertFalse(is_valid_iran_national_code('12345'))

    def test_national_code_validator_raises(self):
        iran_national_code_validator('0499370899')
        with self.assertRaises(DjangoValidationError):
            iran_national_code_validator('0499370898')


class TraceSpanTests(SimpleTestCase):
    def test_reserved_logrecord_keys_do_not_crash(self):
        with self.assertLogs('audit', level='DEBUG'):
            with trace_span('test.stage', name='x', message='y', vehicle_id='v1'):
                pass

    def test_errors_are_logged_and_reraised(self):
        with self.assertLogs('audit', level=logging.WARNING):
            with self.assertRaises(ValueError):
                with trace_span('test.fail'):
                    raise ValueError('nope')