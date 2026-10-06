import os

from django.core.exceptions import ValidationError

from .models import Media


def create_media(
    *,
    owner,
    uploaded_file,
    media_type,
    visibility="PRIVATE",
    service=None,
):
    """
    Create a Media record for an uploaded image.

    Validation of the image itself is handled by the
    validate_uploaded_image model validator.
    """

    if not uploaded_file:
        raise ValidationError(
            "An image file is required."
        )

    allowed_media_types = {
        choice[0]
        for choice in Media.MEDIA_TYPE_CHOICES
    }

    if media_type not in allowed_media_types:
        raise ValidationError(
            "Invalid media type."
        )

    allowed_visibility = {
        choice[0]
        for choice in Media.VISIBILITY_CHOICES
    }

    if visibility not in allowed_visibility:
        raise ValidationError(
            "Invalid media visibility."
        )

    if media_type == "SERVICE" and service is None:
        raise ValidationError(
            "A service is required for service media."
        )

    if media_type == "PROFILE" and service is not None:
        raise ValidationError(
            "Profile media cannot be linked to a service."
        )

    original_filename = os.path.basename(
        uploaded_file.name
    )

    media = Media.objects.create(
        owner=owner,
        service=service,
        file=uploaded_file,
        media_type=media_type,
        visibility=visibility,
        original_filename=original_filename,
        mime_type=getattr(
            uploaded_file,
            "content_type",
            "",
        ),
        file_size=uploaded_file.size,
    )

    return media


def can_access_media(
    *,
    media,
    user=None,
):
    """
    Determine whether a user can access a media object.

    Public media:
        Anyone can access it.

    Private media:
        Only the media owner can access it.

    Anonymous users:
        Can access public media only.
    """

    if media.visibility == "PUBLIC":
        return True

    if media.visibility == "PRIVATE":
        if user is None:
            return False

        if not user.is_authenticated:
            return False

        return media.owner_id == user.id

    return False


def get_media_for_access(
    *,
    media_id,
    user=None,
):
    """
    Retrieve media only when the requesting user
    has permission to access it.
    """

    try:
        media = Media.objects.select_related(
            "owner",
            "service",
        ).get(
            id=media_id,
        )
    except Media.DoesNotExist:
        return None

    if not can_access_media(
        media=media,
        user=user,
    ):
        return None

    return media