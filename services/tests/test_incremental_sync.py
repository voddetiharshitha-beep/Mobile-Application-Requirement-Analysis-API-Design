
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from services.models import (
    Booking,
    Category,
    Provider,
    Service,
)


class IncrementalBookingSyncTests(TestCase):
    """
    Verify incremental booking synchronization
    for mobile clients.
    """

    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create_user(
            username="sync_user",
            password="TestPassword123!",
        )

        self.provider_user = User.objects.create_user(
            username="sync_provider",
            password="TestPassword123!",
        )

        self.provider = Provider.objects.create(
            user=self.provider_user,
        )

        self.category = Category.objects.create(
            name="Sync Category",
        )

        self.service = Service.objects.create(
            name="Sync Service",
            description="Service for incremental sync testing.",
            category=self.category,
            provider=self.provider,
            price="100.00",
            location="Test Location",
        )

        self.client.force_authenticate(
            user=self.user
        )

    def create_booking(self, days_offset):
        return Booking.objects.create(
            customer=self.user,
            provider=self.provider,
            service=self.service,
            booking_date=(
                timezone.localdate()
                + timedelta(days=days_offset)
            ),
            booking_time="10:00:00",
            amount="100.00",
        )

    def test_full_sync_returns_bookings(self):
        """
        Without updated_after, the endpoint should
        return the user's existing bookings.
        """

        self.create_booking(1)
        self.create_booking(2)

        response = self.client.get(
            "/api/v1/sync/bookings/"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTrue(
            response.data["success"]
        )

        self.assertIn(
            "data",
            response.data,
        )

        self.assertIn(
            "sync",
            response.data,
        )

        self.assertEqual(
            len(response.data["data"]),
            2,
        )

        self.assertIn(
            "synced_at",
            response.data["sync"],
        )

        self.assertIn(
            "has_more",
            response.data["sync"],
        )

    def test_incremental_sync_returns_only_changed_bookings(self):
        """
        updated_after should exclude bookings that existed
        before the supplied synchronization timestamp.
        """

        old_booking = self.create_booking(1)

        sync_point = timezone.now()

        new_booking = self.create_booking(2)

        response = self.client.get(
            "/api/v1/sync/bookings/",
            {
                "updated_after": sync_point.isoformat(),
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        returned_ids = {
            item["id"]
            for item in response.data["data"]
        }

        self.assertNotIn(
            str(old_booking.id),
            returned_ids,
        )

        self.assertIn(
            str(new_booking.id),
            returned_ids,
        )

    def test_invalid_updated_after_returns_bad_request(self):
        """
        An invalid synchronization timestamp should
        return a clear validation error.
        """

        response = self.client.get(
            "/api/v1/sync/bookings/",
            {
                "updated_after": "not-a-valid-date",
            },
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertEqual(
            response.data["error_code"],
            "INVALID_SYNC_TIMESTAMP",
        )

    def test_sync_cursor_returns_next_batch(self):
        """
        Cursor pagination should allow the mobile client
        to continue synchronization without page numbers.
        """

        for offset in range(25):
            self.create_booking(offset + 1)

        first_response = self.client.get(
            "/api/v1/sync/bookings/"
        )

        self.assertEqual(
            first_response.status_code,
            200,
        )

        self.assertEqual(
            len(first_response.data["data"]),
            20,
        )

        next_cursor = (
            first_response.data["sync"]["next_cursor"]
        )

        self.assertIsNotNone(
            next_cursor
        )

        second_response = self.client.get(
            next_cursor
        )

        self.assertEqual(
            second_response.status_code,
            200,
        )

        self.assertEqual(
            len(second_response.data["data"]),
            5,
        )

        self.assertIn(
            "sync",
            second_response.data,
        )
