from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from PIL import Image

from services.models import Media


class MediaCleanupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="cleanup_user",
            password="TestPassword123!",
        )

    def create_image(
        self,
        *,
        name="cleanup.jpg",
    ):
        image = Image.new(
            "RGB",
            (100, 100),
            color="white",
        )

        buffer = BytesIO()

        image.save(
            buffer,
            format="JPEG",
        )

        buffer.seek(0)

        return SimpleUploadedFile(
            name,
            buffer.read(),
            content_type="image/jpeg",
        )

    def create_media(self):
        uploaded_file = self.create_image()

        return Media.objects.create(
            owner=self.user,
            file=uploaded_file,
            media_type="PROFILE",
            visibility="PRIVATE",
            original_filename="cleanup.jpg",
            mime_type="image/jpeg",
            file_size=uploaded_file.size,
        )

    def test_media_file_is_deleted_when_media_record_is_deleted(self):
        media = self.create_media()

        file_name = media.file.name

        self.assertTrue(
            media.file.storage.exists(
                file_name,
            )
        )

        media.delete()

        self.assertFalse(
            media.file.storage.exists(
                file_name,
            )
        )

    def test_old_media_file_is_deleted_when_file_is_replaced(self):
        media = self.create_media()

        old_file_name = media.file.name

        new_file = self.create_image(
            name="replacement.jpg",
        )

        media.file = new_file
        media.save()

        self.assertFalse(
            media.file.storage.exists(
                old_file_name,
            )
        )

        self.assertTrue(
            media.file.storage.exists(
                media.file.name,
            )
        )