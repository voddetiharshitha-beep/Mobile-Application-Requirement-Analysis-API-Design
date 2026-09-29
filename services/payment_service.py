from uuid import uuid4

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from .notification_service import send_notification


def initiate_payment(*, payment):
    """
    Prepare a mock payment.

    Business rules:
    - Generate a mock transaction ID.
    - Payment starts in PENDING state.
    - Payment method is MOCK.
    """

    payment.transaction_id = (
        f"MOCK-{uuid4().hex[:12].upper()}"
    )

    payment.payment_status = "PENDING"
    payment.payment_method = "MOCK"

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
    Process a mock payment result.

    The serializer/view is responsible for checking:
    - the payment belongs to the current user
    - the payment is currently pending

    This service only applies the payment result.
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

    Business rules:
    - Update the payment status.
    - When payment succeeds:
      - confirm the booking
      - notify connected WebSocket clients
      - create payment-success notification
      - create booking-confirmed notification
    """

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

        async_to_sync(
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
                    "Booking status changed to confirmed."
                ),
            },
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

