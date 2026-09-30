from django.urls import path

from .views import (
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
        "<uuid:service_id>/images/",
        ServiceImageListCreateView.as_view(),
        name="service-image-list-create",
    ),
    path(
        "<uuid:service_id>/images/<uuid:pk>/",
        ServiceImageDeleteView.as_view(),
        name="service-image-delete",
    ),
]