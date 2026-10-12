import logging

from .tasks import (
    create_notification,
    notify_saved_customers_service_unavailable,
)

logger = logging.getLogger(__name__)


def send_notification(
    *,
    recipient_id,
    booking_id,
    notification_type,
    message,
):
    """Queue a booking notification without hiding broker failures."""
    try:
        return create_notification.delay(
            recipient_id,
            booking_id,
            notification_type,
            message,
        )
    except Exception:
        logger.exception(
            "Failed to queue booking notification",
            extra={
                "booking_id": str(booking_id),
                "notification_type": str(notification_type),
            },
        )
        return None


def send_saved_service_unavailable_notification(
    *,
    service_id,
):
    """Queue saved-customer notifications and log broker failures."""
    try:
        return notify_saved_customers_service_unavailable.delay(
            str(service_id)
        )
    except Exception:
        logger.exception(
            "Failed to queue saved-service notifications",
            extra={"service_id": str(service_id)},
        )
        return None
