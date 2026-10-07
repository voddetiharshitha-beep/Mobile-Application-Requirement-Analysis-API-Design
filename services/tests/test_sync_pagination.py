
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from services.models import (
    Booking,
    Category,
    Provider,
    Service,
)


class BookingCursorPaginationTests(TestCase):
    """
    Verify cursor pagination for mobile-friendly
    booking history requests.
    """

    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create_user(
            username="pagination_user",
            password="TestPassword123!",
        )

        self.client.force_authenticate(
            user=self.user
        )

        self.provider_user = User.objects.create_user(
            username="pagination_provider",
            password="TestPassword123!",
        )

        self.provider = Provider.objects.create(
            user=self.provider_user,
        )

        self.category = Category.objects.create(
            name="Pagination Category",
        )

        self.service = Service.objects.create(
            name="Pagination Service",
            description="Service for pagination testing.",
            category=self.category,
            provider=self.provider,
            price="100.00",
            location="Test Location",
        )

    def create_booking(self, days_offset):
        return Booking.objects.create(
            customer=self.user,
            provider=self.provider,
            service=self.service,
            booking_date=(
                date.today()
                + timedelta(days=days_offset)
            ),
            booking_time="10:00:00",
            amount="100.00",
        )

    def test_booking_history_uses_cursor_pagination(self):
        """
        The first request should return a paginated
        response containing next/previous cursor fields.
        """

        for offset in range(25):
            self.create_booking(offset + 1)

        response = self.client.get(
            "/api/v1/bookings/"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertIn(
            "results",
            response.data,
        )

        self.assertIn(
            "next",
            response.data,
        )

        self.assertIn(
            "previous",
            response.data,
        )

        self.assertEqual(
            len(response.data["results"]),
            20,
        )

        self.assertIsNotNone(
            response.data["next"]
        )

    def test_booking_history_next_cursor_returns_next_batch(self):
        """
        Following the returned cursor should retrieve
        the next batch without using page numbers.
        """

        for offset in range(25):
            self.create_booking(offset + 1)

        first_response = self.client.get(
            "/api/v1/bookings/"
        )

        self.assertEqual(
            first_response.status_code,
            200,
        )

        next_url = first_response.data["next"]

        self.assertIsNotNone(
            next_url
        )

        second_response = self.client.get(
            next_url
        )

        self.assertEqual(
            second_response.status_code,
            200,
        )

        self.assertIn(
            "results",
            second_response.data,
        )

        self.assertEqual(
            len(second_response.data["results"]),
            5,
        )
