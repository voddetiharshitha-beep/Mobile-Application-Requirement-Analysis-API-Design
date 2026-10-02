from importlib import import_module


try:
    shared_task = import_module("celery").shared_task
except ModuleNotFoundError:
    # Keep local development usable when Celery is not installed.
    def shared_task(function):
        return function


from .models import (
    Notification,
    SavedService,
    Service,
)


@shared_task
def create_notification(
    recipient_id,
    booking_id,
    notification_type,
    message,
    service_id=None,
):
    """
    Create a notification safely.

    Booking notifications are associated with a booking.

    Saved-service notifications are associated with a service.

    The database uniqueness constraints prevent duplicate
    notifications when Celery retries a task.
    """

    if service_id is not None:
        notification, created = (
            Notification.objects.get_or_create(
                recipient_id=recipient_id,
                service_id=service_id,
                notification_type=notification_type,
                defaults={
                    "message": message,
                },
            )
        )
    else:
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


@shared_task
def notify_saved_customers_service_unavailable(
    service_id,
):
    """
    Notify every customer who saved a service when
    that service becomes unavailable.
    """

    service = Service.objects.filter(
        id=service_id,
    ).first()

    if service is None:
        return []

    saved_services = (
        SavedService.objects
        .filter(
            service=service,
        )
        .values_list(
            "customer_id",
            flat=True,
        )
    )

    notification_ids = []

    for customer_id in saved_services:
        notification = Notification.objects.get_or_create(
            recipient_id=customer_id,
            service_id=service.id,
            notification_type="SAVED_SERVICE_UNAVAILABLE",
            defaults={
                "message": (
                    f"The saved service "
                    f"'{service.name}' "
                    "is no longer available."
                ),
            },
        )[0]

        notification_ids.append(
            str(notification.id)
        )

    return notification_ids