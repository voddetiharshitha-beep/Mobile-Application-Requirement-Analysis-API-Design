from django.db import transaction
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Booking
from .notification_service import send_notification


def create_booking(
    *,
    customer,
    service,
    booking_date,
    booking_time,
):
    """
    Create a new booking.

    Business rules:
    - The customer comes from the authenticated user.
    - The provider comes from the selected service.
    - The booking amount comes from the service price.
    """

    booking = Booking.objects.create(
        customer=customer,
        provider=service.provider,
        service=service,
        booking_date=booking_date,
        booking_time=booking_time,
        amount=service.price,
    )

    transaction.on_commit(
        lambda: send_notification(
            recipient_id=booking.customer_id,
            booking_id=str(booking.id),
            notification_type="BOOKING_CREATED",
            message="Your booking has been created successfully.",
        )
    )

    return booking


def cancel_booking(*, booking):
    """
    Cancel a booking according to the booking business rules.
    """

    if booking.status == "cancelled":
        raise ValueError(
            "Booking is already cancelled."
        )

    if booking.status == "completed":
        raise ValueError(
            "Completed booking cannot be cancelled."
        )

    booking.status = "cancelled"

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
            "booking_id": str(booking.id),
            "status": booking.status,
            "message": "Booking status changed to cancelled.",
        },
    )

    transaction.on_commit(
        lambda: send_notification(
            recipient_id=booking.customer_id,
            booking_id=str(booking.id),
            notification_type="BOOKING_CANCELLED",
            message="Your booking has been cancelled.",
        )
    )

    return booking


def update_booking_status(
    *,
    booking,
    new_status,
):
    """
    Update a booking status using
    the model's state-transition rules.
    """

    if not booking.can_transition_to(new_status):
        raise ValueError(
            f"Cannot change booking status from "
            f"{booking.status} to {new_status}."
        )

    booking.status = new_status

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
            "booking_id": str(booking.id),
            "status": booking.status,
            "message": (
                f"Booking status changed to "
                f"{booking.status}."
            ),
        },
    )

    if new_status == "in_progress":
        transaction.on_commit(
            lambda: send_notification(
                recipient_id=booking.customer_id,
                booking_id=str(booking.id),
                notification_type="PROVIDER_STARTED",
                message="The provider has started your service.",
            )
        )

    elif new_status == "completed":
        transaction.on_commit(
            lambda: send_notification(
                recipient_id=booking.customer_id,
                booking_id=str(booking.id),
                notification_type="BOOKING_COMPLETED",
                message="Your booking has been completed.",
            )
        )

    return booking