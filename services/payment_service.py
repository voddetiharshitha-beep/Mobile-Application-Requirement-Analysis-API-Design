import logging
import uuid

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from .notification_service import send_notification
from .stripe_service import (
    StripeIntegrationError,
    create_payment_intent,
)


logger = logging.getLogger(__name__)


def initiate_payment(*, payment):
    """
    Create a Stripe test-mode PaymentIntent for the payment.

    Business rules:
    - Payment amount comes from the validated Payment record.
    - Stripe receives the amount in the smallest currency unit.
    - The Stripe PaymentIntent ID is stored as transaction_id.
    - Payment starts in PENDING state.
    - Payment method is STRIPE.
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
            extra={
                "payment_id": str(payment.id),
            },
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

    payment.save(
        update_fields=[
            "payment_status",
        ]
    )

    return payment


def process_payment_webhook(
    *,
    payment,
    payment_status,
):
    """
    Process a payment provider webhook.

    Database operations:
    - Update payment status.
    - When payment succeeds, confirm the booking.

    Payment and booking updates are handled
    inside one atomic transaction.

    If either database update fails,
    both database changes are rolled back.
    """

    with transaction.atomic():

        payment.payment_status = payment_status

        payment.save(
            update_fields=[
                "payment_status",
            ]
        )

        if payment_status == "SUCCESS":
            booking = payment.booking

            booking.status = "confirmed"

            booking.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            channel_layer = get_channel_layer()

            transaction.on_commit(
                lambda: async_to_sync(
                    channel_layer.group_send
                )(
                    f"booking_{booking.id}",
                    {
                        "type": "booking_status_update",
                        "booking_id": str(
                            booking.id
                        ),
                        "status": "confirmed",
                        "message": (
                            "Booking status changed "
                            "to confirmed."
                        ),
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