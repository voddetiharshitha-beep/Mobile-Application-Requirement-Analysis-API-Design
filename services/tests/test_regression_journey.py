from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient

from services.models import Booking, Category, Provider, Service


class RegressionJourneyTests(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()

        self.category = Category.objects.create(
            name="Regression Test Category",
            description="Category used for regression testing.",
        )

        self.provider_user = User.objects.create_user(
            username="regression_provider",
            email="regression_provider@example.com",
            password="Regression@2026!",
        )

        self.customer_username = "regression_customer"
        self.customer_password = "Regression@2026!"

        self.provider = Provider.objects.create(
            user=self.provider_user,
            name="Regression Test Provider",
            description="Provider used for regression testing.",
            status=True,
        )

        self.service = Service.objects.create(
            name="Regression Test Service",
            description="Service used for regression testing.",
            location="Hyderabad",
            price=Decimal("500.00"),
            category=self.category,
            provider=self.provider,
        )

    @override_settings(
        PAYMENT_WEBHOOK_SECRET="REGRESSION_WEBHOOK_SECRET",
        REST_FRAMEWORK={
            "DEFAULT_THROTTLE_CLASSES": [],
            "DEFAULT_THROTTLE_RATES": {},
        },
    )
    def test_complete_customer_regression_journey(self):
        # ---------------------------------------------------------
        # 1. REGISTER
        # ---------------------------------------------------------
        response = self.client.post(
            "/api/v1/register/",
            {
                "username": self.customer_username,
                "email": "regression_customer@example.com",
                "password": self.customer_password,
                "password_confirm": self.customer_password,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            201,
            msg=f"Registration failed: {response.status_code} {response.data}",
        )

        customer = User.objects.get(
            username=self.customer_username
        )

        # ---------------------------------------------------------
        # 2. LOGIN
        # ---------------------------------------------------------
        response = self.client.post(
            "/api/v1/token/",
            {
                "username": self.customer_username,
                "password": self.customer_password,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            200,
            msg=f"Login failed: {response.status_code} {response.data}",
        )

        access_token = response.data.get("access")

        self.assertTrue(
            access_token,
            f"No access token returned. Response: {response.data}",
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )

        # ---------------------------------------------------------
        # 3. SEARCH
        # ---------------------------------------------------------
        response = self.client.get(
            "/api/v1/services/",
            {
                "search": "Regression Test Service",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
            msg=f"Service search failed: {response.status_code} {response.data}",
        )

        if isinstance(response.data, dict):
            services = response.data.get("results", [])
        else:
            services = response.data

        self.assertTrue(
            any(
                str(item.get("id")) == str(self.service.id)
                for item in services
            ),
            f"Regression service was not found. Response: {response.data}",
        )

        # ---------------------------------------------------------
        # 4. BOOK
        # ---------------------------------------------------------
        booking_date = date.today() + timedelta(days=5)
        booking_time = "10:00:00"

        response = self.client.post(
            "/api/v1/bookings/",
            {
                "service": str(self.service.id),
                "booking_date": booking_date.isoformat(),
                "booking_time": booking_time,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="regression-booking-key-2026",
        )

        self.assertEqual(
            response.status_code,
            201,
            msg=f"Booking failed: {response.status_code} {response.data}",
        )

        booking_data = response.data.get("data", {})
        booking_id = booking_data.get("id")

        self.assertTrue(
            booking_id,
            f"Booking was created but no booking ID was returned. "
            f"Response: {response.data}",
        )

        booking = Booking.objects.get(id=booking_id)

        self.assertEqual(
            booking.customer_id,
            customer.id,
        )

        self.assertEqual(
            booking.status,
            "pending",
        )

                # ---------------------------------------------------------
        # 5. INITIATE PAYMENT
        # ---------------------------------------------------------
        response = self.client.post(
            "/api/v1/services/payments/initiate/",
            {
                "booking": str(booking_id),
                "amount": str(booking.amount),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            201,
            msg=(
                f"Payment initiation failed: "
                f"{response.status_code} {response.data}"
            ),
        )

        payment_data = response.data.get(
            "data",
            response.data,
        )

        payment_id = payment_data.get("id")

        self.assertTrue(
            payment_id,
            "Payment was initiated but no payment ID was returned. "
            f"Response: {response.data}",
        )
        # ---------------------------------------------------------
        # 6. PROCESS PAYMENT
        # ---------------------------------------------------------
        response = self.client.post(
            f"/api/v1/services/payments/{payment_id}/process/",
            {
                "result": "SUCCESS",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            200,
            msg=(
                f"Payment processing failed: "
                f"{response.status_code} {response.data}"
            ),
        )

        # ---------------------------------------------------------
        # 7. CONFIRM BOOKING
        # ---------------------------------------------------------
        self.client.force_authenticate(
            user=self.provider_user
        )

        response = self.client.post(
            f"/api/v1/bookings/{booking_id}/status/",
            {
                "status": "confirmed",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            200,
            msg=(
                f"Booking confirmation failed: "
                f"{response.status_code} {response.data}"
            ),
        )

        # ---------------------------------------------------------
        # 8. START BOOKING
        # ---------------------------------------------------------
        response = self.client.post(
            f"/api/v1/bookings/{booking_id}/status/",
            {
                "status": "in_progress",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            200,
            msg=(
                f"Booking start failed: "
                f"{response.status_code} {response.data}"
            ),
        )

        # ---------------------------------------------------------
        # 9. COMPLETE BOOKING
        # ---------------------------------------------------------
        response = self.client.post(
            f"/api/v1/bookings/{booking_id}/status/",
            {
                "status": "completed",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            200,
            msg=(
                f"Booking completion failed: "
                f"{response.status_code} {response.data}"
            ),
        )

        # ---------------------------------------------------------
        # 10. VIEW BOOKING HISTORY
        # ---------------------------------------------------------
        self.client.force_authenticate(
            user=customer
        )

        response = self.client.get(
            "/api/v1/bookings/"
        )

        self.assertEqual(
            response.status_code,
            200,
            msg=(
                f"Booking history failed: "
                f"{response.status_code} {response.data}"
            ),
        )

        if isinstance(response.data, dict):
            history = response.data.get(
                "results",
                response.data.get("data", []),
            )
        else:
            history = response.data

        self.assertTrue(
            any(
                str(item.get("id")) == str(booking_id)
                for item in history
            ),
            f"Completed booking was not found in history. "
            f"Response: {response.data}",
        )

        booking.refresh_from_db()

        self.assertEqual(
            booking.status,
            "completed",
        )