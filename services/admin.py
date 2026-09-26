
from django.contrib import admin
from django.contrib.auth.models import User

from .models import (
    Booking,
    Category,
    Notification,
    Payment,
    Provider,
    ProviderProfile,
    Service,
    ServiceImage,
    UserProfile,
)


# Django registers User automatically.
# Unregister it before using our custom UserAdmin.
admin.site.unregister(User)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "date_joined",
    )
    search_fields = (
        "username",
        "email",
        "first_name",
        "last_name",
    )
    list_filter = (
        "is_staff",
        "is_active",
        "is_superuser",
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "status",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "name",
    )
    list_filter = (
        "status",
    )


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "user",
        "status",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "name",
        "user__username",
        "user__email",
    )
    list_filter = (
        "status",
    )


@admin.register(ProviderProfile)
class ProviderProfileAdmin(admin.ModelAdmin):
    list_display = (
        "provider",
        "name",
        "status",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "name",
        "provider__name",
    )
    list_filter = (
        "status",
    )


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price",
        "category",
        "provider",
        "status",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "name",
        "description",
        "location",
    )
    list_filter = (
        "status",
        "category",
        "provider",
    )


@admin.register(ServiceImage)
class ServiceImageAdmin(admin.ModelAdmin):
    list_display = (
        "service",
        "image",
        "uploaded_at",
    )
    search_fields = (
        "service__name",
    )


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "provider",
        "service",
        "booking_date",
        "booking_time",
        "amount",
        "status",
        "created_at",
    )
    search_fields = (
        "customer__username",
        "customer__email",
        "provider__name",
        "service__name",
    )
    list_filter = (
        "status",
        "booking_date",
        "provider",
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "booking",
        "amount",
        "transaction_id",
        "payment_status",
        "payment_method",
        "created_at",
    )
    search_fields = (
        "transaction_id",
        "booking__customer__username",
        "booking__service__name",
    )
    list_filter = (
        "payment_status",
        "payment_method",
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "recipient",
        "booking",
        "notification_type",
        "is_read",
        "created_at",
    )
    search_fields = (
        "recipient__username",
        "recipient__email",
        "message",
    )
    list_filter = (
        "notification_type",
        "is_read",
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "user__username",
        "user__email",
    )
