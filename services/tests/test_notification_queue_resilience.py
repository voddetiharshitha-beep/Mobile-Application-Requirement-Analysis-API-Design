
from unittest.mock import patch

from django.test import SimpleTestCase

from config.metrics import NOTIFICATION_EVENTS
from services.notification_service import send_notification
from config.middleware import request_id_context

class NotificationQueueResilienceTests(SimpleTestCase):
    @patch(
        "services.notification_service.create_notification.delay",
        side_effect=ConnectionError("broker unavailable"),
    )
    def test_broker_failure_is_logged_and_counted(
        self,
        mocked_delay,
    ):
        counter = NOTIFICATION_EVENTS.labels("queue", "failed")
        before = counter._value.get()

        with self.assertLogs(
            "services.notification_service",
            level="ERROR",
        ) as captured:
            result = send_notification(
                recipient_id=1,
                booking_id="booking-test",
                notification_type="BOOKING_CREATED",
                message="Test notification",
            )

        self.assertIsNone(result)
        mocked_delay.assert_called_once()
        self.assertEqual(counter._value.get(), before + 1)

        self.assertTrue(
            any(
                "Failed to queue booking notification"
                in entry.getMessage()
                for entry in captured.records
            )
        )

    @patch("services.notification_service.create_notification.delay")
    def test_successful_enqueue_returns_result_and_counts_event(
        self,
        mocked_delay,
    ):
        mocked_delay.return_value = "queued-task-result"
        counter = NOTIFICATION_EVENTS.labels("queue", "queued")
        before = counter._value.get()

        result = send_notification(
            recipient_id=1,
            booking_id="booking-test",
            notification_type="BOOKING_CREATED",
            message="Test notification",
        )

        self.assertEqual(result, "queued-task-result")
        mocked_delay.assert_called_once()
        self.assertEqual(counter._value.get(), before + 1)

    @patch(
        "services.notification_service.create_notification.delay",
        side_effect=TimeoutError("Broker enqueue timed out"),
    )
    def test_broker_timeout_is_logged_and_counted(
        self,
        mocked_delay,
    ):
        counter = NOTIFICATION_EVENTS.labels("queue", "failed")
        before = counter._value.get()

        with self.assertLogs(
            "services.notification_service",
            level="ERROR",
        ) as captured:
            result = send_notification(
                recipient_id=1,
                booking_id="booking-timeout-test",
                notification_type="BOOKING_CREATED",
                message="Test notification",
            )

        self.assertIsNone(result)
        mocked_delay.assert_called_once()
        self.assertEqual(counter._value.get(), before + 1)

        self.assertTrue(
            any(
                "Failed to queue booking notification"
                in entry.getMessage()
                for entry in captured.records
            )
        )
    @patch("services.notification_service.create_notification.delay")
    def test_request_correlation_id_is_passed_to_task(self, mocked_delay):
        mocked_delay.return_value = "queued-task-result"
        expected_correlation_id = "trace-propagation-test-456"

        token = request_id_context.set(expected_correlation_id)
        try:
            result = send_notification(
                recipient_id=1,
                booking_id="booking-test",
                notification_type="BOOKING_CREATED",
                message="Test notification",
            )
        finally:
            request_id_context.reset(token)

        self.assertEqual(result, "queued-task-result")
        mocked_delay.assert_called_once()
        self.assertEqual(
            mocked_delay.call_args.kwargs["correlation_id"],
            expected_correlation_id,
        )
