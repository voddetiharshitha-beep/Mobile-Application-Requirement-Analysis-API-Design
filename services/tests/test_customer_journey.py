from datetime import date, time, timedelta
from decimal import Decimal


from django.contrib.auth.models import User
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient

from services.models import Booking, Category, Notification, Provider, Service


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class CustomerJourneyTests(TransactionTestCase):

    def setUp(self):
        self.client = APIClient()

        self.customer = User.objects.create_user(
            username="customer_test",
            email="customer@example.com",
            password="TestPassword123!",
        )

        self.provider_user = User.objects.create_user(
            username="provider_test",
            email="provider@example.com",
            password="TestPassword123!",
        )

        self.category = Category.objects.create(
            name="Cleaning",
            description="Cleaning services",
            status=True,
        )

        self.provider = Provider.objects.create(
            user=self.provider_user,
            name="Test Provider",
            description="Test provider",
            status=True,
        )

        self.service = Service.objects.create(
            name="Home Cleaning",
            description="Home cleaning service",
            location="Hyderabad",
            price=Decimal("500.00"),
            status=True,
            category=self.category,
            provider=self.provider,
        )

    def authenticate(self):
        response = self.client.post(
            "/api/v1/token/",
            {
                "username": "customer_test",
                "password": "TestPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {response.data['access']}"
        )

    def test_customer_can_login_and_view_services(self):
        self.authenticate()

        response = self.client.get(
            "/api/v1/services/"
        )

        self.assertEqual(response.status_code, 200)

        results = response.data["results"]

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["name"],
            "Home Cleaning",
        )

    def test_customer_can_create_booking(self):
        self.authenticate()

        booking_date = date.today() + timedelta(days=1)

        response = self.client.post(
            "/api/v1/services/bookings/",
            {
                "provider": str(self.provider.id),
                "service": str(self.service.id),
                "booking_date": booking_date.isoformat(),
                "booking_time": "10:00:00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        booking = Booking.objects.get(
            id=response.data["id"]
        )

        self.assertEqual(
            booking.customer,
            self.customer,
        )

        self.assertEqual(
            booking.provider,
            self.provider,
        )

        self.assertEqual(
            booking.service,
            self.service,
        )

        self.assertEqual(
            booking.amount,
            Decimal("500.00"),
        )

        self.assertEqual(
            booking.status,
            "pending",
        )

    def test_booking_created_notification_is_generated(self):
        self.authenticate()

        booking_date = date.today() + timedelta(days=1)

        response = self.client.post(
            "/api/v1/services/bookings/",
            {
                "provider": str(self.provider.id),
                "service": str(self.service.id),
                "booking_date": booking_date.isoformat(),
                "booking_time": "10:00:00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        booking = Booking.objects.get(
            id=response.data["id"]
        )

        notification = Notification.objects.filter(
            recipient=self.customer,
            booking=booking,
            notification_type="BOOKING_CREATED",
        ).first()

        self.assertIsNotNone(notification)

        self.assertEqual(
            notification.message,
            "Your booking has been created successfully.",
        )

    def test_customer_can_list_only_own_bookings(self):
        other_customer = User.objects.create_user(
            username="other_customer",
            email="other@example.com",
            password="TestPassword123!",
        )

        Booking.objects.create(
            customer=other_customer,
            provider=self.provider,
            service=self.service,
            booking_date=date.today() + timedelta(days=2),
            booking_time=time(11, 0),
            amount=Decimal("500.00"),
            status="pending",
        )

        self.authenticate()

        response = self.client.get(
            "/api/v1/services/bookings/"
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data["count"],
            0,
        )