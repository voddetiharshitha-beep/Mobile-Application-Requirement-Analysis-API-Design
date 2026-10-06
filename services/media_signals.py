from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import Media


@receiver(post_delete, sender=Media)
def delete_media_file_on_delete(
    sender,
    instance,
    **kwargs,
):
    """
    Delete the physical media file when
    the Media database record is deleted.
    """

    if not instance.file:
        return

    try:
        instance.file.delete(
            save=False,
        )
    except (
        FileNotFoundError,
        ValueError,
    ):
        pass


@receiver(pre_save, sender=Media)
def delete_old_media_file_on_update(
    sender,
    instance,
    **kwargs,
):
    """
    Delete the previous physical media file when
    a Media record is updated with a new file.
    """

    if not instance.pk:
        return

    try:
        old_instance = sender.objects.get(
            pk=instance.pk,
        )
    except sender.DoesNotExist:
        return

    if not old_instance.file:
        return

    if (
        instance.file
        and old_instance.file.name
        != instance.file.name
    ):
        try:
            old_instance.file.delete(
                save=False,
            )
        except (
            FileNotFoundError,
            ValueError,
        ):
            pass