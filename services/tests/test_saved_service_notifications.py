from django.contrib.auth.models import User
from django.test import TestCase

from services.models import (
    Category,
    Notification,
    Provider,
    ProviderProfile,
    SavedService,
    Service,
)
from services.tasks import (
    notify_saved_customers_service_unavailable,
)


class SavedServiceNotificationTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user(
            username="notification_customer",
            password="TestPass123!",
        )

        cls.other_customer = User.objects.create_user(
            username="other_notification_customer",
            password="TestPass123!",
        )

        cls.provider_user = User.objects.create_user(
            username="notification_provider",
            password="TestPass123!",
        )

        cls.provider = Provider.objects.create(
            user=cls.provider_user,
        )

        cls.category = Category.objects.create(
            name="Notification Test Category",
        )

        cls.service = Service.objects.create(
            name="Notification Test Service",
            description="Service for notification testing",
            location="Hyderabad",
            price="500.00",
            status=True,
            category=cls.category,
            provider=cls.provider,
        )

    def test_saved_customer_receives_unavailable_notification(self):
        SavedService.objects.create(
            customer=self.customer,
            service=self.service,
        )

        notify_saved_customers_service_unavailable.run(
            str(self.service.id)
        )

        notification = Notification.objects.get(
            recipient=self.customer,
            service=self.service,
            notification_type="SAVED_SERVICE_UNAVAILABLE",
        )

        self.assertEqual(
            notification.recipient,
            self.customer,
        )

        self.assertEqual(
            notification.service,
            self.service,
        )

        self.assertEqual(
            notification.message,
            (
                "The saved service "
                "'Notification Test Service' "
                "is no longer available."
            ),
        )

    def test_non_saved_customer_receives_no_notification(self):
        SavedService.objects.create(
            customer=self.customer,
            service=self.service,
        )

        notify_saved_customers_service_unavailable.run(
            str(self.service.id)
        )

        self.assertFalse(
            Notification.objects.filter(
                recipient=self.other_customer,
                service=self.service,
                notification_type="SAVED_SERVICE_UNAVAILABLE",
            ).exists()
        )

    def test_notification_is_not_duplicated(self):
        SavedService.objects.create(
            customer=self.customer,
            service=self.service,
        )

        notify_saved_customers_service_unavailable.run(
            str(self.service.id)
        )

        notify_saved_customers_service_unavailable.run(
            str(self.service.id)
        )

        count = Notification.objects.filter(
            recipient=self.customer,
            service=self.service,
            notification_type="SAVED_SERVICE_UNAVAILABLE",
        ).count()

        self.assertEqual(
            count,
            1,
        )

    def test_service_with_no_saved_customers_creates_no_notification(
        self,
    ):
        notify_saved_customers_service_unavailable.run(
            str(self.service.id)
        )

        count = Notification.objects.filter(
            service=self.service,
            notification_type="SAVED_SERVICE_UNAVAILABLE",
        ).count()

        self.assertEqual(
            count,
            0,
        )

    def test_invalid_service_does_not_create_notification(self):
        from uuid import uuid4

        result = notify_saved_customers_service_unavailable.run(
            str(uuid4())
        )

        self.assertEqual(
            result,
            [],
        )