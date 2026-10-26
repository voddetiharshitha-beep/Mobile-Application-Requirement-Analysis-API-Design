
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from services.models import Category, Provider, Service, ServiceImage


class ServiceImageUploadRetryTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.provider_user = User.objects.create_user(
            username="image_retry_provider",
            password="TestPassword123!",
        )
        self.customer = User.objects.create_user(
            username="image_retry_customer",
            password="TestPassword123!",
        )

        self.provider = Provider.objects.create(
            user=self.provider_user,
            name="Image Retry Provider",
            description="Provider for upload retry tests.",
        )
        self.category = Category.objects.create(
            name="Image Retry Category",
            description="Category for upload retry tests.",
        )
        self.service = Service.objects.create(
            name="Image Retry Service",
            description="Service for upload retry tests.",
            category=self.category,
            provider=self.provider,
            price="100.00",
            location="Test Location",
        )

        self.client.force_authenticate(user=self.provider_user)
        self.url = reverse(
            "service-image-list-create",
            kwargs={"service_id": self.service.id},
        )

    def create_image(self, *, color, name="retry.jpg"):
        image = Image.new("RGB", (100, 100), color=color)
        buffer = BytesIO()
        image.save(buffer, format="JPEG")

        return SimpleUploadedFile(
            name,
            buffer.getvalue(),
            content_type="image/jpeg",
        )

    def upload(self, image, key):
        return self.client.post(
            self.url,
            {"image": image},
            format="multipart",
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def test_valid_upload_succeeds(self):
        response = self.upload(
            self.create_image(color="red"),
            str(uuid4()),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            ServiceImage.objects.filter(service=self.service).count(),
            1,
        )

    def test_retry_with_same_key_and_image_does_not_duplicate_record(self):
        key = str(uuid4())

        first_response = self.upload(
            self.create_image(color="red"),
            key,
        )
        self.assertEqual(first_response.status_code, 201)

        original_id = first_response.data["id"]

        retry_response = self.upload(
            self.create_image(color="red"),
            key,
        )

        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(retry_response.data["id"], original_id)
        self.assertEqual(
            ServiceImage.objects.filter(service=self.service).count(),
            1,
        )

    def test_same_key_with_different_image_returns_conflict(self):
        key = str(uuid4())

        first_response = self.upload(
            self.create_image(color="red"),
            key,
        )
        self.assertEqual(first_response.status_code, 201)

        second_response = self.upload(
            self.create_image(color="blue"),
            key,
        )

        self.assertEqual(second_response.status_code, 409)
        self.assertEqual(
            ServiceImage.objects.filter(service=self.service).count(),
            1,
        )

    def test_invalid_image_is_rejected(self):
        response = self.upload(
            SimpleUploadedFile(
                "invalid.jpg",
                b"this is not a real image",
                content_type="image/jpeg",
            ),
            str(uuid4()),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            ServiceImage.objects.filter(service=self.service).count(),
            0,
        )

    def test_oversized_image_is_rejected(self):
        oversized_content = b"x" * (
            settings.MAX_IMAGE_UPLOAD_SIZE + 1
        )
        image = SimpleUploadedFile(
            "oversized.jpg",
            oversized_content,
            content_type="image/jpeg",
        )

        response = self.upload(image, str(uuid4()))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            ServiceImage.objects.filter(service=self.service).count(),
            0,
        )

    def test_non_owner_cannot_upload_service_image(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.post(
            self.url,
            {"image": self.create_image(color="red")},
            format="multipart",
            HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            ServiceImage.objects.filter(service=self.service).count(),
            0,
        )

    @patch(
        "services.views.complete_idempotent_request",
        side_effect=RuntimeError("Simulated completion failure"),
    )
    def test_completion_failure_does_not_create_duplicate_on_retry(
        self,
        mocked_complete,
    ):
        key = str(uuid4())

        with self.assertRaises(RuntimeError):
            self.upload(self.create_image(color="red"), key)

        self.assertEqual(
            ServiceImage.objects.filter(service=self.service).count(),
            1,
        )

        mocked_complete.side_effect = None

        retry_response = self.upload(
            self.create_image(color="red"),
            key,
        )

        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(
            ServiceImage.objects.filter(service=self.service).count(),
            1,
        )

    def test_storage_failure_can_be_retried_without_duplicate_record(self):
        key = str(uuid4())
        storage = ServiceImage._meta.get_field("image").storage

        with patch.object(
            storage,
            "save",
            side_effect=OSError("Simulated storage outage"),
        ):
            with self.assertRaises(OSError):
                self.upload(self.create_image(color="red"), key)

        self.assertEqual(
            ServiceImage.objects.filter(service=self.service).count(),
            0,
        )

        retry_response = self.upload(
            self.create_image(color="red"),
            key,
        )

        self.assertEqual(retry_response.status_code, 201)
        self.assertEqual(
            ServiceImage.objects.filter(service=self.service).count(),
            1,
        )

    def test_uploaded_image_appears_in_service_image_list(self):
        key = str(uuid4())

        upload_response = self.upload(
            self.create_image(color="red"),
            key,
        )

        self.assertEqual(upload_response.status_code, 201)
        uploaded_id = upload_response.data["id"]

        list_response = self.client.get(self.url)

        self.assertEqual(list_response.status_code, 200)
        self.assertIn(
            uploaded_id,
            [item["id"] for item in list_response.data["results"]],
        )
        self.assertEqual(
            ServiceImage.objects.filter(service=self.service).count(),
            1,
        )

    def test_provider_upload_retry_is_visible_to_customer(self):
        key = str(uuid4())

        # Provider uploads the image.
        first_response = self.upload(
            self.create_image(color="red"),
            key,
        )
        self.assertEqual(first_response.status_code, 201)
        uploaded_id = first_response.data["id"]

        # Retry with the same key and image.
        retry_response = self.upload(
            self.create_image(color="red"),
            key,
        )
        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(retry_response.data["id"], uploaded_id)

        # Clear provider authentication and log in as the customer.
        self.client.force_authenticate(user=None)

        login_response = self.client.post(
            "/api/v1/token/",
            {
                "username": "image_retry_customer",
                "password": "TestPassword123!",
            },
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertIn("access", login_response.data)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )

        # Customer discovers the service.
        services_response = self.client.get("/api/v1/services/")
        self.assertEqual(services_response.status_code, 200)

        service_ids = [
            item["id"]
            for item in services_response.data["results"]
        ]
        self.assertIn(str(self.service.id), service_ids)

        # Customer retrieves the service image list.
        images_response = self.client.get(self.url)
        self.assertEqual(images_response.status_code, 200)

        image_ids = [
            item["id"]
            for item in images_response.data["results"]
        ]
        self.assertIn(uploaded_id, image_ids)

        # Confirm that retry did not create a duplicate record.
        self.assertEqual(
            ServiceImage.objects.filter(service=self.service).count(),
            1,
        )
