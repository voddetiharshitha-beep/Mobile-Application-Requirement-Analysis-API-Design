from decimal import Decimal
from unittest.mock import Mock, patch

import stripe
from django.test import SimpleTestCase, override_settings

from services.stripe_service import (
    StripeIntegrationError,
    _convert_amount_to_minor_units,
    _get_stripe_client,
    create_payment_intent,
)


class StripeAmountConversionTests(SimpleTestCase):

    def test_rupees_are_converted_to_paise(self):
        result = _convert_amount_to_minor_units(
            Decimal("500.00")
        )

        self.assertEqual(
            result,
            50000,
        )

    def test_decimal_amount_is_converted_correctly(self):
        result = _convert_amount_to_minor_units(
            Decimal("125.50")
        )

        self.assertEqual(
            result,
            12550,
        )

    def test_zero_amount_is_rejected(self):
        with self.assertRaises(StripeIntegrationError):
            _convert_amount_to_minor_units(
                Decimal("0.00")
            )

    def test_negative_amount_is_rejected(self):
        with self.assertRaises(StripeIntegrationError):
            _convert_amount_to_minor_units(
                Decimal("-100.00")
            )

    def test_invalid_amount_is_rejected(self):
        with self.assertRaises(StripeIntegrationError):
            _convert_amount_to_minor_units(
                "invalid-amount"
            )


class StripeClientConfigurationTests(SimpleTestCase):

    @override_settings(
        STRIPE_SECRET_KEY="sk_test_unit_test_key",
        STRIPE_API_TIMEOUT=10.0,
    )
    @patch("services.stripe_service.stripe.StripeClient")
    @patch("services.stripe_service.stripe.RequestsClient")
    def test_stripe_client_uses_timeout_and_retries(
        self,
        mock_requests_client,
        mock_stripe_client,
    ):
        mock_http_client = Mock()
        mock_requests_client.return_value = mock_http_client

        mock_client = Mock()
        mock_stripe_client.return_value = mock_client

        result = _get_stripe_client()

        mock_requests_client.assert_called_once_with(
            timeout=10.0,
        )

        mock_stripe_client.assert_called_once_with(
            "sk_test_unit_test_key",
            http_client=mock_http_client,
            max_network_retries=2,
        )

        self.assertEqual(
            result,
            mock_client,
        )

    @override_settings(
        STRIPE_SECRET_KEY=None,
        STRIPE_API_TIMEOUT=10.0,
    )
    def test_missing_stripe_key_is_rejected(self):
        with self.assertRaises(StripeIntegrationError):
            _get_stripe_client()


class StripePaymentIntentTests(SimpleTestCase):

    @override_settings(
        STRIPE_SECRET_KEY="sk_test_unit_test_key",
        STRIPE_API_TIMEOUT=10.0,
    )
    @patch("services.stripe_service._get_stripe_client")
    def test_payment_intent_creation_succeeds(
        self,
        mock_get_stripe_client,
    ):
        mock_payment_intent = Mock()

        mock_payment_intent.id = "pi_test_123456789"
        mock_payment_intent.status = (
            "requires_payment_method"
        )
        mock_payment_intent.amount = 50000
        mock_payment_intent.currency = "inr"

        mock_client = Mock()

        (
            mock_client
            .v1
            .payment_intents
            .create
            .return_value
        ) = mock_payment_intent

        mock_get_stripe_client.return_value = mock_client

        result = create_payment_intent(
            amount=Decimal("500.00"),
            currency="inr",
            idempotency_key="payment-test-123",
        )

        self.assertEqual(
            result["id"],
            "pi_test_123456789",
        )

        self.assertEqual(
            result["status"],
            "requires_payment_method",
        )

        self.assertEqual(
            result["amount"],
            50000,
        )

        self.assertEqual(
            result["currency"],
            "inr",
        )

        mock_client.v1.payment_intents.create.assert_called_once_with(
            {
                "amount": 50000,
                "currency": "inr",
            },
            options={
                "idempotency_key": "payment-test-123",
            },
        )

    @override_settings(
        STRIPE_SECRET_KEY="sk_test_unit_test_key",
        STRIPE_API_TIMEOUT=10.0,
    )
    @patch("services.stripe_service._get_stripe_client")
    def test_missing_idempotency_key_is_rejected(
        self,
        mock_get_stripe_client,
    ):
        with self.assertRaises(StripeIntegrationError):
            create_payment_intent(
                amount=Decimal("500.00"),
                currency="inr",
                idempotency_key=None,
            )

        mock_get_stripe_client.assert_not_called()

    @override_settings(
        STRIPE_SECRET_KEY="sk_test_unit_test_key",
        STRIPE_API_TIMEOUT=10.0,
    )
    @patch("services.stripe_service._get_stripe_client")
    def test_stripe_failure_is_converted_to_safe_error(
        self,
        mock_get_stripe_client,
    ):
        mock_client = Mock()

        mock_client.v1.payment_intents.create.side_effect = (
            stripe.error.StripeError(
                "Stripe test failure"
            )
        )

        mock_get_stripe_client.return_value = mock_client

        with self.assertRaises(StripeIntegrationError) as context:
            create_payment_intent(
                amount=Decimal("500.00"),
                currency="inr",
                idempotency_key="payment-test-456",
            )

        self.assertEqual(
            str(context.exception),
            "The external payment service could not "
            "process the payment request.",
        )

    @override_settings(
        STRIPE_SECRET_KEY="sk_test_unit_test_key",
        STRIPE_API_TIMEOUT=10.0,
    )
    @patch("services.stripe_service._get_stripe_client")
    def test_unexpected_failure_is_converted_to_safe_error(
        self,
        mock_get_stripe_client,
    ):
        mock_client = Mock()

        mock_client.v1.payment_intents.create.side_effect = (
            RuntimeError(
                "unexpected test failure"
            )
        )

        mock_get_stripe_client.return_value = mock_client

        with self.assertRaises(StripeIntegrationError) as context:
            create_payment_intent(
                amount=Decimal("500.00"),
                currency="inr",
                idempotency_key="payment-test-789",
            )

        self.assertEqual(
            str(context.exception),
            "The external payment service is temporarily "
            "unavailable.",
        )