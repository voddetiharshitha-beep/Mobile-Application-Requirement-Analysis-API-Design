
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache

from .models import Booking


class BookingStatusConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        self.booking_id = self.scope[
            "url_route"
        ]["kwargs"]["booking_id"]

        user = self.scope.get("user")

        # Reject unauthenticated WebSocket connections.
        if (
            user is None
            or isinstance(user, AnonymousUser)
            or not user.is_authenticated
        ):
            await self.close(code=4001)
            return

        # Verify that the authenticated user is allowed
        # to access this booking.
        authorized = await self.user_can_access_booking(
            user.id,
            self.booking_id,
        )

        if not authorized:
            await self.close(code=4003)
            return

        self.user_id = user.id

        # Track this WebSocket connection as an active
        # connection for the authenticated user.
        await self.track_presence_connect(
            self.user_id
        )

        self.room_group_name = (
            f"booking_{self.booking_id}"
        )

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()

        await self.send_json(
            {
                "event": "connection.established",
                "booking_id": str(self.booking_id),
                "status": "connected",
                "message": (
                    "Real-time booking status connected."
                ),
            }
        )

    @database_sync_to_async
    def user_can_access_booking(
        self,
        user_id,
        booking_id,
    ):
        return Booking.objects.filter(
            id=booking_id,
        ).filter(
            customer_id=user_id
        ).exists() or Booking.objects.filter(
            id=booking_id,
            provider__user_id=user_id,
        ).exists()

    @database_sync_to_async
    def track_presence_connect(
        self,
        user_id,
    ):
        cache_key = f"websocket_presence:{user_id}"

        cache.add(
            cache_key,
            0,
            timeout=3600,
        )

        cache.incr(cache_key)

    @database_sync_to_async
    def track_presence_disconnect(
        self,
        user_id,
    ):
        cache_key = f"websocket_presence:{user_id}"

        try:
            current_count = cache.decr(cache_key)
        except ValueError:
            current_count = 0

        if current_count <= 0:
            cache.delete(cache_key)

    async def disconnect(self, close_code):
        # Remove this WebSocket connection from the
        # booking group.
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            )

        # Remove this connection from user presence.
        if hasattr(self, "user_id"):
            await self.track_presence_disconnect(
                self.user_id
            )

    async def receive_json(
        self,
        content,
        **kwargs,
    ):
        event = content.get("event")

        if event == "heartbeat.ping":
            await self.send_json(
                {
                    "event": "heartbeat.pong",
                    "booking_id": str(
                        self.booking_id
                    ),
                    "status": "connected",
                }
            )
            return

    async def booking_status_update(self, event):
        await self.send_json(
            {
                "event": "booking.status_changed",
                "booking_id": event["booking_id"],
                "status": event["status"],
                "message": event["message"],
            }
        )
