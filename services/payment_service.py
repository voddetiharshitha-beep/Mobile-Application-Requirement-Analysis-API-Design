
import logging
import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from config.middleware import request_id_context

from .models import Payment
from .notification_service import send_notification
from .stripe_service import (
    StripeIntegrationError,
    create_payment_intent,
)


logger = logging.getLogger(__name__)


class PaymentWebhookConflict(Exception):
    """Raised when a webhook conflicts with a final payment state."""


def _current_correlation_id():
    """Return the current request ID for event tracing."""
    request_id = request_id_context.get()

    if not request_id or request_id == "-":
        return None

    return request_id


def initiate_payment(*, payment):
    """
    Create a Stripe test-mode PaymentIntent for the payment.

    Business rules:
    - Payment amount comes from the validated Payment record.
    - Stripe receives the amount in the smallest currency unit.
    - The Stripe PaymentIntent ID is stored as transaction_id.
    - Payment starts in PENDING state.
    """
    idempotency_key = f"payment-{payment.id}"

    try:
        stripe_payment = create_payment_intent(
            amount=payment.amount,
            currency="inr",
            idempotency_key=idempotency_key,
        )
    except StripeIntegrationError:
        logger.exception(
            "Stripe payment initiation failed.",
            extra={"payment_id": str(payment.id)},
        )
        raise

    payment.transaction_id = stripe_payment["id"]
    payment.payment_status = "PENDING"
    payment.payment_method = "STRIPE"

    payment.save(
        update_fields=[
            "transaction_id",
            "payment_status",
            "payment_method",
        ]
    )

    return payment


def process_payment(*, payment, payment_result):
    """
    Process a payment result.

    The serializer/view is responsible for checking:
    - the payment belongs to the current user
    - the payment is currently pending

    This service applies the payment result.
    """
    payment.payment_status = payment_result

    payment.save(update_fields=["payment_status"])

    return payment


def process_payment_webhook(*, payment, payment_status):
    """
    Process a payment provider webhook safely.

    Lock and reload the payment inside the transaction so concurrent
    webhook deliveries cannot overwrite an already committed final state.

    Repeated delivery of the same final status is a no-op.
    A conflicting final status raises PaymentWebhookConflict.

    Payment and booking updates are atomic. Notifications and the
    WebSocket event are scheduled only for the first successful transition.
    """
    if payment_status not in {"SUCCESS", "FAILED"}:
        raise ValueError("Unsupported webhook payment status.")

    with transaction.atomic():
        payment = (
            Payment.objects
            .select_for_update()
            .select_related("booking")
            .get(pk=payment.pk)
        )

        # A duplicate event must not repeat notifications or WebSocket events.
        if payment.payment_status == payment_status:
            return payment

        # Never allow a final payment state to be overwritten.
        if payment.payment_status != "PENDING":
            raise PaymentWebhookConflict(
                "Payment has already been processed with a different status."
            )

        payment.payment_status = payment_status
        payment.save(update_fields=["payment_status"])

        if payment_status == "SUCCESS":
            booking = payment.booking
            booking.status = "confirmed"
            booking.save(update_fields=["status", "updated_at"])

            channel_layer = get_channel_layer()
            correlation_id = _current_correlation_id()

            transaction.on_commit(
                lambda: async_to_sync(channel_layer.group_send)(
                    f"booking_{booking.id}",
                    {
                        "type": "booking_status_update",
                        "booking_id": str(booking.id),
                        "status": "confirmed",
                        "message": "Booking status changed to confirmed.",
                        "correlation_id": correlation_id,
                    },
                )
            )

            transaction.on_commit(
                lambda: send_notification(
                    recipient_id=booking.customer_id,
                    booking_id=str(booking.id),
                    notification_type="PAYMENT_SUCCESSFUL",
                    message="Your payment was successful.",
                )
            )

            transaction.on_commit(
                lambda: send_notification(
                    recipient_id=booking.customer_id,
                    booking_id=str(booking.id),
                    notification_type="BOOKING_CONFIRMED",
                    message="Your booking has been confirmed.",
                )
            )

    return payment
