import re

from PIL import Image, UnidentifiedImageError

from datetime import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from PIL import Image, UnidentifiedImageError
from rest_framework import generics, serializers, status
from rest_framework.response import Response

from .models import (
 Booking,
    Payment,
    Provider,
     SavedService,
    Service,
    ServiceImage,
    UserProfile,
    Notification,
)

User = get_user_model()
class StrictModelSerializer(serializers.ModelSerializer):
    """
    Strict serializer that rejects:
    1. Unknown fields.
    2. Read-only fields supplied by the client.
    """

    def to_internal_value(self, data):
        if hasattr(data, "keys"):
            incoming_fields = set(data.keys())
            allowed_fields = set(self.fields.keys())

            unexpected_fields = (
                incoming_fields - allowed_fields
            )

            if unexpected_fields:
                raise serializers.ValidationError(
                    {
                        field: [
                            "This field is not allowed."
                        ]
                        for field in sorted(
                            unexpected_fields
                        )
                    }
                )

            read_only_fields = {
                field_name
                for field_name, field in self.fields.items()
                if field.read_only
            }

            supplied_read_only_fields = (
                incoming_fields & read_only_fields
            )

            if supplied_read_only_fields:
                raise serializers.ValidationError(
                    {
                        field: [
                            "This field is read-only."
                        ]
                        for field in sorted(
                            supplied_read_only_fields
                        )
                    }
                )

        return super().to_internal_value(data)

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8,
    )

    password_confirm = serializers.CharField(
        write_only=True,
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "password_confirm",
        ]

    def validate_username(self, value):
        if User.objects.filter(
            username=value
        ).exists():
            raise serializers.ValidationError(
                "A user with this username already exists."
            )

        return value

    def validate_email(self, value):
        if (
            value
            and User.objects.filter(
                email=value
            ).exists()
        ):
            raise serializers.ValidationError(
                "A user with this email already exists."
            )

        return value

    def validate(self, attrs):
        if (
            attrs["password"]
            != attrs["password_confirm"]
        ):
            raise serializers.ValidationError(
                {
                    "password_confirm": (
                        "Passwords do not match."
                    )
                }
            )

        return attrs

    def create(self, validated_data):
        validated_data.pop(
            "password_confirm"
        )

        password = validated_data.pop(
            "password"
        )

        user = User.objects.create_user(
            password=password,
            **validated_data,
        )

        return user
class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        write_only=True,
        required=True,
    )

    new_password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
    )

    new_password_confirm = serializers.CharField(
        write_only=True,
        required=True,
    )

    def validate_old_password(self, value):
        user = self.context["request"].user

        if not user.check_password(value):
            raise serializers.ValidationError(
                "Current password is incorrect."
            )

        return value

    def validate(self, attrs):
        if (
            attrs["new_password"]
            != attrs["new_password_confirm"]
        ):
            raise serializers.ValidationError(
                {
                    "new_password_confirm": (
                        "New passwords do not match."
                    )
                }
            )

        if attrs["old_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {
                    "new_password": (
                        "New password must be different "
                        "from the current password."
                    )
                }
            )

        from django.contrib.auth.password_validation import (
            validate_password,
        )

        validate_password(
            attrs["new_password"],
            self.context["request"].user,
        )

        return attrs

class ServiceSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = Service

        fields = [
            "id",
            "name",
            "description",
            "location",
            "price",
            "status",
            "category",
            "provider",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "provider",
            "created_at",
            "updated_at",
        ]
class ServiceListSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = Service

        fields = [
            "id",
            "name",
            "location",
            "price",
            "status",
            "category",
            "provider",
        ]

        read_only_fields = fields

class BookingSerializer(
    StrictModelSerializer
):
    customer = serializers.PrimaryKeyRelatedField(
        read_only=True,
    )

    provider = serializers.PrimaryKeyRelatedField(
        queryset=Provider.objects.all(),
        required=False,
    )

    class Meta:
        model = Booking

        fields = [
            "id",
            "customer",
            "provider",
            "service",
            "booking_date",
            "booking_time",
            "amount",
            "status",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "customer",
            "amount",
            "status",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        service = attrs.get("service")

        # During partial updates, service may not be
        # included in the request.
        if service is None:
            if self.instance:
                service = self.instance.service
            else:
                raise serializers.ValidationError(
                    {
                        "service": (
                            "Service is required."
                        )
                    }
                )

        try:
            service = Service.objects.select_related(
                "provider"
            ).get(
                id=service.id
            )
        except Service.DoesNotExist:
            raise serializers.ValidationError(
                {
                    "service": (
                        "Service does not exist."
                    )
                }
            )

        # The provider is determined by the selected service.
        service_provider = service.provider

        # If the client supplies a provider,
        # make sure it matches the service provider.
        requested_provider = attrs.get("provider")

        if requested_provider is not None:
            if requested_provider != service_provider:
                raise serializers.ValidationError(
                    {
                        "provider": (
                            "Provider does not match "
                            "the selected service."
                        )
                    }
                )

        # Always use the provider belonging to the service.
        attrs["provider"] = service_provider
        provider = service_provider

        if not provider.status:
            raise serializers.ValidationError(
                {
                    "service": (
                        "The provider for this service "
                        "is not active."
                    )
                }
            )

        booking_date = attrs.get(
            "booking_date"
        )

        booking_time = attrs.get(
            "booking_time"
        )

        if self.instance:
            if booking_date is None:
                booking_date = (
                    self.instance.booking_date
                )

            if booking_time is None:
                booking_time = (
                    self.instance.booking_time
                )

        if (
            booking_date is None
            or booking_time is None
        ):
            raise serializers.ValidationError(
                {
                    "booking_date": (
                        "Booking date is required."
                    ),
                    "booking_time": (
                        "Booking time is required."
                    ),
                }
            )

        requested_datetime = datetime.combine(
            booking_date,
            booking_time,
        )

        if (
            not self.instance
            and requested_datetime
            <= datetime.now()
        ):
            raise serializers.ValidationError(
                {
                    "booking_time": (
                        "Booking date and time "
                        "must be in the future."
                    )
                }
            )

        conflicting_booking = Booking.objects.filter(
            provider=provider,
            booking_date=booking_date,
            booking_time=booking_time,
        ).exclude(
            status="cancelled"
        )

        if self.instance:
            conflicting_booking = (
                conflicting_booking.exclude(
                    id=self.instance.id
                )
            )

        if conflicting_booking.exists():
            raise serializers.ValidationError(
                {
                    "booking_time": (
                        "Provider is already booked "
                        "for this time."
                    )
                }
            )

        return attrs

    def update(
        self,
        instance,
        validated_data,
    ):
        if instance.status == "cancelled":
            raise serializers.ValidationError(
                {
                    "detail": (
                        "Cancelled booking "
                        "cannot be modified."
                    )
                }
            )

        if instance.status == "completed":
            raise serializers.ValidationError(
                {
                    "detail": (
                        "Completed booking "
                        "cannot be modified."
                    )
                }
            )

        # Provider, customer, amount, and status
        # must never be changed through this serializer.
        validated_data.pop(
            "provider",
            None,
        )

        validated_data.pop(
            "customer",
            None,
        )

        validated_data.pop(
            "amount",
            None,
        )

        validated_data.pop(
            "status",
            None,
        )

        return super().update(
            instance,
            validated_data,
        )

class PaymentInitiateSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = Payment

        fields = [
            "booking",
            "amount",
        ]

    def validate(self, attrs):
        booking = attrs["booking"]
        amount = attrs["amount"]
        request = self.context["request"]

        if booking.customer != request.user:
            raise serializers.ValidationError(
                {
                    "booking": (
                        "This booking does not belong "
                        "to the current user."
                    )
                }
            )

        if booking.status != "pending":
            raise serializers.ValidationError(
                {
                    "booking": (
                        "Only pending bookings can be paid."
                    )
                }
            )

        if amount != booking.amount:
            raise serializers.ValidationError(
                {
                    "amount": (
                        "Payment amount must match "
                        "the booking amount."
                    )
                }
            )

        if Payment.objects.filter(
            booking=booking
        ).exists():
            raise serializers.ValidationError(
                {
                    "booking": (
                        "A payment already exists "
                        "for this booking."
                    )
                }
            )

        return attrs


class PaymentProcessSerializer(
    serializers.Serializer
):
    result = serializers.ChoiceField(
        choices=[
            "SUCCESS",
            "FAILED",
        ]
    )


class PaymentWebhookSerializer(
    serializers.Serializer
):
    payment_id = serializers.UUIDField()

    transaction_id = serializers.CharField(
        max_length=100,
    )

    payment_status = serializers.ChoiceField(
        choices=[
            "SUCCESS",
            "FAILED",
        ]
    )

    def validate(self, attrs):
        payment_id = attrs["payment_id"]
        transaction_id = attrs["transaction_id"]
        payment_status = attrs["payment_status"]

        try:
            payment = (
                Payment.objects
                .select_related("booking")
                .get(
                    id=payment_id,
                )
            )
        except Payment.DoesNotExist:
            raise serializers.ValidationError(
                {
                    "payment_id": (
                        "Payment does not exist."
                    )
                }
            )

        if payment.transaction_id != transaction_id:
            raise serializers.ValidationError(
                {
                    "transaction_id": (
                        "Transaction ID does not "
                        "match the payment."
                    )
                }
            )

        # Idempotency:
        # A repeated webhook with the same
        # final status is already processed.
        if payment.payment_status == payment_status:
            attrs["payment"] = payment
            attrs["already_processed"] = True

            return attrs

        # Do not allow a payment that has already
        # reached a final state to change status.
        if payment.payment_status != "PENDING":
            raise serializers.ValidationError(
                {
                    "payment_id": (
                        "Payment has already been "
                        "processed with a different status."
                    )
                }
            )

        attrs["payment"] = payment
        attrs["already_processed"] = False

        return attrs


def build_api_error_response(
    message,
    code,
    status_code,
):
    return Response(
        {
            "success": False,
            "error": {
                "message": message,
                "code": code,
            },
        },
        status=status_code,
    )


class PaymentWebhookView(
    generics.GenericAPIView
):
    serializer_class = PaymentProcessSerializer
    permission_classes = []

    def post(
        self,
        request,
        *args,
        **kwargs,
    ):
        webhook_secret = request.headers.get(
            "X-Webhook-Secret"
        )

        if (
            webhook_secret
            != settings.PAYMENT_WEBHOOK_SECRET
        ):
            return build_api_error_response(
                "Invalid webhook secret.",
                "INVALID_WEBHOOK_SECRET",
                status.HTTP_401_UNAUTHORIZED,
            )

        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        payment = serializer.validated_data[
            "payment"
        ]

        payment_status = serializer.validated_data[
            "payment_status"
        ]

        already_processed = serializer.validated_data.get(
            "already_processed",
            False,
        )

        if not already_processed:
            payment = process_payment_webhook(
                payment=payment,
                payment_status=payment_status,
            )

        return Response(
            {
                "success": True,
                "message": (
                    "Payment webhook processed successfully."
                ),
                "data": {
                    "payment_id": str(
                        payment.id
                    ),
                    "payment_status": (
                        payment.payment_status
                    ),
                },
            },
            status=200,
        )




class BookingStatusSerializer(
    serializers.Serializer
):
    status = serializers.ChoiceField(
        choices=[
            "pending",
            "confirmed",
            "in_progress",
            "completed",
            "cancelled",
            "payment_failed",
        ]
    )

    def validate_status(self, value):
        booking = self.context[
            "booking"
        ]

        if not booking.can_transition_to(
            value
        ):
            raise serializers.ValidationError(
                f"Invalid booking status transition: "
                f"{booking.status} → {value}."
            )

        return value


class ProfileImageSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = UserProfile
        fields = [
            "image"
        ]

    def validate_image(self, image):
        allowed_types = [
            "image/jpeg",
            "image/png",
        ]

        if image.content_type not in allowed_types:
            raise serializers.ValidationError(
                "Only JPG, JPEG, and PNG images are allowed."
            )

        if image.size > settings.MAX_IMAGE_UPLOAD_SIZE:
            raise serializers.ValidationError(
                "Image size must not exceed 5 MB."
            )
            

        if not image.name:
            raise serializers.ValidationError(
                "Filename is required."
            )

        allowed_extensions = [
            ".jpg",
            ".jpeg",
            ".png",
        ]

        filename = image.name.lower()

        if not any(
            filename.endswith(ext)
            for ext in allowed_extensions
        ):
            raise serializers.ValidationError(
                "Filename must end with .jpg, .jpeg, or .png."
            )

        try:
            image_file = Image.open(image)
            image_file.verify()
        except (
            UnidentifiedImageError,
            OSError,
            SyntaxError,
        ):
            raise serializers.ValidationError(
                "Invalid image file."
            )
        finally:
            image.seek(0)

        return image



class ServiceImageSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = ServiceImage

        fields = [
            "id",
            "service",
            "image",
            "uploaded_at",
        ]

        read_only_fields = [
            "id",
            "service",
            "uploaded_at",
        ]

    def validate_image(self, image):
        """
        Secure validation for service image uploads.

        Checks:
        1. File exists
        2. File size
        3. Safe filename
        4. Allowed extension
        5. Declared MIME type
        6. Actual image content
        7. MIME type matches actual image format
        """

        # ---------------------------------------------------------
        # 1. MISSING FILE
        # ---------------------------------------------------------

        if image is None:
            raise serializers.ValidationError(
                "Image file is required."
            )

        # ---------------------------------------------------------
        # 2. FILE SIZE
        # ---------------------------------------------------------

        if image.size > settings.MAX_IMAGE_UPLOAD_SIZE:
            raise serializers.ValidationError(
                "Image size must not exceed 5 MB."
            )

        # ---------------------------------------------------------
        # 3. FILENAME REQUIRED
        # ---------------------------------------------------------

        if not image.name:
            raise serializers.ValidationError(
                "Filename is required."
            )

        filename = image.name

        # ---------------------------------------------------------
        # 4. MALICIOUS FILENAME PROTECTION
        # ---------------------------------------------------------

        # Reject path traversal and null-byte filenames.
        if (
            "/" in filename
            or "\\" in filename
            or "\x00" in filename
            or ".." in filename
        ):
            raise serializers.ValidationError(
                "Invalid filename."
            )

        # Reject control characters.
        if any(
            ord(character) < 32 or ord(character) == 127
            for character in filename
        ):
            raise serializers.ValidationError(
                "Invalid filename."
            )

        # Keep filenames reasonably short and predictable.
        if len(filename) > 100:
            raise serializers.ValidationError(
                "Filename is too long."
            )

        # ---------------------------------------------------------
        # 5. ALLOWED EXTENSION
        # ---------------------------------------------------------

        filename_pattern = re.compile(
            r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,94}\.(jpg|jpeg|png)$",
            re.IGNORECASE,
        )

        if not filename_pattern.fullmatch(filename):
            raise serializers.ValidationError(
                "Filename must use a valid .jpg, .jpeg, or .png extension."
            )

        # ---------------------------------------------------------
        # 6. DECLARED MIME TYPE
        # ---------------------------------------------------------

        allowed_mime_types = {
            "image/jpeg",
            "image/png",
        }

        if image.content_type not in allowed_mime_types:
            raise serializers.ValidationError(
                "Only JPG, JPEG, and PNG images are allowed."
            )

        # ---------------------------------------------------------
        # 7. VERIFY ACTUAL IMAGE CONTENT
        # ---------------------------------------------------------

        try:
            image.seek(0)

            image_file = Image.open(image)

            detected_format = image_file.format

            image_file.verify()

        except (
            UnidentifiedImageError,
            OSError,
            SyntaxError,
        ):
            raise serializers.ValidationError(
                "Invalid image file."
            )

        finally:
            image.seek(0)

        # ---------------------------------------------------------
        # 8. MIME TYPE MUST MATCH ACTUAL FILE FORMAT
        # ---------------------------------------------------------

        expected_formats = {
            "image/jpeg": "JPEG",
            "image/png": "PNG",
        }

        expected_format = expected_formats.get(
            image.content_type
        )

        if detected_format != expected_format:
            raise serializers.ValidationError(
                "File content does not match its MIME type."
            )

        # ---------------------------------------------------------
        # 9. EXTENSION MUST MATCH ACTUAL FORMAT
        # ---------------------------------------------------------

        extension = filename.rsplit(
            ".",
            1
        )[1].lower()

        extension_formats = {
            "jpg": "JPEG",
            "jpeg": "JPEG",
            "png": "PNG",
        }

        if extension_formats[extension] != detected_format:
            raise serializers.ValidationError(
                "File extension does not match its actual image format."
            )

        image.seek(0)

        return image




class NotificationSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = Notification

        fields = [
            "id",
            "booking",
            "notification_type",
            "message",
            "is_read",
            "created_at",
            "updated_at",
            "version",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "version",
        ]


class ProfileSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
        ]
        read_only_fields = [
            "username",
        ]
class SavedServiceSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(
        source="service.name",
        read_only=True,
    )

    class Meta:
        model = SavedService

        fields = [
            "id",
            "service",
            "service_name",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "service_name",
            "created_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)

        data["service"] = str(instance.service_id)

        return data