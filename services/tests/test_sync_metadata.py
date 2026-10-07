
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from services.models import (
    Booking,
    Category,
    Notification,
    Provider,
    Service,
)


class SyncMetadataTests(TestCase):
    """
    Verify updated_at and version fields used
    by mobile incremental synchronization.
    """

    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create_user(
            username="sync_metadata_user",
            password="TestPassword123!",
        )

        self.provider_user = User.objects.create_user(
            username="sync_metadata_provider",
            password="TestPassword123!",
        )

        self.provider = Provider.objects.create(
            user=self.provider_user,
        )

        self.category = Category.objects.create(
            name="Sync Metadata Category",
        )

        self.service = Service.objects.create(
            name="Sync Metadata Service",
            description="Service for sync metadata testing.",
            category=self.category,
            provider=self.provider,
            price="100.00",
            location="Test Location",
        )

        self.booking = Booking.objects.create(
            customer=self.user,
            provider=self.provider,
            service=self.service,
            booking_date=timezone.localdate()
            + timedelta(days=1),
            booking_time="10:00:00",
            amount="100.00",
        )

    def test_notification_has_initial_sync_metadata(self):
        """
        A newly created notification must start
        with version 1 and a populated updated_at.
        """

        notification = Notification.objects.create(
            recipient=self.user,
            booking=self.booking,
            notification_type="BOOKING_CREATED",
            message="Booking created.",
        )

        self.assertEqual(
            notification.version,
            1,
        )

        self.assertIsNotNone(
            notification.updated_at,
        )

    def test_notification_serializer_returns_sync_metadata(self):
        """
        Notification API responses must expose
        updated_at and version to the mobile client.
        """

        notification = Notification.objects.create(
            recipient=self.user,
            booking=self.booking,
            notification_type="BOOKING_CREATED",
            message="Booking created.",
        )

        self.client.force_authenticate(
            user=self.user
        )

        response = self.client.get(
            "/api/v1/services/notifications/"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertIn(
            "results",
            response.data,
        )

        notification_data = response.data["results"][0]

        self.assertIn(
            "updated_at",
            notification_data,
        )

        self.assertIn(
            "version",
            notification_data,
        )

        self.assertEqual(
            notification_data["version"],
            1,
        )

    def test_notification_version_can_be_incremented(self):
        """
        Version must be usable as a synchronization revision.
        """

        notification = Notification.objects.create(
            recipient=self.user,
            booking=self.booking,
            notification_type="BOOKING_CREATED",
            message="Booking created.",
        )

        original_updated_at = notification.updated_at

        notification.version = 2
        notification.message = "Booking updated."

        notification.save()

        notification.refresh_from_db()

        self.assertEqual(
            notification.version,
            2,
        )

        self.assertGreaterEqual(
            notification.updated_at,
            original_updated_at,
        )
