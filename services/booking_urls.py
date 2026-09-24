from django.urls import path

from .views import (
    BookingCancelView,
    BookingDetailView,
    BookingListCreateView,
    BookingStatusUpdateView,
)

urlpatterns = [
    path(
        "bookings/",
        BookingListCreateView.as_view(),
        name="booking-list-create",
    ),
    path(
        "bookings/<uuid:pk>/",
        BookingDetailView.as_view(),
        name="booking-detail",
    ),
    path(
        "bookings/<uuid:pk>/cancel/",
        BookingCancelView.as_view(),
        name="booking-cancel",
    ),
    path(
        "bookings/<uuid:pk>/status/",
        BookingStatusUpdateView.as_view(),
        name="booking-status-update",
    ),
]