import uuid

from django.contrib.auth.models import User
from django.db import models
from .validators import (
    generate_safe_media_filename,
    validate_uploaded_image,
)

class Category(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Provider(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="provider",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ProviderProfile(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    provider = models.OneToOneField(
        Provider,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.provider.name} Profile"


class Service(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=200, blank=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    status = models.BooleanField(default=True)

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="services",
    )
    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name="services",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Booking(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("payment_failed", "Payment Failed"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="bookings",
    )

    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name="bookings",
    )

    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="bookings",
    )

    booking_date = models.DateField()
    booking_time = models.TimeField()

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def can_transition_to(self, new_status):
        allowed_transitions = {
            "pending": {
                "confirmed",
                "cancelled",
                "payment_failed",
            },
            "confirmed": {
                "in_progress",
                "cancelled",
            },
            "in_progress": {
                "completed",
            },
            "completed": set(),
            "cancelled": set(),
            "payment_failed": set(),
        }

        return new_status in allowed_transitions.get(
            self.status,
            set(),
        )

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "provider",
                    "booking_date",
                    "booking_time",
                ],
                name="booking_provider_date_time_idx",
            ),
        ]

    def __str__(self):
        return f"{self.service.name} - {self.customer.username}"


class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
        ("REFUNDED", "Refunded"),
    ]

    PAYMENT_METHOD_CHOICES = [
    ("MOCK", "Mock Payment"),
    ("STRIPE", "Stripe"),
]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name="payment",
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    transaction_id = models.CharField(
    max_length=100,
    unique=True,
    default=uuid.uuid4,
    editable=False,
)

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="PENDING",
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default="MOCK",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_id} - {self.payment_status}"


class Notification(models.Model):
    NOTIFICATION_TYPE_CHOICES = [
        ("BOOKING_CREATED", "Booking Created"),
        ("PAYMENT_SUCCESSFUL", "Payment Successful"),
        ("BOOKING_CONFIRMED", "Booking Confirmed"),
        ("PROVIDER_STARTED", "Provider Started Service"),
        ("BOOKING_COMPLETED", "Booking Completed"),
        ("BOOKING_CANCELLED", "Booking Cancelled"),
        (
            "SAVED_SERVICE_UNAVAILABLE",
            "Saved Service Unavailable",
        ),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )

    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )

    notification_type = models.CharField(
        max_length=40,
        choices=NOTIFICATION_TYPE_CHOICES,
    )

    message = models.TextField()

    is_read = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    version = models.PositiveIntegerField(
        default=1,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "recipient",
                    "booking",
                    "notification_type",
                ],
                name="unique_notification_per_booking_type",
            ),
            models.UniqueConstraint(
                fields=[
                    "recipient",
                    "service",
                    "notification_type",
                ],
                condition=models.Q(
                    service__isnull=False,
                ),
                name="unique_notification_per_service_type",
            ),
        ]

    def __str__(self):
        return (
            f"{self.notification_type} - "
            f"{self.recipient.username}"
        )

class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    image = models.ImageField(
        upload_to="profile_images/",
        validators=[validate_uploaded_image],
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} Profile"


class ServiceImage(models.Model):
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(
        upload_to="service_images/",
        validators=[validate_uploaded_image],
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.service.name}"

class BookingIdempotencyKey(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="booking_idempotency_keys",
    )

    key = models.CharField(
        max_length=100,
    )

    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name="idempotency_key_record",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "key"],
                name="unique_booking_idempotency_key_per_user",
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.key}"
class SavedService(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="saved_services",
    )

    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="saved_by_customers",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "customer",
                    "service",
                ],
                name="unique_saved_service",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "customer",
                    "-created_at",
                ],
                name="saved_service_customer_created",
            ),
        ]

    def __str__(self):
        return (
            f"{self.customer.username} - "
            f"{self.service.name}"
        )
class Media(models.Model):
    MEDIA_TYPE_CHOICES = [
        ("PROFILE", "Profile"),
        ("SERVICE", "Service"),
    ]

    VISIBILITY_CHOICES = [
        ("PUBLIC", "Public"),
        ("PRIVATE", "Private"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="media",
    )

    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="media",
        null=True,
        blank=True,
    )

    file = models.ImageField(
        upload_to=generate_safe_media_filename,
        validators=[validate_uploaded_image],
    )

    media_type = models.CharField(
        max_length=20,
        choices=MEDIA_TYPE_CHOICES,
    )

    visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default="PRIVATE",
    )

    original_filename = models.CharField(
        max_length=255,
    )

    mime_type = models.CharField(
        max_length=100,
    )

    file_size = models.PositiveBigIntegerField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        indexes = [
            models.Index(
                fields=["owner", "media_type"],
                name="media_owner_type_idx",
            ),
            models.Index(
                fields=["service", "visibility"],
                name="media_service_visibility_idx",
            ),
        ]

    def __str__(self):
        return self.original_filename
class IdempotencyRecord(models.Model):
    STATUS_CHOICES = [
        ("PROCESSING", "Processing"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="idempotency_records",
    )

    key = models.CharField(
        max_length=100,
    )

    operation = models.CharField(
        max_length=100,
    )

    request_hash = models.CharField(
        max_length=64,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PROCESSING",
    )

    response_status = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    response_body = models.JSONField(
        null=True,
        blank=True,
    )

    resource_type = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    resource_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "user",
                    "key",
                    "operation",
                ],
                name="unique_idempotency_record_per_operation",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "user",
                    "key",
                    "operation",
                ],
                name="idempotency_lookup_idx",
            ),
            models.Index(
                fields=[
                    "expires_at",
                ],
                name="idempotency_expiry_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.operation} - "
            f"{self.key}"
        )
