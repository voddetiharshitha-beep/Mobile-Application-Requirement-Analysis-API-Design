from django.urls import path

from .views import (
    MediaDownloadView,
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
        "media/<uuid:media_id>/download/",
        MediaDownloadView.as_view(),
        name="media-download",
    ),

    path(
        "<uuid:pk>/",
        ServiceDetailView.as_view(),
        name="service-detail",
    ),

    path(
        "<uuid:service_id>/images/",
        ServiceImageListCreateView.as_view(),
        name="service-image-list-create",
    ),

    path(
        "<uuid:service_id>/images/<uuid:pk>/",
        ServiceImageDeleteView.as_view(),
        name="service-image-delete",
    ),

    # Notification endpoints
    path(
        "notifications/",
        NotificationListView.as_view(),
        name="notification-list",
    ),

    # Payment endpoints
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