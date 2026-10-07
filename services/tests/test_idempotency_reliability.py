
import threading
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth.models import User
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from services.idempotency_service import build_request_hash
from services.models import (
    Booking,
    Category,
    IdempotencyRecord,
    Provider,
    Service,
)


class IdempotencyReliabilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create_user(
            username="reliability_customer",
            password="TestPassword123!",
        )

        self.provider_user = User.objects.create_user(
            username="reliability_provider",
            password="TestPassword123!",
        )

        self.provider = Provider.objects.create(
            user=self.provider_user,
        )

        self.category = Category.objects.create(
            name="Reliability Category",
        )

        self.service = Service.objects.create(
            name="Reliability Service",
            description="Service for idempotency reliability testing.",
            category=self.category,
            provider=self.provider,
            price="100.00",
            location="Test Location",
        )

        self.client.force_authenticate(
            user=self.user,
        )

    def booking_payload(self):
        return {
            "service": str(self.service.id),
            "booking_date": (
                timezone.localdate() + timedelta(days=1)
            ).isoformat(),
            "booking_time": "10:00:00",
        }

    def get_booking_id_from_response(self, response):
        response_data = response.data

        if "id" in response_data:
            return response_data["id"]

        if (
            "data" in response_data
            and isinstance(response_data["data"], dict)
            and "id" in response_data["data"]
        ):
            return response_data["data"]["id"]

        self.fail(
            "Booking ID was not found in API response: "
            f"{response_data}"
        )

    def test_same_idempotency_key_and_same_payload_returns_original_result(
        self,
    ):
        idempotency_key = str(uuid4())
        payload = self.booking_payload()

        first_response = self.client.post(
            "/api/v1/bookings/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )

        self.assertEqual(
            first_response.status_code,
            201,
        )

        first_booking_id = self.get_booking_id_from_response(
            first_response,
        )

        second_response = self.client.post(
            "/api/v1/bookings/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )

        self.assertEqual(
            second_response.status_code,
            200,
        )

        second_booking_id = self.get_booking_id_from_response(
            second_response,
        )

        self.assertEqual(
            second_booking_id,
            first_booking_id,
        )

        self.assertEqual(
            Booking.objects.filter(
                customer=self.user,
            ).count(),
            1,
        )

    def test_same_idempotency_key_with_different_payload_returns_conflict(
        self,
    ):
        idempotency_key = str(uuid4())

        first_payload = self.booking_payload()

        first_response = self.client.post(
            "/api/v1/bookings/",
            first_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )

        self.assertEqual(
            first_response.status_code,
            201,
        )

        second_payload = self.booking_payload()
        second_payload["booking_time"] = "11:00:00"

        second_response = self.client.post(
            "/api/v1/bookings/",
            second_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )

        self.assertEqual(
            second_response.status_code,
            409,
        )

        self.assertEqual(
            Booking.objects.filter(
                customer=self.user,
            ).count(),
            1,
        )


    def test_processing_request_returns_conflict_for_duplicate(self):
        idempotency_key = str(uuid4())
        payload = self.booking_payload()

        request_hash = build_request_hash(
            payload,
        )

        IdempotencyRecord.objects.create(
            user=self.user,
            key=idempotency_key,
            operation="create_booking",
            request_hash=request_hash,
            status="PROCESSING",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        response = self.client.post(
            "/api/v1/bookings/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )

        self.assertEqual(
            response.status_code,
            409,
        )

        self.assertEqual(
            Booking.objects.filter(
                customer=self.user,
            ).count(),
            0,
        )

        record = IdempotencyRecord.objects.get(
            user=self.user,
            key=idempotency_key,
            operation="create_booking",
        )

        self.assertEqual(
            record.status,
            "PROCESSING",
        )

    def test_failed_request_can_be_retried_with_same_idempotency_key(
        self,
    ):
        idempotency_key = str(uuid4())
        payload = self.booking_payload()

        request_hash = build_request_hash(
            payload,
        )

        IdempotencyRecord.objects.create(
            user=self.user,
            key=idempotency_key,
            operation="create_booking",
            request_hash=request_hash,
            status="FAILED",
            response_status=500,
            response_body={
                "success": False,
                "message": "Temporary booking failure.",
            },
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        response = self.client.post(
            "/api/v1/bookings/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )

        self.assertEqual(
            response.status_code,
            201,
        )

        self.assertEqual(
            Booking.objects.filter(
                customer=self.user,
            ).count(),
            1,
        )

        record = IdempotencyRecord.objects.get(
            user=self.user,
            key=idempotency_key,
            operation="create_booking",
        )

        self.assertEqual(
            record.status,
            "COMPLETED",
        )

        self.assertIsNotNone(
            record.response_body,
        )

        self.assertEqual(
            record.response_status,
            201,
        )

    def test_response_loss_retry_returns_original_booking(
        self,
    ):
        idempotency_key = str(uuid4())
        payload = self.booking_payload()

        # Simulate the first request succeeding.
        first_response = self.client.post(
            "/api/v1/bookings/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )

        self.assertEqual(
            first_response.status_code,
            201,
        )

        first_booking_id = self.get_booking_id_from_response(
            first_response,
        )

        # The client behaves as if the response was lost.
        # It sends the EXACT SAME request again.
        retry_response = self.client.post(
            "/api/v1/bookings/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )

        self.assertEqual(
            retry_response.status_code,
            200,
        )

        retry_booking_id = self.get_booking_id_from_response(
            retry_response,
        )

        # The retry must return the original booking.
        self.assertEqual(
            retry_booking_id,
            first_booking_id,
        )

        # No duplicate booking may be created.
        self.assertEqual(
            Booking.objects.filter(
                customer=self.user,
            ).count(),
            1,
        )

        # The idempotency record must remain completed.
        record = IdempotencyRecord.objects.get(
            user=self.user,
            key=idempotency_key,
            operation="create_booking",
        )

        self.assertEqual(
            record.status,
            "COMPLETED",
        )

        self.assertEqual(
            record.response_status,
            201,
        )

class ConcurrentIdempotencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user = User.objects.create_user(
            username="concurrent_customer",
            password="TestPassword123!",
        )

        self.provider_user = User.objects.create_user(
            username="concurrent_provider",
            password="TestPassword123!",
        )

        self.provider = Provider.objects.create(
            user=self.provider_user,
        )

        self.category = Category.objects.create(
            name="Concurrent Category",
        )

        self.service = Service.objects.create(
            name="Concurrent Service",
            description="Service for concurrent idempotency testing.",
            category=self.category,
            provider=self.provider,
            price="100.00",
            location="Test Location",
        )

    def booking_payload(self):
        return {
            "service": str(self.service.id),
            "booking_date": (
                timezone.localdate() + timedelta(days=1)
            ).isoformat(),
            "booking_time": "10:00:00",
        }

    def send_booking_request(
        self,
        idempotency_key,
        results,
    ):
        close_old_connections()

        try:
            client = APIClient()

            user = User.objects.get(
                pk=self.user.pk,
            )

            client.force_authenticate(
                user=user,
            )

            payload = self.booking_payload()

            response = client.post(
                "/api/v1/bookings/",
                payload,
                format="json",
                HTTP_IDEMPOTENCY_KEY=idempotency_key,
            )

            results.append(
                response.status_code,
            )

        finally:
            close_old_connections()

    def test_concurrent_requests_with_same_key_create_one_booking(
        self,
    ):
        idempotency_key = str(uuid4())

        results = []

        thread_one = threading.Thread(
            target=self.send_booking_request,
            args=(
                idempotency_key,
                results,
            ),
        )

        thread_two = threading.Thread(
            target=self.send_booking_request,
            args=(
                idempotency_key,
                results,
            ),
        )

        thread_one.start()
        thread_two.start()

        thread_one.join()
        thread_two.join()

        self.assertEqual(
            len(results),
            2,
        )

        self.assertIn(
            201,
            results,
        )

        self.assertTrue(
            200 in results or 409 in results,
        )

        self.assertEqual(
            Booking.objects.filter(
                customer=self.user,
            ).count(),
            1,
        )

        self.assertEqual(
            IdempotencyRecord.objects.filter(
                user=self.user,
                key=idempotency_key,
                operation="create_booking",
            ).count(),
            1,
        )

        record = IdempotencyRecord.objects.get(
            user=self.user,
            key=idempotency_key,
            operation="create_booking",
        )

        self.assertEqual(
            record.status,
            "COMPLETED",
        )
