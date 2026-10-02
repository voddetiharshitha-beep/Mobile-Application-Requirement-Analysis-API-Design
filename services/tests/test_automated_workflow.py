from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TransactionTestCase, override_settings
from django.utils.crypto import get_random_string
from rest_framework.test import APIClient

from services.models import (
    Booking,
    BookingIdempotencyKey,
    Category,
    Provider,
    Service,
)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class AutomatedWorkflowTests(TransactionTestCase):

    def setUp(self):
        self.test_password = get_random_string(32)

        self.customer = User.objects.create_user(
            username="workflow_customer",
            email="workflow_customer@example.com",
            password=self.test_password,
        )

        self.provider_user = User.objects.create_user(
            username="workflow_provider",
            email="workflow_provider@example.com",
            password=self.test_password,
        )

        self.category = Category.objects.create(
            name="Workflow Test Category",
            description="Workflow test category",
            status=True,
        )

        self.provider = Provider.objects.create(
            user=self.provider_user,
            name="Workflow Test Provider",
            description="Workflow test provider",
            status=True,
        )

        self.service = Service.objects.create(
            name="Workflow Test Service",
            description="Workflow test service",
            location="Hyderabad",
            price=Decimal("500.00"),
            status=True,
            category=self.category,
            provider=self.provider,
        )

        self.booking_date = (
            date.today() + timedelta(days=1)
        )

        self.booking_time = "10:00:00"

    def create_authenticated_client(self):
        client = APIClient()

        client.force_authenticate(
            user=self.customer
        )

        return client

    def test_failure_invalid_booking_status_transition(self):
        """
        Failure case:

        A pending booking cannot jump directly
        to completed.
        """

        booking = Booking.objects.create(
            customer=self.customer,
            provider=self.provider,
            service=self.service,
            booking_date=self.booking_date,
            booking_time=self.booking_time,
            amount=Decimal("500.00"),
            status="pending",
        )

        client = APIClient()

        client.force_authenticate(
            user=self.provider_user
        )

        response = client.post(
            f"/api/v1/bookings/{booking.id}/status/",
            {
                "status": "completed",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        booking.refresh_from_db()

        self.assertEqual(
            booking.status,
            "pending",
        )

    def test_duplicate_request_returns_existing_booking(self):
        """
        Duplicate request case:

        Two booking requests use the same Idempotency-Key.

        The second request must return the original
        booking instead of creating a new booking.
        """

        client = self.create_authenticated_client()

        idempotency_key = (
            "workflow-duplicate-key-001"
        )

        first_payload = {
            "service": str(self.service.id),
            "booking_date": (
                self.booking_date.isoformat()
            ),
            "booking_time": self.booking_time,
        }

        first_response = client.post(
            "/api/v1/bookings/",
            first_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )

        self.assertEqual(
            first_response.status_code,
            201,
        )

        first_booking_id = (
            first_response.data["data"]["id"]
        )

        first_booking = Booking.objects.get(
            id=first_booking_id
        )

        self.assertEqual(
            first_booking.booking_date,
            self.booking_date,
        )

        # Use a different booking date for the second
        # request. The Idempotency-Key must still cause
        # the original booking to be returned.
        second_payload = {
            "service": str(self.service.id),
            "booking_date": (
                self.booking_date + timedelta(days=1)
            ).isoformat(),
            "booking_time": "11:00:00",
        }

        second_response = client.post(
            "/api/v1/bookings/",
            second_payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )

        self.assertEqual(
            second_response.status_code,
            200,
        )

        second_booking_id = (
            second_response.data["data"]["id"]
        )

        # Both requests must point to the same booking.
        self.assertEqual(
            first_booking_id,
            second_booking_id,
        )

        # Only one booking must exist.
        self.assertEqual(
            Booking.objects.filter(
                customer=self.customer,
                service=self.service,
            ).count(),
            1,
        )

        # Only one idempotency record must exist.
        self.assertEqual(
            BookingIdempotencyKey.objects.filter(
                user=self.customer,
                key=idempotency_key,
            ).count(),
            1,
        )

        # Confirm that the original booking data was
        # preserved and the second request did not
        # create or modify the booking.
        booking = Booking.objects.get(
            id=first_booking_id
        )

        self.assertEqual(
            booking.booking_date,
            self.booking_date,
        )

        self.assertEqual(
            booking.booking_time.strftime("%H:%M:%S"),
            self.booking_time,
        )

    def test_concurrent_duplicate_requests_create_only_one_booking(
        self,
    ):
        """
        Concurrent request case:

        Two requests arrive at approximately the same time
        using the same Idempotency-Key.

        PostgreSQL + the database uniqueness constraint must
        ensure that only one booking is created.
        """

        idempotency_key = (
            "workflow-concurrent-key-001"
        )

        payload = {
            "service": str(self.service.id),
            "booking_date": (
                self.booking_date.isoformat()
            ),
            "booking_time": self.booking_time,
        }

        def send_booking_request():
            client = APIClient()

            client.force_authenticate(
                user=self.customer
            )

            response = client.post(
                "/api/v1/bookings/",
                payload,
                format="json",
                HTTP_IDEMPOTENCY_KEY=idempotency_key,
            )

            return (
                response.status_code,
                response.data,
            )

        with ThreadPoolExecutor(
            max_workers=2
        ) as executor:

            futures = [
                executor.submit(
                    send_booking_request
                )
                for _ in range(2)
            ]

            results = [
                future.result()
                for future in futures
            ]

        status_codes = [
            result[0]
            for result in results
        ]

        booking_ids = [
            result[1]["data"]["id"]
            for result in results
        ]

        self.assertIn(
            201,
            status_codes,
        )

        self.assertIn(
            200,
            status_codes,
        )

        self.assertEqual(
            booking_ids[0],
            booking_ids[1],
        )

        self.assertEqual(
            Booking.objects.filter(
                customer=self.customer,
                service=self.service,
            ).count(),
            1,
        )

        self.assertEqual(
            BookingIdempotencyKey.objects.filter(
                user=self.customer,
                key=idempotency_key,
            ).count(),
            1,
        )
        