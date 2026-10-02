from .tasks import (
    create_notification,
    notify_saved_customers_service_unavailable,
)


def send_notification(
    *,
    recipient_id,
    booking_id,
    notification_type,
    message,
):
    """
    Queue a booking-related notification
    asynchronously using Celery.
    """

    return create_notification.delay(
        recipient_id,
        booking_id,
        notification_type,
        message,
    )


def send_saved_service_unavailable_notification(
    *,
    service_id,
):
    """
    Queue notifications for all customers who saved
    the service.
    """

    return (
        notify_saved_customers_service_unavailable.delay(
            str(service_id)
        )
    )