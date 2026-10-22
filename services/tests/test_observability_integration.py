from unittest.mock import patch

from django.test import Client, SimpleTestCase

from config.metrics import HTTP_REQUESTS, HTTP_SERVER_ERRORS


class ObservabilityIntegrationTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    def test_health_request_includes_request_id_and_updates_metrics(self):
        counter = HTTP_REQUESTS.labels("GET", "2xx")
        before = counter._value.get()

        response = self.client.get(
            "/health/live/",
            HTTP_X_REQUEST_ID="integration-trace-001",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "alive")
        self.assertEqual(
            response["X-Request-ID"],
            "integration-trace-001",
        )
        self.assertEqual(counter._value.get(), before + 1)

    @patch("services.health_views.connections")
    @patch("services.health_views.cache")
    def test_readiness_failure_includes_request_id_and_updates_error_metrics(
        self, mock_cache, mock_connections
    ):
        mock_connections.__getitem__.side_effect = Exception(
            "Simulated database failure"
        )
        mock_cache.set.return_value = None
        mock_cache.get.return_value = "ok"
        mock_cache.delete.return_value = None

        counter = HTTP_SERVER_ERRORS.labels("GET")
        before = counter._value.get()

        response = self.client.get(
            "/health/ready/",
            HTTP_X_REQUEST_ID="integration-trace-503",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response["X-Request-ID"],
            "integration-trace-503",
        )
        self.assertEqual(
            response.json()["dependencies"]["database"],
            "unavailable",
        )
        self.assertEqual(
            response.json()["dependencies"]["redis"],
            "ok",
        )
        self.assertEqual(counter._value.get(), before + 1)
