from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import TransactionTestCase
from django.utils.crypto import get_random_string

from config.asgi import application
from services.booking_service import (
    cancel_booking,
    update_booking_status,
)
from services.models import (
    Booking,
    Category,
    Payment,
    Provider,
    Service,
)
from services.payment_service import (
    process_payment_webhook,
)


class BookingWebSocketTests(TransactionTestCase):

    def setUp(self):
        self.test_password = get_random_string(32)

        self.customer = User.objects.create_user(
            username="websocket_customer",
            email="websocket_customer@example.com",
            password=self.test_password,
        )

        self.provider_user = User.objects.create_user(
            username="websocket_provider",
            email="websocket_provider@example.com",
            password=self.test_password,
        )

        self.other_user = User.objects.create_user(
            username="websocket_other",
            email="websocket_other@example.com",
            password=self.test_password,
        )

        self.category = Category.objects.create(
            name="WebSocket Test Category",
            description="WebSocket test category",
            status=True,
        )

        self.provider = Provider.objects.create(
            user=self.provider_user,
            name="WebSocket Test Provider",
            description="WebSocket test provider",
            status=True,
        )

        self.service = Service.objects.create(
            name="WebSocket Test Service",
            description="WebSocket test service",
            location="Hyderabad",
            price=Decimal("500.00"),
            status=True,
            category=self.category,
            provider=self.provider,
        )

        self.booking = Booking.objects.create(
            customer=self.customer,
            provider=self.provider,
            service=self.service,
            booking_date=date.today() + timedelta(days=1),
            booking_time="10:00:00",
            amount=Decimal("500.00"),
            status="pending",
        )

    async def connect_as_user(self, user):
        communicator = WebsocketCommunicator(
            application,
            f"/ws/bookings/{self.booking.id}/",
        )

        communicator.scope["user"] = user

        connected, _ = await communicator.connect()

        return communicator, connected

    async def test_customer_can_connect_to_own_booking(self):
        communicator, connected = await self.connect_as_user(
            self.customer
        )

        self.assertTrue(connected)

        response = await communicator.receive_json_from()

        self.assertEqual(
            response["booking_id"],
            str(self.booking.id),
        )

        self.assertEqual(
            response["status"],
            "connected",
        )

        await communicator.disconnect()

    async def test_provider_can_connect_to_assigned_booking(self):
        communicator, connected = await self.connect_as_user(
            self.provider_user
        )

        self.assertTrue(connected)

        response = await communicator.receive_json_from()

        self.assertEqual(
            response["booking_id"],
            str(self.booking.id),
        )

        self.assertEqual(
            response["status"],
            "connected",
        )

        await communicator.disconnect()

    async def test_websocket_receives_booking_status_update(self):
        communicator, connected = await self.connect_as_user(
            self.customer
        )

        self.assertTrue(connected)

        connected_message = (
            await communicator.receive_json_from()
        )

        self.assertEqual(
            connected_message["status"],
            "connected",
        )

        channel_layer = get_channel_layer()

        await channel_layer.group_send(
            f"booking_{self.booking.id}",
            {
                "type": "booking_status_update",
                "booking_id": str(self.booking.id),
                "status": "confirmed",
                "message": (
                    "Booking status changed to confirmed."
                ),
            },
        )

        response = await communicator.receive_json_from()

        self.assertEqual(
            response["booking_id"],
            str(self.booking.id),
        )

        self.assertEqual(
            response["status"],
            "confirmed",
        )

        self.assertEqual(
            response["message"],
            "Booking status changed to confirmed.",
        )

        await communicator.disconnect()

    async def test_other_user_cannot_connect_to_booking(self):
        communicator, connected = await self.connect_as_user(
            self.other_user
        )

        self.assertFalse(connected)

        await communicator.disconnect()

    async def test_anonymous_user_cannot_connect(self):
        communicator = WebsocketCommunicator(
            application,
            f"/ws/bookings/{self.booking.id}/",
        )

        connected, _ = await communicator.connect()

        self.assertFalse(connected)

        await communicator.disconnect()

    async def test_booking_status_service_broadcasts_to_websocket(
        self,
    ):
        communicator, connected = await self.connect_as_user(
            self.customer
        )

        self.assertTrue(connected)

        connected_message = (
            await communicator.receive_json_from()
        )

        self.assertEqual(
            connected_message["status"],
            "connected",
        )

        await sync_to_async(
            update_booking_status
        )(
            booking=self.booking,
            new_status="confirmed",
        )

        response = await communicator.receive_json_from()

        self.assertEqual(
            response["booking_id"],
            str(self.booking.id),
        )

        self.assertEqual(
            response["status"],
            "confirmed",
        )

        self.assertEqual(
            response["message"],
            "Booking status changed to confirmed.",
        )

        await communicator.disconnect()

    async def test_cancel_booking_service_broadcasts_to_websocket(
        self,
    ):
        communicator, connected = await self.connect_as_user(
            self.customer
        )

        self.assertTrue(connected)

        connected_message = (
            await communicator.receive_json_from()
        )

        self.assertEqual(
            connected_message["status"],
            "connected",
        )

        await sync_to_async(
            cancel_booking
        )(
            booking=self.booking,
        )

        response = await communicator.receive_json_from()

        self.assertEqual(
            response["booking_id"],
            str(self.booking.id),
        )

        self.assertEqual(
            response["status"],
            "cancelled",
        )

        self.assertEqual(
            response["message"],
            "Booking status changed to cancelled.",
        )

        await communicator.disconnect()

    async def test_payment_success_confirms_booking_and_broadcasts_to_websocket(
        self,
    ):
        communicator, connected = await self.connect_as_user(
            self.customer
        )

        self.assertTrue(connected)

        connected_message = (
            await communicator.receive_json_from()
        )

        self.assertEqual(
            connected_message["status"],
            "connected",
        )

        payment = await sync_to_async(
            Payment.objects.create
        )(
            booking=self.booking,
            amount=Decimal("500.00"),
            transaction_id="websocket-payment-test-001",
            payment_status="PENDING",
            payment_method="MOCK",
        )

        await sync_to_async(
            process_payment_webhook
        )(
            payment=payment,
            payment_status="SUCCESS",
        )

        response = await communicator.receive_json_from()

        self.assertEqual(
            response["booking_id"],
            str(self.booking.id),
        )

        self.assertEqual(
            response["status"],
            "confirmed",
        )

        self.assertEqual(
            response["message"],
            "Booking status changed to confirmed.",
        )

        booking = await sync_to_async(
            Booking.objects.get
        )(
            id=self.booking.id
        )

        self.assertEqual(
            booking.status,
            "confirmed",
        )

        payment = await sync_to_async(
            Payment.objects.get
        )(
            id=payment.id
        )

        self.assertEqual(
            payment.payment_status,
            "SUCCESS",
        )

        await communicator.disconnect()

    async def test_websocket_heartbeat_ping_returns_pong(
        self,
    ):
        communicator, connected = await self.connect_as_user(
            self.customer
        )

        self.assertTrue(connected)

        connected_message = (
            await communicator.receive_json_from()
        )

        self.assertEqual(
            connected_message["event"],
            "connection.established",
        )

        await communicator.send_json_to(
            {
                "event": "heartbeat.ping",
            }
        )

        response = await communicator.receive_json_from()

        self.assertEqual(
            response["event"],
            "heartbeat.pong",
        )

        self.assertEqual(
            response["booking_id"],
            str(self.booking.id),
        )

        self.assertEqual(
            response["status"],
            "connected",
        )

        await communicator.disconnect()

    async def test_booking_status_change_triggers_websocket_and_celery_notification(
        self,
    ):
        communicator, connected = await self.connect_as_user(
            self.customer
        )

        self.assertTrue(connected)

        connected_message = (
            await communicator.receive_json_from()
        )

        self.assertEqual(
            connected_message["event"],
            "connection.established",
        )

        # Valid transition:
        # pending -> confirmed.
        await sync_to_async(
            update_booking_status
        )(
            booking=self.booking,
            new_status="confirmed",
        )

        confirmed_response = (
            await communicator.receive_json_from()
        )

        self.assertEqual(
            confirmed_response["event"],
            "booking.status_changed",
        )

        self.assertEqual(
            confirmed_response["booking_id"],
            str(self.booking.id),
        )

        self.assertEqual(
            confirmed_response["status"],
            "confirmed",
        )

        self.assertEqual(
            confirmed_response["message"],
            "Booking status changed to confirmed.",
        )

        with patch(
            "services.booking_service.send_notification"
        ) as mock_send_notification:

            # Valid transition:
            # confirmed -> in_progress.
            await sync_to_async(
                update_booking_status
            )(
                booking=self.booking,
                new_status="in_progress",
            )

            response = (
                await communicator.receive_json_from()
            )

            self.assertEqual(
                response["event"],
                "booking.status_changed",
            )

            self.assertEqual(
                response["booking_id"],
                str(self.booking.id),
            )

            self.assertEqual(
                response["status"],
                "in_progress",
            )

            self.assertEqual(
                response["message"],
                "Booking status changed to in_progress.",
            )

            mock_send_notification.assert_called_once_with(
                recipient_id=self.customer.id,
                booking_id=str(self.booking.id),
                notification_type="PROVIDER_STARTED",
                message=(
                    "The provider has started "
                    "your service."
                ),
            )

        await communicator.disconnect()

    async def test_multiple_devices_receive_same_booking_event(
        self,
    ):
        # Device 1.
        device_one, connected_one = (
            await self.connect_as_user(
                self.customer
            )
        )

        self.assertTrue(connected_one)

        device_one_connection = (
            await device_one.receive_json_from()
        )

        self.assertEqual(
            device_one_connection["event"],
            "connection.established",
        )

        self.assertEqual(
            device_one_connection["booking_id"],
            str(self.booking.id),
        )

        # Device 2.
        device_two, connected_two = (
            await self.connect_as_user(
                self.customer
            )
        )

        self.assertTrue(connected_two)

        device_two_connection = (
            await device_two.receive_json_from()
        )

        self.assertEqual(
            device_two_connection["event"],
            "connection.established",
        )

        self.assertEqual(
            device_two_connection["booking_id"],
            str(self.booking.id),
        )

        # One status change.
        await sync_to_async(
            update_booking_status
        )(
            booking=self.booking,
            new_status="confirmed",
        )

        # Device 1 receives the event.
        device_one_response = (
            await device_one.receive_json_from()
        )

        self.assertEqual(
            device_one_response["event"],
            "booking.status_changed",
        )

        self.assertEqual(
            device_one_response["booking_id"],
            str(self.booking.id),
        )

        self.assertEqual(
            device_one_response["status"],
            "confirmed",
        )

        self.assertEqual(
            device_one_response["message"],
            "Booking status changed to confirmed.",
        )

        # Device 2 receives the same event.
        device_two_response = (
            await device_two.receive_json_from()
        )

        self.assertEqual(
            device_two_response["event"],
            "booking.status_changed",
        )

        self.assertEqual(
            device_two_response["booking_id"],
            str(self.booking.id),
        )

        self.assertEqual(
            device_two_response["status"],
            "confirmed",
        )

        self.assertEqual(
            device_two_response["message"],
            "Booking status changed to confirmed.",
        )

        await device_one.disconnect()
        await device_two.disconnect()

    async def test_client_can_disconnect_and_reconnect(
        self,
    ):
        # First connection.
        communicator, connected = await self.connect_as_user(
            self.customer
        )

        self.assertTrue(connected)

        first_connection = (
            await communicator.receive_json_from()
        )

        self.assertEqual(
            first_connection["event"],
            "connection.established",
        )

        self.assertEqual(
            first_connection["booking_id"],
            str(self.booking.id),
        )

        await communicator.disconnect()

        # Reconnect using a new WebSocket connection.
        reconnected_communicator, reconnected = (
            await self.connect_as_user(
                self.customer
            )
        )

        self.assertTrue(reconnected)

        reconnect_message = (
            await reconnected_communicator.receive_json_from()
        )

        self.assertEqual(
            reconnect_message["event"],
            "connection.established",
        )

        self.assertEqual(
            reconnect_message["booking_id"],
            str(self.booking.id),
        )

        self.assertEqual(
            reconnect_message["status"],
            "connected",
        )

        await reconnected_communicator.disconnect()

    async def test_single_status_change_produces_one_event(
        self,
    ):
        communicator, connected = await self.connect_as_user(
            self.customer
        )

        self.assertTrue(connected)

        connected_message = (
            await communicator.receive_json_from()
        )

        self.assertEqual(
            connected_message["event"],
            "connection.established",
        )

        # Perform exactly one status transition.
        await sync_to_async(
            update_booking_status
        )(
            booking=self.booking,
            new_status="confirmed",
        )

        # Receive the expected status event.
        response = await communicator.receive_json_from()

        self.assertEqual(
            response["event"],
            "booking.status_changed",
        )

        self.assertEqual(
            response["booking_id"],
            str(self.booking.id),
        )

        self.assertEqual(
            response["status"],
            "confirmed",
        )

        self.assertEqual(
            response["message"],
            "Booking status changed to confirmed.",
        )

        # Verify the booking was updated correctly.
        booking = await sync_to_async(
            Booking.objects.get
        )(
            id=self.booking.id
        )

        self.assertEqual(
            booking.status,
            "confirmed",
        )

        await communicator.disconnect()