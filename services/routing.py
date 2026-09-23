from django.urls import path

from .consumers import BookingStatusConsumer


websocket_urlpatterns = [
    path(
        "ws/bookings/<uuid:booking_id>/",
        BookingStatusConsumer.as_asgi(),
    ),
]