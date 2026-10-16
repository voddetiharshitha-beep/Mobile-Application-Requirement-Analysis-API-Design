
import json
import logging

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase
from prometheus_client import generate_latest

from config.metrics import (
    HTTP_REQUESTS,
    HTTP_REQUEST_DURATION,
    HTTP_SERVER_ERRORS,
    NOTIFICATION_EVENTS,
    PrometheusMetricsMiddleware,
    metrics_view,
    record_notification_event,
)
from config.middleware import JSONLogFormatter


class PrometheusMetricsTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_successful_request_increments_request_counter(self):
        counter = HTTP_REQUESTS.labels("GET", "2xx")
        before = counter._value.get()

        request = self.factory.get("/health/live/")
        middleware = PrometheusMetricsMiddleware(
            lambda request: HttpResponse("ok", status=200)
        )

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(counter._value.get(), before + 1)

    def test_server_error_increments_error_counter(self):
        counter = HTTP_SERVER_ERRORS.labels("GET")
        before = counter._value.get()

        request = self.factory.get("/test-error/")
        middleware = PrometheusMetricsMiddleware(
            lambda request: HttpResponse("error", status=503)
        )

        response = middleware(request)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(counter._value.get(), before + 1)

    def test_request_duration_is_recorded(self):
        def get_histogram_count():
            for metric in HTTP_REQUEST_DURATION.collect():
                for sample in metric.samples:
                    if (
                        sample.name == "http_request_duration_seconds_count"
                        and sample.labels.get("method") == "GET"
                    ):
                        return sample.value
            return 0

        before_count = get_histogram_count()

        request = self.factory.get("/health/live/")
        middleware = PrometheusMetricsMiddleware(
            lambda request: HttpResponse("ok", status=200)
        )

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_histogram_count(), before_count + 1)

        samples = generate_latest().decode("utf-8")
        self.assertIn("http_request_duration_seconds", samples)

    def test_metrics_scrape_is_not_counted_as_application_request(self):
        counter = HTTP_REQUESTS.labels("GET", "2xx")
        before = counter._value.get()

        request = self.factory.get("/metrics/")
        middleware = PrometheusMetricsMiddleware(metrics_view)

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(counter._value.get(), before)
        self.assertIn(
            "http_request_duration_seconds",
            response.content.decode("utf-8"),
        )

    def test_unknown_http_method_uses_bounded_label(self):
        request = self.factory.generic("CUSTOM", "/test/")
        middleware = PrometheusMetricsMiddleware(
            lambda request: HttpResponse("ok", status=200)
        )

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        samples = generate_latest().decode("utf-8")
        self.assertIn('method="OTHER"', samples)

    def test_json_log_formatter_outputs_valid_json(self):
        record = logging.LogRecord(
            name="request",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="HTTP request completed",
            args=(),
            exc_info=None,
        )

        record.request_id = "observability-test-123"
        record.http_method = "GET"
        record.http_path = "/health/live/"
        record.status_code = 200
        record.duration_ms = 4.2

        result = JSONLogFormatter().format(record)
        data = json.loads(result)

        self.assertEqual(data["message"], "HTTP request completed")
        self.assertEqual(data["request_id"], "observability-test-123")
        self.assertEqual(data["status_code"], 200)
        self.assertEqual(data["duration_ms"], 4.2)

    def test_notification_queue_success_metric_increments(self):
        counter = NOTIFICATION_EVENTS.labels("queue", "queued")
        before = counter._value.get()

        record_notification_event("queue", "queued")

        self.assertEqual(counter._value.get(), before + 1)

    def test_notification_queue_failure_metric_increments(self):
        counter = NOTIFICATION_EVENTS.labels("queue", "failed")
        before = counter._value.get()

        record_notification_event("queue", "failed")

        self.assertEqual(counter._value.get(), before + 1)

    def test_notification_processing_outcome_metrics_increment(self):
        created = NOTIFICATION_EVENTS.labels("processing", "created")
        duplicate = NOTIFICATION_EVENTS.labels("processing", "duplicate")

        created_before = created._value.get()
        duplicate_before = duplicate._value.get()

        record_notification_event("processing", "created")
        record_notification_event("processing", "duplicate")

        self.assertEqual(created._value.get(), created_before + 1)
        self.assertEqual(duplicate._value.get(), duplicate_before + 1)

    def test_notification_metrics_use_bounded_labels(self):
        record_notification_event("unrecognized_event", "unrecognized_outcome")

        counter = NOTIFICATION_EVENTS.labels("other", "other")
        self.assertGreaterEqual(counter._value.get(), 1)

        samples = generate_latest().decode("utf-8")
        self.assertIn("notification_events_total", samples)
