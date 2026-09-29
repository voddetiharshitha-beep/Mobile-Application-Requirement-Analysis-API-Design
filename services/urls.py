
from django.urls import path

from .views import (
    NotificationListView,
    PaymentInitiateView,
    PaymentProcessView,
    PaymentWebhookView,
    ServiceDetailView,
    ServiceListCreateView,
    ServiceImageListCreateView,
    ServiceImageDeleteView,
)

urlpatterns = [
    path(
        "",
        ServiceListCreateView.as_view(),
        name="service-list-create",
    ),
    path(
        "<uuid:pk>/",
        ServiceDetailView.as_view(),
        name="service-detail",
    ),
    path(
        "notifications/",
        NotificationListView.as_view(),
        name="notification-list",
    ),
    path(
        "<uuid:service_id>/images/",
        ServiceImageListCreateView.as_view(),
        name="service-image-list-create",
    ),
    path(
        "<uuid:service_id>/images/<int:image_id>/",
        ServiceImageDeleteView.as_view(),
        name="service-image-delete",
    ),
    path(
        "payments/initiate/",
        PaymentInitiateView.as_view(),
        name="payment-initiate",
    ),
    path(
        "payments/<uuid:pk>/process/",
        PaymentProcessView.as_view(),
        name="payment-process",
    ),
    path(
        "payments/webhook/",
        PaymentWebhookView.as_view(),
        name="payment-webhook",
    ),
]
