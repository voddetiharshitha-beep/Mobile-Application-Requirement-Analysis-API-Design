from django.core.cache import cache


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
    """

    service = serializer.save()

    clear_service_list_cache()

    return service


def delete_service(*, service):
    """
    Delete an existing service.
    """

    service.delete()

    clear_service_list_cache()