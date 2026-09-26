from channels.generic.websocket import AsyncJsonWebsocketConsumer


class BookingStatusConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.booking_id = self.scope["url_route"]["kwargs"]["booking_id"]
        self.room_group_name = f"booking_{self.booking_id}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()

        await self.send_json(
            {
                "booking_id": str(self.booking_id),
                "status": "connected",
                "message": "Real-time booking status connected.",
            }
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )

    async def booking_status_update(self, event):
        await self.send_json(
            {
                "booking_id": event["booking_id"],
                "status": event["status"],
                "message": event["message"],
            }
        )