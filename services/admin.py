from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import Category, Provider, ProviderProfile, Service


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "created_at", "updated_at")
    search_fields = ("name",)


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "created_at", "updated_at")
    search_fields = ("name",)


@admin.register(ProviderProfile)
class ProviderProfileAdmin(admin.ModelAdmin):
    list_display = ("provider", "name", "status", "created_at", "updated_at")
    search_fields = ("name", "provider__name")


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
    search_fields = ("name", "description")
    list_filter = ("status", "category", "provider")