from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.crypto import get_random_string
from rest_framework.test import APITestCase

from services.models import Booking, Category, Provider, Service
from services.serializers import (
    BookingSerializer,
    RegisterSerializer,
    ServiceImageSerializer,
)


User = get_user_model()


class InputValidationTests(APITestCase):
    """
    Input validation and safe rejection tests.

    These tests verify that invalid client input is rejected
    without creating or modifying database records.
    """

    @classmethod
    def setUpTestData(cls):
        cls.test_password = get_random_string(32)

        cls.user = User.objects.create_user(
            username="validation_user",
            email="validation@example.com",
            password=cls.test_password,
        )

        cls.provider_user = User.objects.create_user(
            username="validation_provider",
            email="provider@example.com",
            password=cls.test_password,
        )

        cls.provider = Provider.objects.create(
            user=cls.provider_user,
            name="Validation Provider",
            description="Provider used for validation tests.",
        )

        cls.category = Category.objects.create(
            name="Validation Category",
            description="Category used for validation tests.",
        )

        cls.service = Service.objects.create(
            name="Validation Service",
            description="Service used for validation tests.",
            location="Hyderabad",
            price="500.00",
            category=cls.category,
            provider=cls.provider,
        )

    # ---------------------------------------------------------
    # 1. EMPTY DATA
    # ---------------------------------------------------------

    def test_empty_registration_data_is_rejected(self):
        serializer = RegisterSerializer(
            data={}
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "username",
            serializer.errors,
        )

        self.assertIn(
            "password",
            serializer.errors,
        )

        self.assertEqual(
            User.objects.filter(
                username="",
            ).count(),
            0,
        )

    def test_empty_booking_data_is_rejected(self):
        serializer = BookingSerializer(
            data={}
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertTrue(
            len(serializer.errors) > 0
        )

    # ---------------------------------------------------------
    # 2. INVALID UUID
    # ---------------------------------------------------------

    def test_invalid_uuid_endpoint_is_rejected(self):
        self.client.force_authenticate(
            user=self.user
        )

        response = self.client.get(
            "/api/v1/services/not-a-valid-uuid/"
        )

        self.assertIn(
            response.status_code,
            [400, 404],
        )

        self.assertNotEqual(
            response.status_code,
            500,
        )

    # ---------------------------------------------------------
    # 3. EXTREMELY LONG STRINGS
    # ---------------------------------------------------------

    def test_extremely_long_username_is_rejected(self):
        long_username = "A" * 1000

        serializer = RegisterSerializer(
            data={
                "username": long_username,
                "email": "long@example.com",
                "password": self.test_password,
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "username",
            serializer.errors,
        )

    def test_extremely_long_service_name_is_rejected(self):
        self.client.force_authenticate(
            user=self.provider_user
        )

        payload = {
            "name": "A" * 5000,
            "description": "Valid description",
            "location": "Hyderabad",
            "price": "500.00",
            "category": str(self.category.id),
        }

        response = self.client.post(
            "/api/v1/services/",
            payload,
            format="json",
        )

        self.assertIn(
            response.status_code,
            [400, 403],
        )

        self.assertNotEqual(
            response.status_code,
            500,
        )

    # ---------------------------------------------------------
    # 4. INVALID NUMBERS
    # ---------------------------------------------------------

    def test_invalid_price_is_rejected(self):
        self.client.force_authenticate(
            user=self.provider_user
        )

        payload = {
            "name": "Invalid Price Service",
            "description": "Testing invalid numeric input.",
            "location": "Hyderabad",
            "price": "not-a-number",
            "category": str(self.category.id),
        }

        response = self.client.post(
            "/api/v1/services/",
            payload,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertNotEqual(
            response.status_code,
            500,
        )

    def test_invalid_booking_number_is_rejected(self):
        serializer = BookingSerializer(
            data={
                "service": str(self.service.id),
                "booking_date": "2026-10-10",
                "booking_time": "10:00:00",
                "amount": "not-a-number",
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "amount",
            serializer.errors,
        )

    # ---------------------------------------------------------
    # 5. INVALID DATES
    # ---------------------------------------------------------

    def test_invalid_booking_date_is_rejected(self):
        serializer = BookingSerializer(
            data={
                "service": str(self.service.id),
                "booking_date": "not-a-date",
                "booking_time": "10:00:00",
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "booking_date",
            serializer.errors,
        )

    def test_invalid_booking_time_is_rejected(self):
        serializer = BookingSerializer(
            data={
                "service": str(self.service.id),
                "booking_date": "2026-10-10",
                "booking_time": "not-a-time",
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "booking_time",
            serializer.errors,
        )

    # ---------------------------------------------------------
    # 6. INVALID FILE TYPES
    # ---------------------------------------------------------

    def test_invalid_service_image_file_type_is_rejected(self):
        invalid_file = SimpleUploadedFile(
            "malicious.exe",
            b"fake executable content",
            content_type="application/x-msdownload",
        )

        serializer = ServiceImageSerializer(
            data={
                "image": invalid_file,
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "image",
            serializer.errors,
        )

    # ---------------------------------------------------------
    # 7. UNEXPECTED JSON FIELDS
    # ---------------------------------------------------------

    def test_unexpected_registration_field_is_rejected(self):
        serializer = RegisterSerializer(
            data={
                "username": "unexpected_field_user",
                "email": "unexpected@example.com",
                "password": self.test_password,
                "unexpected_field": "should-not-be-accepted",
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertTrue(
            len(serializer.errors) > 0
        )

    def test_unexpected_booking_field_is_rejected(self):
        serializer = BookingSerializer(
            data={
                "service": str(self.service.id),
                "booking_date": "2026-10-10",
                "booking_time": "10:00:00",
                "unexpected_field": "attack",
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertTrue(
            len(serializer.errors) > 0
        )

    # ---------------------------------------------------------
    # SAFE REJECTION
    # ---------------------------------------------------------

    def test_invalid_registration_does_not_create_user(self):
        username = "should_not_be_created"

        serializer = RegisterSerializer(
            data={
                "username": username,
                "email": "invalid-email",
                "password": "",
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertFalse(
            User.objects.filter(
                username=username
            ).exists()
        )

    def test_invalid_service_price_does_not_create_service(self):
        self.client.force_authenticate(
            user=self.provider_user
        )

        before_count = Service.objects.count()

        response = self.client.post(
            "/api/v1/services/",
            {
                "name": "Should Not Exist",
                "description": "Invalid service",
                "location": "Hyderabad",
                "price": "invalid-number",
                "category": str(self.category.id),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            400,
        )

        self.assertEqual(
            Service.objects.count(),
            before_count,
        )

        self.assertNotEqual(
            response.status_code,
            500,
        )

    # ---------------------------------------------------------
    # 8. FILE UPLOAD SECURITY
    # ---------------------------------------------------------

    def test_invalid_extension_is_rejected(self):
        invalid_file = SimpleUploadedFile(
            "service.gif",
            b"fake image content",
            content_type="image/gif",
        )

        serializer = ServiceImageSerializer(
            data={
                "image": invalid_file,
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "image",
            serializer.errors,
        )

    
    
    def test_large_file_is_rejected(self):
        from PIL import Image
        import random

        width = 3000
        height = 3000

        random.seed(42)

        pixels = bytearray(
            random.getrandbits(8)
            for _ in range(width * height * 3)
        )

        image = Image.frombytes(
            "RGB",
            (width, height),
            bytes(pixels),
        )

        image_buffer = BytesIO()

        image.save(
            image_buffer,
            format="JPEG",
            quality=100,
        )

        image_data = image_buffer.getvalue()

        self.assertGreater(
            len(image_data),
            5 * 1024 * 1024,
        )

        large_file = SimpleUploadedFile(
            "large.jpg",
            image_data,
            content_type="image/jpeg",
        )

        serializer = ServiceImageSerializer(
            data={
                "image": large_file,
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "image",
            serializer.errors,
        )

        self.assertIn(
            "5 MB",
            str(
                serializer.errors["image"]
            ),
        )

    
    def test_missing_file_is_rejected(self):
        serializer = ServiceImageSerializer(
            data={}
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "image",
            serializer.errors,
        )

    def test_malicious_filename_is_rejected(self):
        malicious_file = SimpleUploadedFile(
            "../../evil.jpg",
            b"fake image content",
            content_type="image/jpeg",
        )

        serializer = ServiceImageSerializer(
            data={
                "image": malicious_file,
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "image",
            serializer.errors,
        )

    def test_incorrect_mime_type_is_rejected(self):
        png_bytes = (
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR"
            b"\x00\x00\x00\x01"
            b"\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00"
            b"\x90wS\xde"
        )

        invalid_mime_file = SimpleUploadedFile(
            "service.png",
            png_bytes,
            content_type="image/jpeg",
        )

        serializer = ServiceImageSerializer(
            data={
                "image": invalid_mime_file,
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "image",
            serializer.errors,
        )

    def test_fake_image_with_valid_extension_is_rejected(self):
        fake_image = SimpleUploadedFile(
            "fake.jpg",
            b"This is not a real JPEG image.",
            content_type="image/jpeg",
        )

        serializer = ServiceImageSerializer(
            data={
                "image": fake_image,
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "image",
            serializer.errors,
        )