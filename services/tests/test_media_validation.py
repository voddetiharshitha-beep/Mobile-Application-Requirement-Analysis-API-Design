from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from PIL import Image

from services.validators import validate_uploaded_image


class MediaValidationTests(TestCase):
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

    def test_valid_jpeg_image_is_accepted(self):
        image = self.create_image(
            name="valid.jpg",
            image_format="JPEG",
        )

        validate_uploaded_image(image)

    def test_valid_png_image_is_accepted(self):
        image = self.create_image(
            name="valid.png",
            image_format="PNG",
        )

        validate_uploaded_image(image)

    def test_invalid_file_content_is_rejected(self):
        invalid_file = SimpleUploadedFile(
            "invalid.jpg",
            b"This is not a real image file.",
            content_type="image/jpeg",
        )

        with self.assertRaises(ValidationError):
            validate_uploaded_image(invalid_file)

    def test_file_larger_than_5_mb_is_rejected(self):
        large_file = SimpleUploadedFile(
            "large.jpg",
            b"0" * (5 * 1024 * 1024 + 1),
            content_type="image/jpeg",
        )

        with self.assertRaises(ValidationError):
            validate_uploaded_image(large_file)

    def test_image_width_larger_than_4096_is_rejected(self):
        image = self.create_image(
            name="wide.jpg",
            image_format="JPEG",
            size=(4097, 100),
        )

        with self.assertRaises(ValidationError):
            validate_uploaded_image(image)

    def test_image_height_larger_than_4096_is_rejected(self):
        image = self.create_image(
            name="tall.jpg",
            image_format="JPEG",
            size=(100, 4097),
        )

        with self.assertRaises(ValidationError):
            validate_uploaded_image(image)

    def test_image_with_more_than_maximum_pixels_is_rejected(self):
        image = self.create_image(
            name="large_dimensions.jpg",
            image_format="JPEG",
            size=(4096, 4097),
        )

        with self.assertRaises(ValidationError):
            validate_uploaded_image(image)
            