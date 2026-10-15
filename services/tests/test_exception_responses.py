from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView
from django.test import SimpleTestCase

from services.exceptions import custom_exception_handler


class ExceptionResponseTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def get_response(self, exception):
        request = self.factory.get("/api/v1/test/")
        view = APIView()
        view.request = view.initialize_request(request)

        return custom_exception_handler(
            exception,
            {"request": view.request, "view": view},
        )

    def assert_error_format(self, exception, expected_status, expected_code):
        response = self.get_response(exception)

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, expected_status)
        self.assertEqual(
            set(response.data.keys()),
            {"success", "message", "error_code", "data"},
        )
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["error_code"], expected_code)
        self.assertTrue(response.data["message"])

    def test_validation_error_has_consistent_format_and_details(self):
        response = self.get_response(
            ValidationError({"name": ["This field is required."]})
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["error_code"], "VALIDATION_ERROR")
        self.assertIn("name", response.data["data"])

    def test_authentication_error_has_consistent_format(self):
        self.assert_error_format(
            NotAuthenticated(),
            401,
            "AUTHENTICATION_REQUIRED",
        )

    def test_authentication_failed_has_consistent_format(self):
        self.assert_error_format(
            AuthenticationFailed(),
            401,
            "AUTHENTICATION_REQUIRED",
        )

    def test_permission_denied_has_consistent_format(self):
        self.assert_error_format(
            PermissionDenied(),
            403,
            "PERMISSION_DENIED",
        )

    def test_not_found_has_consistent_format(self):
        self.assert_error_format(
            NotFound(),
            404,
            "NOT_FOUND",
        )

    def test_throttling_has_consistent_format(self):
        self.assert_error_format(
            Throttled(),
            429,
            "THROTTLED",
        )