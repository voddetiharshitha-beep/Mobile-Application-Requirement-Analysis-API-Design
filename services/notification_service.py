from .tasks import create_notification


def send_notification(
    *,
    recipient_id,
    booking_id,
    notification_type,
    message,
):
    """
    Queue a notification to be created
    asynchronously by Celery.
    """

    return create_notification.delay(
        recipient_id,
        booking_id,
        notification_type,
        message,
    )