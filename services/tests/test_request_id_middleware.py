import uuid

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from config.middleware import RequestIDMiddleware


class RequestIDMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_valid_request_id_is_returned_and_logged(self):
        request = self.factory.get(
            "/health/live/",
            HTTP_X_REQUEST_ID="trace-test-123",
        )
        middleware = RequestIDMiddleware(
            lambda request: HttpResponse("ok", status=200)
        )

        with self.assertLogs("request", level="INFO") as captured:
            response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Request-ID"], "trace-test-123")
        self.assertEqual(request.request_id, "trace-test-123")
        self.assertEqual(len(captured.records), 1)

        record = captured.records[0]
        self.assertEqual(record.http_method, "GET")
        self.assertEqual(record.http_path, "/health/live/")
        self.assertEqual(record.status_code, 200)
        self.assertGreaterEqual(record.duration_ms, 0)

    def test_invalid_request_id_is_replaced_with_uuid(self):
        request = self.factory.get(
            "/health/live/",
            HTTP_X_REQUEST_ID="invalid request id",
        )
        middleware = RequestIDMiddleware(
            lambda request: HttpResponse("ok", status=200)
        )

        response = middleware(request)
        returned_id = response["X-Request-ID"]

        self.assertEqual(request.request_id, returned_id)
        self.assertEqual(str(uuid.UUID(returned_id)), returned_id)
        self.assertNotEqual(returned_id, "invalid request id")
