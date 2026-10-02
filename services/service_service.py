from django.core.cache import cache

from .notification_service import (
    send_saved_service_unavailable_notification,
)
from .tasks import notify_saved_customers_service_unavailable


def clear_service_list_cache():
    """
    Clear all cached Service List API responses.
    """

    try:
        cache.delete_pattern("service_list:*")
    except AttributeError:
        pass


def create_service(*, serializer, provider):
    """
    Create a service for the given provider.
    """

    service = serializer.save(
        provider=provider
    )

    clear_service_list_cache()

    return service


def update_service(*, serializer):
    """
    Update an existing service.

    If the service changes from available to unavailable,
    queue a Celery task to notify customers who saved it.
    """

    service = serializer.instance

    was_available = service.status

    service = serializer.save()

    is_available = service.status

    clear_service_list_cache()

    if was_available and not is_available:
        notify_saved_customers_service_unavailable.delay(
            str(service.id)
        )

    return service


def delete_service(*, service):
    """
    Delete an existing service.
    """

    service.delete()

    clear_service_list_cache()