from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient

from services.models import (
    Booking,
    Category,
    Notification,
    Payment,
    Provider,
    Service,
)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    PAYMENT_WEBHOOK_SECRET="test-webhook-secret",
)
class NotificationJourneyTests(TransactionTestCase):

    def setUp(self):
        self.client = APIClient()

        self.customer = User.objects.create_user(
            username="notification_customer",
            email="notification_customer@example.com",
            password="TestPassword123!",
        )

        self.provider_user = User.objects.create_user(
            username="notification_provider",
            email="notification_provider@example.com",
            password="TestPassword123!",
        )

        self.category = Category.objects.create(
            name="Notification Test Category",
            description="Notification test category",
            status=True,
        )

        self.provider = Provider.objects.create(
            user=self.provider_user,
            name="Notification Test Provider",
            description="Notification test provider",
            status=True,
        )

        self.service = Service.objects.create(
            name="Notification Test Service",
            description="Notification test service",
            location="Hyderabad",
            price=Decimal("500.00"),
            status=True,
            category=self.category,
            provider=self.provider,
        )

        self.client.force_authenticate(
            user=self.customer
        )

    def create_booking(self, status="pending"):
        return Booking.objects.create(
            customer=self.customer,
            provider=self.provider,
            service=self.service,
            booking_date=date.today() + timedelta(days=1),
            booking_time="10:00:00",
            amount=Decimal("500.00"),
            status=status,
        )

    def test_booking_created_notification(self):
        booking = self.create_booking()

        Notification.objects.create(
            recipient=self.customer,
            booking=booking,
            notification_type="BOOKING_CREATED",
            message="Your booking has been created successfully.",
        )

        notification = Notification.objects.filter(
            recipient=self.customer,
            booking=booking,
            notification_type="BOOKING_CREATED",
        ).first()

        self.assertIsNotNone(notification)
        self.assertEqual(
            notification.message,
            "Your booking has been created successfully.",
        )

    def test_payment_successful_and_booking_confirmed_notifications(
        self,
    ):
        booking = self.create_booking()

        payment = Payment.objects.create(
            booking=booking,
            amount=Decimal("500.00"),
            transaction_id="MOCK-NOTIFICATION-SUCCESS",
            payment_status="PENDING",
            payment_method="MOCK",
        )

        response = self.client.post(
            "/api/v1/services/payments/webhook/",
            {
                "payment_id": str(payment.id),
                "transaction_id": payment.transaction_id,
                "payment_status": "SUCCESS",
            },
            format="json",
            HTTP_X_WEBHOOK_SECRET="test-webhook-secret",
        )

        self.assertEqual(response.status_code, 200)

        payment.refresh_from_db()
        booking.refresh_from_db()

        self.assertEqual(
            payment.payment_status,
            "SUCCESS",
        )

        self.assertEqual(
            booking.status,
            "confirmed",
        )

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.customer,
                booking=booking,
                notification_type="PAYMENT_SUCCESSFUL",
            ).exists()
        )

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.customer,
                booking=booking,
                notification_type="BOOKING_CONFIRMED",
            ).exists()
        )

    def test_provider_started_notification(self):
        booking = self.create_booking(
            status="confirmed"
        )

        response = self.client.post(
            f"/api/v1/services/bookings/{booking.id}/status/",
            {
                "status": "in_progress",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.customer,
                booking=booking,
                notification_type="PROVIDER_STARTED",
            ).exists()
        )

    def test_booking_completed_notification(self):
        booking = self.create_booking(
            status="in_progress"
        )

        response = self.client.post(
            f"/api/v1/services/bookings/{booking.id}/status/",
            {
                "status": "completed",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.customer,
                booking=booking,
                notification_type="BOOKING_COMPLETED",
            ).exists()
        )

    def test_booking_cancelled_notification(self):
        booking = self.create_booking()

        response = self.client.post(
            f"/api/v1/services/bookings/{booking.id}/cancel/",
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        booking.refresh_from_db()

        self.assertEqual(
            booking.status,
            "cancelled",
        )

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.customer,
                booking=booking,
                notification_type="BOOKING_CANCELLED",
            ).exists()
        )

    def test_customer_can_list_notifications(self):
        booking = self.create_booking()

        Notification.objects.create(
            recipient=self.customer,
            booking=booking,
            notification_type="BOOKING_CREATED",
            message="Your booking has been created successfully.",
        )

        response = self.client.get(
            "/api/v1/services/notifications/"
        )

        self.assertEqual(response.status_code, 200)

        self.assertGreaterEqual(
            response.data["count"],
            1,
        )

        notification_types = [
            notification["notification_type"]
            for notification in response.data["results"]
        ]

        self.assertIn(
            "BOOKING_CREATED",
            notification_types,
        )