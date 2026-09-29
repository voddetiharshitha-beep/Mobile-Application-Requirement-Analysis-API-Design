from django.db import IntegrityError, transaction
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import (
    Booking,
    BookingIdempotencyKey,
)
from .notification_service import send_notification


def create_booking(
    *,
    customer,
    service,
    booking_date,
    booking_time,
    idempotency_key=None,
):
    """
    Create a new booking safely.

    Business rules:
    - The customer comes from the authenticated user.
    - The provider comes from the selected service.
    - The booking amount comes from the service price.

    Idempotency:
    - If the same customer sends the same
      Idempotency-Key again, the existing booking
      is returned.
    - A database uniqueness constraint protects
      against concurrent duplicate requests.
    """

    # Check whether this customer has already used
    # this idempotency key.
    if idempotency_key:
        try:
            existing_key = (
                BookingIdempotencyKey.objects
                .select_related("booking")
                .get(
                    user=customer,
                    key=idempotency_key,
                )
            )

            return existing_key.booking, False

        except BookingIdempotencyKey.DoesNotExist:
            pass

    try:
        with transaction.atomic():

            booking = Booking.objects.create(
                customer=customer,
                provider=service.provider,
                service=service,
                booking_date=booking_date,
                booking_time=booking_time,
                amount=service.price,
            )

            if idempotency_key:
                BookingIdempotencyKey.objects.create(
                    user=customer,
                    key=idempotency_key,
                    booking=booking,
                )

            transaction.on_commit(
                lambda: send_notification(
                    recipient_id=booking.customer_id,
                    booking_id=str(booking.id),
                    notification_type="BOOKING_CREATED",
                    message=(
                        "Your booking has been "
                        "created successfully."
                    ),
                )
            )

            return booking, True

    except IntegrityError:
        # Another concurrent request may have created
        # the same customer + idempotency key first.
        if idempotency_key:
            existing_key = (
                BookingIdempotencyKey.objects
                .select_related("booking")
                .get(
                    user=customer,
                    key=idempotency_key,
                )
            )

            return existing_key.booking, False

        raise


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
            "message": (
                "Booking status changed to cancelled."
            ),
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
    Update a booking status safely under concurrent requests.

    A database row lock ensures that concurrent requests
    cannot successfully update the same booking at the same time.
    """

    with transaction.atomic():

        locked_booking = (
            Booking.objects
            .select_for_update()
            .get(pk=booking.pk)
        )

        if not locked_booking.can_transition_to(
            new_status
        ):
            raise ValueError(
                f"Cannot change booking status from "
                f"{locked_booking.status} to {new_status}."
            )

        locked_booking.status = new_status

        locked_booking.save(
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
                f"booking_{locked_booking.id}",
                {
                    "type": "booking_status_update",
                    "booking_id": str(
                        locked_booking.id
                    ),
                    "status": locked_booking.status,
                    "message": (
                        f"Booking status changed to "
                        f"{locked_booking.status}."
                    ),
                },
            )
        )

        if new_status == "in_progress":
            transaction.on_commit(
                lambda: send_notification(
                    recipient_id=locked_booking.customer_id,
                    booking_id=str(locked_booking.id),
                    notification_type="PROVIDER_STARTED",
                    message=(
                        "The provider has started "
                        "your service."
                    ),
                )
            )

        elif new_status == "completed":
            transaction.on_commit(
                lambda: send_notification(
                    recipient_id=locked_booking.customer_id,
                    booking_id=str(locked_booking.id),
                    notification_type="BOOKING_COMPLETED",
                    message=(
                        "Your booking has been completed."
                    ),
                )
            )

        return locked_booking