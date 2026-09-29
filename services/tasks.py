from importlib import import_module


try:
    shared_task = import_module("celery").shared_task
except ModuleNotFoundError:
    # Keep local development usable when Celery is not installed.
    def shared_task(function):
        return function


from .models import Notification


@shared_task
def create_notification(
    recipient_id,
    booking_id,
    notification_type,
    message,
):
    """
    Create a notification safely.

    If Celery retries the same notification task,
    the existing notification is returned instead
    of creating a duplicate notification.
    """

    notification, created = (
        Notification.objects.get_or_create(
            recipient_id=recipient_id,
            booking_id=booking_id,
            notification_type=notification_type,
            defaults={
                "message": message,
            },
        )
    )

    return str(notification.id)