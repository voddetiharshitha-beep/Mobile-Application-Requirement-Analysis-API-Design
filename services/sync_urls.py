
from django.urls import path

from .sync_views import BookingSyncView


urlpatterns = [
    path(
        "bookings/",
        BookingSyncView.as_view(),
        name="booking-sync",
    ),
]
