import secrets
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import override_settings
from django.utils.crypto import get_random_string
from rest_framework.test import APIClient, APITestCase

from services.models import (
    Booking,
    Category,
    Payment,
    Provider,
    Service,
)


TEST_WEBHOOK_SECRET = secrets.token_urlsafe(32)


@override_settings(
    PAYMENT_WEBHOOK_SECRET=TEST_WEBHOOK_SECRET,
    REST_FRAMEWORK={
        "DEFAULT_PERMISSION_CLASSES": [
            "rest_framework.permissions.IsAuthenticated",
        ],
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        ],
        "DEFAULT_THROTTLE_CLASSES": [
            "rest_framework.throttling.ScopedRateThrottle",
        ],
        "DEFAULT_THROTTLE_RATES": {
            "login": "5/minute",
            "registration": "5/minute",
            "password": "5/minute",
            "booking": "5/minute",
            "payment": "5/minute",
        },
    },
)
class APIThrottlingTests(APITestCase):

    def setUp(self):
        self.client = APIClient()

        cache.clear()

        self.test_password = get_random_string(32)

        self.customer = User.objects.create_user(
            username="throttle_customer",
            email="throttle_customer@example.com",
            password=self.test_password,
        )

        self.provider_user = User.objects.create_user(
            username="throttle_provider",
            email="throttle_provider@example.com",
            password=self.test_password,
        )

        self.category = Category.objects.create(
            name="Throttle Category",
            description="Category for throttling tests",
            status=True,
        )

        self.provider = Provider.objects.create(
            user=self.provider_user,
            name="Throttle Provider",
            description="Provider for throttling tests",
            status=True,
        )

        self.service = Service.objects.create(
            name="Throttle Service",
            description="Service for throttling tests",
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

    def assert_first_five_allowed_sixth_throttled(
        self,
        method,
        url,
        data=None,
        **kwargs,
    ):
        responses = []

        for _ in range(5):
            response = method(
                url,
                data,
                format="json",
                **kwargs,
            )
            responses.append(response)

        for response in responses:
            self.assertNotEqual(
                response.status_code,
                429,
                msg="A request within the configured limit was throttled.",
            )

        sixth_response = method(
            url,
            data,
            format="json",
            **kwargs,
        )

        self.assertEqual(
            sixth_response.status_code,
            429,
        )

        return responses, sixth_response

    def test_login_is_throttled(self):
        self.assert_first_five_allowed_sixth_throttled(
            self.client.post,
            "/api/v1/token/",
            {
                "username": "throttle_customer",
                "password": self.test_password,
            },
        )

    def test_registration_is_throttled(self):
        for index in range(5):
            registration_password = get_random_string(32)

            response = self.client.post(
                "/api/v1/register/",
                {
                    "username": f"throttle_registration_{index}",
                    "email": (
                        f"throttle_registration_{index}"
                        "@example.com"
                    ),
                    "password": registration_password,
                    "password_confirm": registration_password,
                },
                format="json",
            )

            self.assertNotEqual(
                response.status_code,
                429,
            )

        registration_password = get_random_string(32)

        response = self.client.post(
            "/api/v1/register/",
            {
                "username": "throttle_registration_6",
                "email": "throttle_registration_6@example.com",
                "password": registration_password,
                "password_confirm": registration_password,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            429,
        )

    def test_password_change_is_throttled(self):
        self.client.force_authenticate(
            user=self.customer
        )

        for _ in range(5):
            old_password = get_random_string(32)
            new_password = get_random_string(32)

            self.customer.set_password(old_password)
            self.customer.save(
                update_fields=["password"]
            )

            response = self.client.post(
                "/api/v1/password/change/",
                {
                    "old_password": old_password,
                    "new_password": new_password,
                    "new_password_confirm": new_password,
                },
                format="json",
            )

            self.assertNotEqual(
                response.status_code,
                429,
            )

        final_old_password = get_random_string(32)
        final_new_password = get_random_string(32)

        self.customer.set_password(final_old_password)
        self.customer.save(
            update_fields=["password"]
        )

        response = self.client.post(
            "/api/v1/password/change/",
            {
                "old_password": final_old_password,
                "new_password": final_new_password,
                "new_password_confirm": final_new_password,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            429,
        )

    def test_booking_creation_is_throttled(self):
        self.client.force_authenticate(
            user=self.customer
        )

        for index in range(5):
            response = self.client.post(
                "/api/v1/bookings/",
                {
                    "service": str(self.service.id),
                    "booking_date": (
                        date.today()
                        + timedelta(days=index + 2)
                    ).isoformat(),
                    "booking_time": "10:00:00",
                },
                format="json",
            )

            self.assertNotEqual(
                response.status_code,
                429,
            )

        response = self.client.post(
            "/api/v1/bookings/",
            {
                "service": str(self.service.id),
                "booking_date": (
                    date.today() + timedelta(days=10)
                ).isoformat(),
                "booking_time": "10:00:00",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            429,
        )

    def test_payment_initiation_is_throttled(self):
        self.client.force_authenticate(
            user=self.customer
        )

        for index in range(5):
            booking = Booking.objects.create(
                customer=self.customer,
                provider=self.provider,
                service=self.service,
                booking_date=(
                    date.today()
                    + timedelta(days=20 + index)
                ),
                booking_time="10:00:00",
                amount=Decimal("500.00"),
                status="pending",
            )

            response = self.client.post(
                "/api/v1/services/payments/initiate/",
                {
                    "booking": str(booking.id),
                    "amount": "500.00",
                },
                format="json",
            )

            self.assertNotEqual(
                response.status_code,
                429,
            )

        extra_booking = Booking.objects.create(
            customer=self.customer,
            provider=self.provider,
            service=self.service,
            booking_date=date.today() + timedelta(days=30),
            booking_time="10:00:00",
            amount=Decimal("500.00"),
            status="pending",
        )

        response = self.client.post(
            "/api/v1/services/payments/initiate/",
            {
                "booking": str(extra_booking.id),
                "amount": "500.00",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            429,
        )

    def test_payment_process_is_throttled(self):
        self.client.force_authenticate(
            user=self.customer
        )

        for index in range(5):
            payment_booking = Booking.objects.create(
                customer=self.customer,
                provider=self.provider,
                service=self.service,
                booking_date=(
                    date.today()
                    + timedelta(days=40 + index)
                ),
                booking_time="10:00:00",
                amount=Decimal("500.00"),
                status="pending",
            )

            payment = Payment.objects.create(
                booking=payment_booking,
                amount=Decimal("500.00"),
                payment_method="MOCK",
                payment_status="PENDING",
                transaction_id=f"THROTTLE-{index}",
            )

            response = self.client.post(
                f"/api/v1/services/payments/"
                f"{payment.id}/process/",
                {
                    "result": "SUCCESS",
                },
                format="json",
            )

            self.assertNotEqual(
                response.status_code,
                429,
            )

        extra_booking = Booking.objects.create(
            customer=self.customer,
            provider=self.provider,
            service=self.service,
            booking_date=date.today() + timedelta(days=50),
            booking_time="10:00:00",
            amount=Decimal("500.00"),
            status="pending",
        )

        extra_payment = Payment.objects.create(
            booking=extra_booking,
            amount=Decimal("500.00"),
            payment_method="MOCK",
            payment_status="PENDING",
            transaction_id="THROTTLE-EXTRA",
        )

        response = self.client.post(
            f"/api/v1/services/payments/"
            f"{extra_payment.id}/process/",
            {
                "result": "SUCCESS",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            429,
        )

    def test_payment_webhook_is_throttled(self):
        self.client.force_authenticate(
            user=self.customer
        )

        for index in range(5):
            webhook_booking = Booking.objects.create(
                customer=self.customer,
                provider=self.provider,
                service=self.service,
                booking_date=(
                    date.today()
                    + timedelta(days=60 + index)
                ),
                booking_time="10:00:00",
                amount=Decimal("500.00"),
                status="pending",
            )

            payment = Payment.objects.create(
                booking=webhook_booking,
                amount=Decimal("500.00"),
                payment_method="MOCK",
                payment_status="PENDING",
                transaction_id=f"WEBHOOK-{index}",
            )

            response = self.client.post(
                "/api/v1/services/payments/webhook/",
                {
                    "payment_id": str(payment.id),
                    "transaction_id": payment.transaction_id,
                    "payment_status": "SUCCESS",
                },
                format="json",
                HTTP_X_WEBHOOK_SECRET=TEST_WEBHOOK_SECRET,
            )

            self.assertNotEqual(
                response.status_code,
                429,
            )

        extra_booking = Booking.objects.create(
            customer=self.customer,
            provider=self.provider,
            service=self.service,
            booking_date=date.today() + timedelta(days=70),
            booking_time="10:00:00",
            amount=Decimal("500.00"),
            status="pending",
        )

        extra_payment = Payment.objects.create(
            booking=extra_booking,
            amount=Decimal("500.00"),
            payment_method="MOCK",
            payment_status="PENDING",
            transaction_id="WEBHOOK-EXTRA",
        )

        response = self.client.post(
            "/api/v1/services/payments/webhook/",
            {
                "payment_id": str(extra_payment.id),
                "transaction_id": extra_payment.transaction_id,
                "payment_status": "SUCCESS",
            },
            format="json",
            HTTP_X_WEBHOOK_SECRET=TEST_WEBHOOK_SECRET,
        )

        self.assertEqual(
            response.status_code,
            429,
        )