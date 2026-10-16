
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from celery.exceptions import Retry
from django.contrib.auth.models import User
from django.db import InterfaceError, OperationalError
from django.test import TransactionTestCase

from config.metrics import NOTIFICATION_EVENTS
from services.models import (
    Booking,
    Category,
    Notification,
    Provider,
    Service,
)
from services.tasks import (
    create_notification,
    notify_saved_customers_service_unavailable,
)


class ReliableNotificationTaskTests(TransactionTestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="reliable_event_customer",
            email="reliable_event_customer@example.com",
            password="TestPassword123!",
        )

        self.provider_user = User.objects.create_user(
            username="reliable_event_provider",
            email="reliable_event_provider@example.com",
            password="TestPassword123!",
        )

        self.category = Category.objects.create(
            name="Reliable Event Category",
            description="Category for reliability tests",
            status=True,
        )

        self.provider = Provider.objects.create(
            user=self.provider_user,
            name="Reliable Event Provider",
            description="Provider for reliability tests",
            status=True,
        )

        self.service = Service.objects.create(
            name="Reliable Event Service",
            description="Service for reliability tests",
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

    def test_notification_tasks_have_bounded_retry_policy(self):
        tasks = (
            create_notification,
            notify_saved_customers_service_unavailable,
        )

        for task in tasks:
            with self.subTest(task=task.name):
                self.assertTrue(
                    {
                        OperationalError,
                        InterfaceError,
                    }.issubset(set(task.autoretry_for))
                )

                self.assertTrue(task.retry_backoff)
                self.assertEqual(task.retry_backoff_max, 60)
                self.assertTrue(task.retry_jitter)
                self.assertEqual(
                    task.retry_kwargs.get("max_retries"),
                    5,
                )

    def test_repeating_booking_notification_task_creates_one_record(self):
        task_args = (
            self.customer.pk,
            str(self.booking.pk),
            "BOOKING_CREATED",
            "Your booking has been created.",
        )

        created_counter = NOTIFICATION_EVENTS.labels(
            "processing",
            "created",
        )
        duplicate_counter = NOTIFICATION_EVENTS.labels(
            "processing",
            "duplicate",
        )

        created_before = created_counter._value.get()
        duplicate_before = duplicate_counter._value.get()

        first_result = create_notification.apply(
            args=task_args,
            kwargs={
                "correlation_id": "reliable-event-test-001",
            },
            throw=True,
        ).get()

        second_result = create_notification.apply(
            args=task_args,
            kwargs={
                "correlation_id": "reliable-event-test-001",
            },
            throw=True,
        ).get()

        self.assertEqual(first_result, second_result)

        notification_count = Notification.objects.filter(
            recipient=self.customer,
            booking=self.booking,
            notification_type="BOOKING_CREATED",
        ).count()

        self.assertEqual(notification_count, 1)
        self.assertEqual(
            created_counter._value.get(),
            created_before + 1,
        )
        self.assertEqual(
            duplicate_counter._value.get(),
            duplicate_before + 1,
        )

    def test_transient_database_failure_retries_and_recovers(self):
        task_args = (
            self.customer.pk,
            str(self.booking.pk),
            "BOOKING_CREATED",
            "Your booking has been created.",
        )

        original_get_or_create = Notification.objects.get_or_create

        retry_counter = NOTIFICATION_EVENTS.labels(
            "processing",
            "retryable_error",
        )
        retry_before = retry_counter._value.get()

        with patch(
            "services.tasks.Notification.objects.get_or_create",
            side_effect=[
                OperationalError("Temporary database outage"),
                original_get_or_create,
            ],
        ) as mocked_get_or_create:
            with self.assertRaises(Retry):
                create_notification.apply(
                    args=task_args,
                    kwargs={
                        "correlation_id": "recovery-test-001",
                    },
                    throw=True,
                ).get()

        self.assertEqual(mocked_get_or_create.call_count, 1)
        self.assertEqual(
            retry_counter._value.get(),
            retry_before + 1,
        )

        with patch(
            "services.tasks.Notification.objects.get_or_create",
            wraps=original_get_or_create,
        ) as mocked_recovery:
            result = create_notification.apply(
                args=task_args,
                kwargs={
                    "correlation_id": "recovery-test-001",
                },
                throw=True,
            ).get()

        self.assertTrue(result)
        mocked_recovery.assert_called_once()

        notifications = Notification.objects.filter(
            recipient=self.customer,
            booking=self.booking,
            notification_type="BOOKING_CREATED",
        )

        self.assertEqual(notifications.count(), 1)
