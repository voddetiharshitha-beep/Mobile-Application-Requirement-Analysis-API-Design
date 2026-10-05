from datetime import date, timedelta
from decimal import Decimal
import secrets
from unittest.mock import patch

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
from services.stripe_service import StripeIntegrationError


class PaymentJourneyTests(TransactionTestCase):

    def setUp(self):
        self.client = APIClient()

        # Generate test-only credentials/secrets at runtime.
        # Nothing sensitive is stored in source code.
        self.test_password = secrets.token_urlsafe(24)
        self.webhook_secret = secrets.token_urlsafe(32)

        self.settings_override = override_settings(
            CELERY_TASK_ALWAYS_EAGER=True,
            CELERY_TASK_EAGER_PROPAGATES=True,
            PAYMENT_WEBHOOK_SECRET=self.webhook_secret,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.customer = User.objects.create_user(
            username="payment_customer",
            email="payment_customer@example.com",
            password=self.test_password,
        )

        self.provider_user = User.objects.create_user(
            username="payment_provider",
            email="payment_provider@example.com",
            password=self.test_password,
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

    @patch(
        "services.payment_service.create_payment_intent"
    )
    def test_customer_can_initiate_payment(
        self,
        mock_create_payment_intent,
    ):
        """
        Verify that a customer can initiate a Stripe payment.

        The external Stripe API is mocked so this automated test
        does not depend on network connectivity or a real Stripe
        request.
        """

        mock_create_payment_intent.return_value = {
            "id": "pi_test_123456789",
            "status": "requires_payment_method",
            "amount": 50000,
            "currency": "inr",
        }

        response = self.client.post(
            "/api/v1/services/payments/initiate/",
            {
                "booking": str(self.booking.id),
                "amount": "500.00",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            201,
        )

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
            "STRIPE",
        )

        self.assertEqual(
            payment.transaction_id,
            "pi_test_123456789",
        )

        mock_create_payment_intent.assert_called_once()

        call_kwargs = (
            mock_create_payment_intent.call_args.kwargs
        )

        self.assertEqual(
            call_kwargs["amount"],
            payment.amount,
        )

        self.assertEqual(
            call_kwargs["currency"],
            "inr",
        )

        self.assertTrue(
            call_kwargs["idempotency_key"]
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

        self.assertEqual(
            response.status_code,
            200,
        )

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
            HTTP_X_WEBHOOK_SECRET="invalid-test-secret",
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
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret,
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
            HTTP_X_WEBHOOK_SECRET=self.webhook_secret,
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

        payment_notification = (
            Notification.objects.filter(
                recipient=self.customer,
                booking=self.booking,
                notification_type="PAYMENT_SUCCESSFUL",
            ).first()
        )

        confirmed_notification = (
            Notification.objects.filter(
                recipient=self.customer,
                booking=self.booking,
                notification_type="BOOKING_CONFIRMED",
            ).first()
        )

        self.assertIsNotNone(
            payment_notification
        )

        self.assertIsNotNone(
            confirmed_notification
        )

    @patch(
        "services.payment_service.create_payment_intent"
    )
    def test_payment_initiation_returns_502_when_stripe_fails(
        self,
        mock_create_payment_intent,
    ):
        """
        Verify that an external Stripe failure is converted
        into a safe HTTP 502 response.

        The internal Stripe error must not be exposed to the
        API client.
        """

        mock_create_payment_intent.side_effect = (
            StripeIntegrationError(
                "Internal Stripe failure that must not be exposed."
            )
        )

        response = self.client.post(
            "/api/v1/services/payments/initiate/",
            {
                "booking": str(self.booking.id),
                "amount": "500.00",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            502,
        )

        self.assertFalse(
            response.data["success"]
        )

        self.assertEqual(
            response.data["error_code"],
            "PAYMENT_SERVICE_UNAVAILABLE",
        )

        self.assertEqual(
            response.data["message"],
            "The external payment service is temporarily unavailable.",
        )

        self.assertNotIn(
            "Internal Stripe failure",
            str(response.data),
        )

        self.assertNotIn(
            "sk_test_",
            str(response.data),
        )