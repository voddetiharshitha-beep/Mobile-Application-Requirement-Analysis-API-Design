import os
import uuid

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError


MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_IMAGE_WIDTH = 4096
MAX_IMAGE_HEIGHT = 4096
MAX_IMAGE_PIXELS = 16_777_216


def generate_safe_media_filename(instance, filename):
    """
    Generate a safe, unique filename for uploaded media.

    The original filename is never used as the storage filename.
    """

    extension = os.path.splitext(filename)[1].lower()

    allowed_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
    }

    if extension not in allowed_extensions:
        extension = ".jpg"

    return (
        f"media/{uuid.uuid4().hex}"
        f"{extension}"
    )


# Protect Pillow from images with an excessive number of pixels.
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def validate_uploaded_image(image):
    """
    Validate uploaded images for:
    - file size
    - valid image format
    - maximum width
    - maximum height
    - maximum total pixel count
    """

    # 1. File-size protection
    if image.size > MAX_IMAGE_SIZE:
        raise ValidationError(
            "Image file size must not exceed 5 MB."
        )

    # 2. Verify that the file is actually a valid image
    try:
        image.seek(0)

        img = Image.open(image)
        img.verify()

    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
    ):
        raise ValidationError(
            "The uploaded file is not a valid image."
        )

    # 3. Read the image dimensions
    try:
        image.seek(0)

        img = Image.open(image)

        width, height = img.size

    except (
        UnidentifiedImageError,
        OSError,
        SyntaxError,
    ):
        raise ValidationError(
            "The uploaded file is not a valid image."
        )

    # 4. Maximum width
    if width > MAX_IMAGE_WIDTH:
        raise ValidationError(
            f"Image width must not exceed "
            f"{MAX_IMAGE_WIDTH} pixels."
        )

    # 5. Maximum height
    if height > MAX_IMAGE_HEIGHT:
        raise ValidationError(
            f"Image height must not exceed "
            f"{MAX_IMAGE_HEIGHT} pixels."
        )

    # 6. Maximum total pixels
    if width * height > MAX_IMAGE_PIXELS:
        raise ValidationError(
            "Image dimensions are too large. "
            "The maximum allowed resolution is "
            "4096 x 4096 pixels."
        )

    # Reset the uploaded file pointer
    image.seek(0)