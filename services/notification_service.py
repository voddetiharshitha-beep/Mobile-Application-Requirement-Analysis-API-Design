
import logging

from config.metrics import record_notification_event
from config.middleware import request_id_context

from .tasks import (
    create_notification,
    notify_saved_customers_service_unavailable,
)

logger = logging.getLogger(__name__)


def _current_correlation_id():
    """Return the current request ID when one is available."""
    request_id = request_id_context.get()

    if not request_id or request_id == "-":
        return None

    return request_id


def send_notification(
    *,
    recipient_id,
    booking_id,
    notification_type,
    message,
):
    """Queue a booking notification and record its queue outcome."""
    correlation_id = _current_correlation_id()
    task_kwargs = {}

    if correlation_id:
        task_kwargs["correlation_id"] = correlation_id

    try:
        result = create_notification.delay(
            recipient_id,
            booking_id,
            notification_type,
            message,
            **task_kwargs,
        )
    except Exception:
        record_notification_event("queue", "failed")
        logger.exception(
            "Failed to queue booking notification",
            extra={
                "correlation_id": correlation_id or "-",
                "booking_id": str(booking_id),
                "notification_type": str(notification_type),
            },
        )
        return None

    record_notification_event("queue", "queued")
    return result


def send_saved_service_unavailable_notification(
    *,
    service_id,
):
    """Queue saved-service notifications and record their queue outcome."""
    correlation_id = _current_correlation_id()
    task_kwargs = {}

    if correlation_id:
        task_kwargs["correlation_id"] = correlation_id

    try:
        result = notify_saved_customers_service_unavailable.delay(
            str(service_id),
            **task_kwargs,
        )
    except Exception:
        record_notification_event("queue", "failed")
        logger.exception(
            "Failed to queue saved-service notifications",
            extra={
                "correlation_id": correlation_id or "-",
                "service_id": str(service_id),
            },
        )
        return None

    record_notification_event("queue", "queued")
    return result
