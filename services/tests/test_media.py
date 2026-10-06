from io import BytesIO
import uuid

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from PIL import Image
from rest_framework.test import APIClient

from services.media_service import can_access_media
from services.models import Media


class MediaAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.owner = User.objects.create_user(
            username="media_owner",
            password="TestPassword123!",
        )

        self.other_user = User.objects.create_user(
            username="media_other",
            password="TestPassword123!",
        )

    def create_image(
        self,
        *,
        name="test.jpg",
        image_format="JPEG",
        size=(100, 100),
    ):
        image = Image.new(
            "RGB",
            size,
            color="white",
        )

        buffer = BytesIO()

        image.save(
            buffer,
            format=image_format,
        )

        buffer.seek(0)

        return SimpleUploadedFile(
            name,
            buffer.read(),
            content_type=f"image/{image_format.lower()}",
        )

    def create_media(
        self,
        *,
        owner,
        visibility="PRIVATE",
        name="test.jpg",
    ):
        uploaded_file = self.create_image(
            name=name,
        )

        media = Media.objects.create(
            owner=owner,
            file=uploaded_file,
            media_type="PROFILE",
            visibility=visibility,
            original_filename=name,
            mime_type="image/jpeg",
            file_size=uploaded_file.size,
        )

        return media

    def test_public_media_is_accessible_anonymously(self):
        media = self.create_media(
            owner=self.owner,
            visibility="PUBLIC",
        )

        response = self.client.get(
            reverse(
                "media-download",
                kwargs={
                    "media_id": media.id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_private_media_is_not_accessible_anonymously(self):
        media = self.create_media(
            owner=self.owner,
            visibility="PRIVATE",
        )

        response = self.client.get(
            reverse(
                "media-download",
                kwargs={
                    "media_id": media.id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_private_media_access_function_allows_owner(self):
        media = self.create_media(
            owner=self.owner,
            visibility="PRIVATE",
        )

        self.assertTrue(
            can_access_media(
                media=media,
                user=self.owner,
            )
        )

    def test_private_media_is_accessible_by_owner(self):
        media = self.create_media(
            owner=self.owner,
            visibility="PRIVATE",
        )

        self.client.force_authenticate(
            user=self.owner,
        )

        response = self.client.get(
            reverse(
                "media-download",
                kwargs={
                    "media_id": media.id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_private_media_is_not_accessible_by_other_user(self):
        media = self.create_media(
            owner=self.owner,
            visibility="PRIVATE",
        )

        self.client.force_authenticate(
            user=self.other_user,
        )

        response = self.client.get(
            reverse(
                "media-download",
                kwargs={
                    "media_id": media.id,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_missing_media_returns_404(self):
        self.client.force_authenticate(
            user=self.owner,
        )

        response = self.client.get(
            reverse(
                "media-download",
                kwargs={
                    "media_id": uuid.uuid4(),
                },
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )