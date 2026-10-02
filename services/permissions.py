from rest_framework.permissions import BasePermission

from .models import Provider


class IsCustomer(BasePermission):
    """
    Allows authenticated users who are not providers
    and are not staff members.
    """

    message = "Only customers can use this endpoint."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if user.is_staff:
            return False

        if Provider.objects.filter(
            user=user,
        ).exists():
            return False

        return True