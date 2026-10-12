import logging

from django.core.cache import cache

from .tasks import notify_saved_customers_service_unavailable


logger = logging.getLogger(__name__)


def clear_service_list_cache():
    """
    Invalidate cached service-list responses.

    Cache failures are logged but do not prevent service operations.
    """
    try:
        cache.delete_pattern("service_list:*")
    except Exception:
        logger.exception(
            "Failed to invalidate cached service-list responses."
        )


def create_service(*, serializer, provider):
    """
    Create a service for the given provider.
    """
    service = serializer.save(provider=provider)

    clear_service_list_cache()

    return service


def update_service(*, serializer):
    """
    Update a service and gracefully handle notification queue failures.
    """
    service = serializer.instance
    was_available = service.status

    service = serializer.save()
    is_available = service.status

    clear_service_list_cache()

    if was_available and not is_available:
        try:
            notify_saved_customers_service_unavailable.delay(
                str(service.id)
            )
        except Exception:
            logger.exception(
                "Failed to queue service-unavailable notification "
                "for service_id=%s",
                service.id,
            )

    return service


def delete_service(*, service):
    """
    Delete a service and invalidate cached service lists.
    """
    service.delete()
    clear_service_list_cache()