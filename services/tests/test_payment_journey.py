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
class PaymentJourneyTests(TransactionTestCase):

    def setUp(self):
        self.client = APIClient()

        self.customer = User.objects.create_user(
            username="payment_customer",
            email="payment_customer@example.com",
            password="TestPassword123!",
        )

        self.provider_user = User.objects.create_user(
            username="payment_provider",
            email="payment_provider@example.com",
            password="TestPassword123!",
        )

        self.category = Category.objects.create(
            name="Payment Test Category",
            description="Payment test category",
            status=True,
        )

        self.provider = Provider.objects.create(
            user=self.provider_user,
            name="Payment Test Provider",
            description="Payment test provider",
            status=True,
        )

        self.service = Service.objects.create(
            name="Payment Test Service",
            description="Payment test service",
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
            user=self.customer
        )

    def test_customer_can_initiate_payment(self):
        response = self.client.post(
            "/api/v1/services/payments/initiate/",
            {
                "booking": str(self.booking.id),
                "amount": "500.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        payment = Payment.objects.get(
            booking=self.booking
        )

        self.assertEqual(
            payment.amount,
            Decimal("500.00"),
        )

        self.assertEqual(
            payment.payment_status,
            "PENDING",
        )

        self.assertEqual(
            payment.payment_method,
            "MOCK",
        )

        self.assertTrue(
            payment.transaction_id.startswith("MOCK-")
        )

    def test_customer_can_process_successful_payment(self):
        payment = Payment.objects.create(
            booking=self.booking,
            amount=Decimal("500.00"),
            transaction_id="MOCK-PROCESS-123",
            payment_status="PENDING",
            payment_method="MOCK",
        )

        response = self.client.post(
            f"/api/v1/services/payments/{payment.id}/process/",
            {
                "result": "SUCCESS",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        payment.refresh_from_db()

        self.assertEqual(
            payment.payment_status,
            "SUCCESS",
        )

    def test_webhook_rejects_invalid_secret(self):
        payment = Payment.objects.create(
            booking=self.booking,
            amount=Decimal("500.00"),
            transaction_id="MOCK-WEBHOOK-SECRET",
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
            HTTP_X_WEBHOOK_SECRET="wrong-secret",
        )

        self.assertEqual(
            response.status_code,
            401,
        )

        payment.refresh_from_db()

        self.assertEqual(
            payment.payment_status,
            "PENDING",
        )

    def test_webhook_rejects_wrong_transaction_id(self):
        payment = Payment.objects.create(
            booking=self.booking,
            amount=Decimal("500.00"),
            transaction_id="MOCK-CORRECT-TRANSACTION",
            payment_status="PENDING",
            payment_method="MOCK",
        )

        response = self.client.post(
            "/api/v1/services/payments/webhook/",
            {
                "payment_id": str(payment.id),
                "transaction_id": "MOCK-WRONG-TRANSACTION",
                "payment_status": "SUCCESS",
            },
            format="json",
            HTTP_X_WEBHOOK_SECRET="test-webhook-secret",
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        payment.refresh_from_db()

        self.assertEqual(
            payment.payment_status,
            "PENDING",
        )

    def test_successful_webhook_updates_payment_booking_and_notifications(
        self,
    ):
        payment = Payment.objects.create(
            booking=self.booking,
            amount=Decimal("500.00"),
            transaction_id="MOCK-SUCCESS-TRANSACTION",
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

        self.assertEqual(
            response.status_code,
            200,
        )

        payment.refresh_from_db()
        self.booking.refresh_from_db()

        self.assertEqual(
            payment.payment_status,
            "SUCCESS",
        )

        self.assertEqual(
            self.booking.status,
            "confirmed",
        )

        payment_notification = Notification.objects.filter(
            recipient=self.customer,
            booking=self.booking,
            notification_type="PAYMENT_SUCCESSFUL",
        ).first()

        confirmed_notification = Notification.objects.filter(
            recipient=self.customer,
            booking=self.booking,
            notification_type="BOOKING_CONFIRMED",
        ).first()

        self.assertIsNotNone(
            payment_notification
        )

        self.assertIsNotNone(
            confirmed_notification
        )