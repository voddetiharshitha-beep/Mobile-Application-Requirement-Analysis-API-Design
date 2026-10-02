from django.db import IntegrityError, transaction

from .models import SavedService, Service


class SavedServiceAlreadyExists(Exception):
    """Raised when a customer has already saved a service."""


class ServiceNotFound(Exception):
    """Raised when the requested service does not exist."""


@transaction.atomic
def save_service(*, customer, service):
    """
    Save a service for a customer.

    Business rules:
    - The service must exist.
    - A customer cannot save the same service twice.
    """

    if not Service.objects.filter(
        id=service.id
    ).exists():
        raise ServiceNotFound()

    try:
        return SavedService.objects.create(
            customer=customer,
            service=service,
        )
    except IntegrityError:
        raise SavedServiceAlreadyExists()


def list_saved_services(*, customer):
    """
    Return only the saved services belonging to the customer.
    """

    return (
        SavedService.objects
        .select_related("service")
        .filter(customer=customer)
        .order_by("-created_at")
    )


def delete_saved_service(*, customer, saved_service_id):
    """
    Delete a customer's saved-service relationship.

    Returning None when the record does not belong to the
    customer prevents cross-user access.
    """

    saved_service = (
        SavedService.objects
        .filter(
            id=saved_service_id,
            customer=customer,
        )
        .first()
    )

    if saved_service is None:
        return False

    saved_service.delete()

    return True