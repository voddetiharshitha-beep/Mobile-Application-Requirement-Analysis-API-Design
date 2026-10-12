from unittest.mock import patch

from django.test import SimpleTestCase

from services.notification_service import send_notification


class NotificationQueueResilienceTests(SimpleTestCase):
    @patch(
        "services.notification_service.create_notification.delay",
        side_effect=ConnectionError("broker unavailable"),
    )
    def test_broker_failure_is_logged_and_does_not_propagate(
        self,
        mocked_delay,
    ):
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
        self.assertTrue(
            any(
                "Failed to queue booking notification"
                in entry.getMessage()
                for entry in captured.records
            )
        )

    @patch("services.notification_service.create_notification.delay")
    def test_successful_enqueue_returns_task_result(self, mocked_delay):
        mocked_delay.return_value = "queued-task-result"

        result = send_notification(
            recipient_id=1,
            booking_id="booking-test",
            notification_type="BOOKING_CREATED",
            message="Test notification",
        )

        self.assertEqual(result, "queued-task-result")
        mocked_delay.assert_called_once()
