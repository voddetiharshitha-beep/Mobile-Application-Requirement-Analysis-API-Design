
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.test import Client


class HealthCheckTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    def test_liveness_returns_alive(self):
        response = self.client.get("/health/live/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "alive")

    @patch("services.health_views.connections")
    @patch("services.health_views.cache")
    def test_readiness_returns_503_when_database_fails(
        self, mock_cache, mock_connections
    ):
        mock_connections.__getitem__.side_effect = Exception(
            "Simulated database failure"
        )
        mock_cache.set.return_value = None
        mock_cache.get.return_value = "ok"

        response = self.client.get("/health/ready/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["dependencies"]["database"],
            "unavailable",
        )
        self.assertEqual(
            response.json()["dependencies"]["redis"],
            "ok",
        )

    @patch("services.health_views.cache")
    def test_readiness_returns_503_when_redis_fails(self, mock_cache):
        mock_cache.set.side_effect = Exception(
            "Simulated Redis failure"
        )

        response = self.client.get("/health/ready/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["dependencies"]["redis"],
            "unavailable",
        )

    @patch("services.health_views.connections")
    @patch("services.health_views.cache")
    def test_readiness_returns_503_when_both_fail(
        self, mock_cache, mock_connections
    ):
        mock_connections.__getitem__.side_effect = Exception(
            "Simulated database failure"
        )
        mock_cache.set.side_effect = Exception(
            "Simulated Redis failure"
        )

        response = self.client.get("/health/ready/")

        self.assertEqual(response.status_code, 503)
        dependencies = response.json()["dependencies"]
        self.assertEqual(dependencies["database"], "unavailable")
        self.assertEqual(dependencies["redis"], "unavailable")
