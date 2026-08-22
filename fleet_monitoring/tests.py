from rest_framework.test import APITestCase


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


class CorrelationIdMiddlewareTests(APITestCase):
    def test_response_echoes_generated_correlation_id(self):
        response = self.client.get('/health/')
        self.assertIn('X-Request-ID', response)
        self.assertTrue(len(response['X-Request-ID']) > 0)

    def test_response_echoes_supplied_correlation_id(self):
        response = self.client.get('/health/', HTTP_X_REQUEST_ID='test-correlation-123')
        self.assertEqual(response['X-Request-ID'], 'test-correlation-123')