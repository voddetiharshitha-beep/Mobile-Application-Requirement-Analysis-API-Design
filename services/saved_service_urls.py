from django.urls import path

from .views import (
    SavedServiceDeleteView,
    SavedServiceListCreateView,
)


urlpatterns = [
    path(
        "",
        SavedServiceListCreateView.as_view(),
        name="saved-service-list-create",
    ),
    path(
        "<uuid:pk>/",
        SavedServiceDeleteView.as_view(),
        name="saved-service-delete",
    ),
]