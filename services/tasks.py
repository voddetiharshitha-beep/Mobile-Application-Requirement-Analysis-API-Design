
import logging
from importlib import import_module

from django.db import InterfaceError, OperationalError

from config.metrics import record_notification_event

try:
    shared_task = import_module("celery").shared_task
except ModuleNotFoundError:
    # Keep local development usable when Celery is not installed.
    def shared_task(*decorator_args, **decorator_kwargs):
        if (
            len(decorator_args) == 1
            and callable(decorator_args[0])
            and not decorator_kwargs
        ):
            return decorator_args[0]

        def decorator(function):
            return function

        return decorator


from .models import Notification, SavedService, Service

logger = logging.getLogger(__name__)

RETRYABLE_DATABASE_ERRORS = (OperationalError, InterfaceError)


@shared_task(
    autoretry_for=RETRYABLE_DATABASE_ERRORS,
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def create_notification(
    recipient_id,
    booking_id,
    notification_type,
    message,
    service_id=None,
    correlation_id=None,
):
    """Create a deduplicated notification and record its processing outcome."""
    try:
        if service_id is not None:
            notification, created = Notification.objects.get_or_create(
                recipient_id=recipient_id,
                service_id=service_id,
                notification_type=notification_type,
                defaults={"message": message},
            )
        else:
            notification, created = Notification.objects.get_or_create(
                recipient_id=recipient_id,
                booking_id=booking_id,
                notification_type=notification_type,
                defaults={"message": message},
            )
    except RETRYABLE_DATABASE_ERRORS:
        record_notification_event("processing", "retryable_error")
        logger.exception(
            "Notification database operation failed; task will retry",
            extra={
                "correlation_id": correlation_id or "-",
                "notification_type": str(notification_type),
            },
        )
        raise

    outcome = "created" if created else "duplicate"
    record_notification_event("processing", outcome)

    logger.info(
        "Notification record processed",
        extra={
            "correlation_id": correlation_id or "-",
            "notification_id": str(notification.id),
            "notification_type": str(notification_type),
            "notification_created": created,
        },
    )

    return str(notification.id)


@shared_task(
    autoretry_for=RETRYABLE_DATABASE_ERRORS,
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def notify_saved_customers_service_unavailable(
    service_id,
    correlation_id=None,
):
    """Create deduplicated saved-service notifications and record outcomes."""
    try:
        service = Service.objects.filter(id=service_id).first()

        if service is None:
            record_notification_event("processing", "failed")
            logger.warning(
                "Saved-service notification skipped: service not found",
                extra={
                    "correlation_id": correlation_id or "-",
                    "service_id": str(service_id),
                },
            )
            return []

        customer_ids = (
            SavedService.objects
            .filter(service=service)
            .values_list("customer_id", flat=True)
        )

        notification_ids = []

        for customer_id in customer_ids:
            notification, created = Notification.objects.get_or_create(
                recipient_id=customer_id,
                service_id=service.id,
                notification_type="SAVED_SERVICE_UNAVAILABLE",
                defaults={
                    "message": (
                        f"The saved service '{service.name}' "
                        "is no longer available."
                    ),
                },
            )

            outcome = "created" if created else "duplicate"
            record_notification_event("processing", outcome)
            notification_ids.append(str(notification.id))

    except RETRYABLE_DATABASE_ERRORS:
        record_notification_event("processing", "retryable_error")
        logger.exception(
            "Saved-service notification database operation failed; "
            "task will retry",
            extra={
                "correlation_id": correlation_id or "-",
                "service_id": str(service_id),
            },
        )
        raise

    logger.info(
        "Saved-service notification records processed",
        extra={
            "correlation_id": correlation_id or "-",
            "service_id": str(service.id),
            "notification_count": len(notification_ids),
        },
    )

    return notification_ids
