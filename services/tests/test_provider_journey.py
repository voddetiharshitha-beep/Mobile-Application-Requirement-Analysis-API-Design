from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient

from services.models import (
    Booking,
    Category,
    Notification,
    Provider,
    Service,
)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class ProviderJourneyTests(TransactionTestCase):

    def setUp(self):
        self.client = APIClient()

        self.customer = User.objects.create_user(
            username="provider_journey_customer",
            email="customer@example.com",
            password="TestPassword123!",
        )

        self.provider_user = User.objects.create_user(
            username="provider_journey_provider",
            email="provider@example.com",
            password="TestPassword123!",
        )

        self.category = Category.objects.create(
            name="Provider Journey Category",
            description="Provider journey test category",
            status=True,
        )

        self.provider = Provider.objects.create(
            user=self.provider_user,
            name="Provider Journey Provider",
            description="Provider journey test provider",
            status=True,
        )

        self.service = Service.objects.create(
            name="Provider Journey Service",
            description="Provider journey test service",
            location="Hyderabad",
            price=Decimal("500.00"),
            status=True,
            category=self.category,
            provider=self.provider,
        )

        self.booking = Booking.objects.create(
            customer=self.customer,
            provider=self.provider,
            service=self.service,
            booking_date=date.today() + timedelta(days=1),
            booking_time="10:00:00",
            amount=Decimal("500.00"),
            status="pending",
        )

        self.client.force_authenticate(
            user=self.provider_user
        )

    def test_booking_can_be_confirmed(self):
        response = self.client.post(
            f"/api/v1/services/bookings/{self.booking.id}/status/",
            {
                "status": "confirmed",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.booking.refresh_from_db()

        self.assertEqual(
            self.booking.status,
            "confirmed",
        )

    def test_confirmed_booking_can_start_service(self):
        self.booking.status = "confirmed"
        self.booking.save(update_fields=["status"])

        response = self.client.post(
            f"/api/v1/services/bookings/{self.booking.id}/status/",
            {
                "status": "in_progress",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.booking.refresh_from_db()

        self.assertEqual(
            self.booking.status,
            "in_progress",
        )

        notification_exists = Notification.objects.filter(
            recipient=self.customer,
            booking=self.booking,
            notification_type="PROVIDER_STARTED",
        ).exists()

        self.assertTrue(notification_exists)

    def test_in_progress_booking_can_be_completed(self):
        self.booking.status = "in_progress"
        self.booking.save(update_fields=["status"])

        response = self.client.post(
            f"/api/v1/services/bookings/{self.booking.id}/status/",
            {
                "status": "completed",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.booking.refresh_from_db()

        self.assertEqual(
            self.booking.status,
            "completed",
        )

        notification_exists = Notification.objects.filter(
            recipient=self.customer,
            booking=self.booking,
            notification_type="BOOKING_COMPLETED",
        ).exists()

        self.assertTrue(notification_exists)

    def test_invalid_status_transition_is_rejected(self):
        response = self.client.post(
            f"/api/v1/services/bookings/{self.booking.id}/status/",
            {
                "status": "completed",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        self.booking.refresh_from_db()

        self.assertEqual(
            self.booking.status,
            "pending",
        )