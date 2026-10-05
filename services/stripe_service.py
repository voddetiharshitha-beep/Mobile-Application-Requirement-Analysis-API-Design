import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import stripe
from django.conf import settings


logger = logging.getLogger(__name__)


class StripeIntegrationError(Exception):
    """Raised when communication with Stripe fails safely."""


def _get_stripe_client():
    """
    Create a configured Stripe client.

    Authentication:
        Uses STRIPE_SECRET_KEY from Django settings.

    Timeout:
        Configured at the HTTP client level.

    Retries:
        Stripe SDK automatically retries eligible transient failures.
    """

    if not settings.STRIPE_SECRET_KEY:
        raise StripeIntegrationError(
            "Stripe payment integration is not configured."
        )

    http_client = stripe.RequestsClient(
        timeout=settings.STRIPE_API_TIMEOUT,
    )

    return stripe.StripeClient(
        settings.STRIPE_SECRET_KEY,
        http_client=http_client,
        max_network_retries=2,
    )


def _convert_amount_to_minor_units(amount):
    """
    Convert a normal currency amount into the smallest currency unit.

    Example:
        Decimal("500.00") INR -> 50000 paise
    """

    try:
        decimal_amount = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise StripeIntegrationError(
            "Invalid payment amount."
        ) from exc

    if decimal_amount <= Decimal("0"):
        raise StripeIntegrationError(
            "Payment amount must be greater than zero."
        )

    decimal_amount = decimal_amount.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    minor_units = int(
        decimal_amount * Decimal("100")
    )

    if minor_units <= 0:
        raise StripeIntegrationError(
            "Payment amount must be greater than zero."
        )

    return minor_units


def create_payment_intent(
    *,
    amount,
    currency="inr",
    idempotency_key=None,
):
    """
    Create a Stripe PaymentIntent in test mode.

    The application stores amounts in normal currency units.
    Stripe receives the amount in the smallest currency unit.

    Example:
        500.00 INR -> 50000 paise

    The idempotency key is supplied separately through Stripe's
    request options so retries remain safe.
    """

    if not idempotency_key:
        raise StripeIntegrationError(
            "An idempotency key is required for payment creation."
        )

    minor_amount = _convert_amount_to_minor_units(
        amount
    )

    try:
        stripe_client = _get_stripe_client()

        payment_intent = (
            stripe_client.v1.payment_intents.create(
                {
                    "amount": minor_amount,
                    "currency": currency.lower(),
                },
                options={
                    "idempotency_key": idempotency_key,
                },
            )
        )

        return {
            "id": payment_intent.id,
            "status": payment_intent.status,
            "amount": payment_intent.amount,
            "currency": payment_intent.currency,
        }

    except stripe.error.StripeError as exc:
        logger.exception(
            "Stripe payment integration failed.",
            extra={
                "error_type": exc.__class__.__name__,
            },
        )

        raise StripeIntegrationError(
            "The external payment service could not "
            "process the payment request."
        ) from exc

    except Exception as exc:
        logger.exception(
            "Unexpected Stripe integration failure.",
            extra={
                "error_type": exc.__class__.__name__,
            },
        )

        raise StripeIntegrationError(
            "The external payment service is temporarily "
            "unavailable."
        ) from exc