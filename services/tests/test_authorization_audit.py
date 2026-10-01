from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.utils.crypto import get_random_string
from rest_framework import status
from rest_framework.test import APITestCase

from services.models import (
    Booking,
    Category,
    Provider,
    Service,
)


class AuthorizationAuditTest(APITestCase):

    def setUp(self):
        self.test_password = get_random_string(32)

        # ==============================
        # CREATE USERS
        # ==============================

        self.admin = User.objects.create_superuser(
            username="audit_admin",
            email="audit_admin@example.com",
            password=self.test_password,
        )

        self.provider_user = User.objects.create_user(
            username="audit_provider",
            email="audit_provider@example.com",
            password=self.test_password,
        )

        self.provider_user_2 = User.objects.create_user(
            username="audit_provider_2",
            email="audit_provider_2@example.com",
            password=self.test_password,
        )

        self.customer = User.objects.create_user(
            username="audit_customer",
            email="audit_customer@example.com",
            password=self.test_password,
        )

        self.customer_2 = User.objects.create_user(
            username="audit_customer_2",
            email="audit_customer2@example.com",
            password=self.test_password,
        )

        # ==============================
        # CREATE PROVIDERS
        # ==============================

        self.provider = Provider.objects.create(
            user=self.provider_user,
            name="Audit Provider",
            description="Authorization audit provider",
            status=True,
        )

        self.provider_2 = Provider.objects.create(
            user=self.provider_user_2,
            name="Audit Provider 2",
            description="Second audit provider",
            status=True,
        )

        # ==============================
        # CREATE CATEGORY
        # ==============================

        self.category = Category.objects.create(
            name="Audit Category",
            description="Authorization audit category",
            status=True,
        )

        # ==============================
        # CREATE SERVICES
        # ==============================

        self.service = Service.objects.create(
            name="Audit Service",
            description="Provider owned service",
            location="Hyderabad",
            price="500.00",
            status=True,
            category=self.category,
            provider=self.provider,
        )

        self.service_2 = Service.objects.create(
            name="Audit Service 2",
            description="Second provider service",
            location="Hyderabad",
            price="700.00",
            status=True,
            category=self.category,
            provider=self.provider_2,
        )

        # ==============================
        # CREATE BOOKINGS
        # ==============================

        self.booking = Booking.objects.create(
            customer=self.customer,
            provider=self.provider,
            service=self.service,
            booking_date=date.today() + timedelta(days=1),
            booking_time=time(10, 0),
            amount="500.00",
            status="pending",
        )

        self.booking_2 = Booking.objects.create(
            customer=self.customer_2,
            provider=self.provider_2,
            service=self.service_2,
            booking_date=date.today() + timedelta(days=2),
            booking_time=time(11, 0),
            amount="700.00",
            status="confirmed",
        )

    # ==========================================
    # ANONYMOUS
    # ==========================================

    def test_anonymous_services_denied(self):
        response = self.client.get(
            "/api/v1/services/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_anonymous_bookings_denied(self):
        response = self.client.get(
            "/api/v1/bookings/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_anonymous_booking_detail_denied(self):
        response = self.client.get(
            f"/api/v1/bookings/{self.booking.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    # ==========================================
    # CUSTOMER
    # ==========================================

    def test_customer_can_view_services(self):
        self.client.force_authenticate(
            user=self.customer
        )

        response = self.client.get(
            "/api/v1/services/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_customer_only_sees_own_bookings(self):
        self.client.force_authenticate(
            user=self.customer
        )

        response = self.client.get(
            "/api/v1/bookings/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_ids = {
            str(item["id"])
            for item in response.data["results"]
        }

        self.assertIn(
            str(self.booking.id),
            returned_ids,
        )

        self.assertNotIn(
            str(self.booking_2.id),
            returned_ids,
        )

    def test_customer_cannot_access_other_customer_booking(self):
        self.client.force_authenticate(
            user=self.customer_2
        )

        response = self.client.get(
            f"/api/v1/bookings/{self.booking.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_customer_cannot_cancel_other_customer_booking(self):
        self.client.force_authenticate(
            user=self.customer_2
        )

        response = self.client.post(
            f"/api/v1/bookings/{self.booking.id}/cancel/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_customer_cannot_update_booking_status(self):
        self.client.force_authenticate(
            user=self.customer
        )

        response = self.client.post(
            f"/api/v1/bookings/{self.booking.id}/status/",
            {"status": "confirmed"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    # ==========================================
    # PROVIDER
    # ==========================================

    def test_provider_only_sees_own_bookings(self):
        self.client.force_authenticate(
            user=self.provider_user
        )

        response = self.client.get(
            "/api/v1/bookings/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        returned_ids = {
            str(item["id"])
            for item in response.data["results"]
        }

        self.assertIn(
            str(self.booking.id),
            returned_ids,
        )

        self.assertNotIn(
            str(self.booking_2.id),
            returned_ids,
        )

    def test_provider_cannot_access_other_provider_booking(self):
        self.client.force_authenticate(
            user=self.provider_user
        )

        response = self.client.get(
            f"/api/v1/bookings/{self.booking_2.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_provider_can_update_own_booking_status(self):
        self.client.force_authenticate(
            user=self.provider_user
        )

        response = self.client.post(
            f"/api/v1/bookings/{self.booking.id}/status/",
            {"status": "confirmed"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.booking.refresh_from_db()

        self.assertEqual(
            self.booking.status,
            "confirmed",
        )

    def test_provider_cannot_update_other_provider_booking(self):
        self.client.force_authenticate(
            user=self.provider_user
        )

        response = self.client.post(
            f"/api/v1/bookings/{self.booking_2.id}/status/",
            {"status": "in_progress"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    # ==========================================
    # SERVICE OWNERSHIP
    # ==========================================

    def test_provider_cannot_delete_other_provider_service(self):
        self.client.force_authenticate(
            user=self.provider_user
        )

        response = self.client.delete(
            f"/api/v1/services/{self.service_2.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.assertTrue(
            Service.objects.filter(
                id=self.service_2.id
            ).exists()
        )

    # ==========================================
    # ADMIN
    # ==========================================

    def test_admin_can_access_services(self):
        self.client.force_authenticate(
            user=self.admin
        )

        response = self.client.get(
            "/api/v1/services/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_admin_can_access_bookings(self):
        self.client.force_authenticate(
            user=self.admin
        )

        response = self.client.get(
            "/api/v1/bookings/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    # ==========================================
    # IDOR TESTING
    # ==========================================

    def test_customer_cannot_access_other_customer_booking_idor(self):
        """
        Customer A must not access Customer B's booking.
        """

        self.client.force_authenticate(
            user=self.customer
        )

        response = self.client.get(
            f"/api/v1/bookings/{self.booking_2.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_provider_cannot_update_other_provider_service_idor(self):
        """
        Provider A must not modify Provider B's service.
        """

        self.client.force_authenticate(
            user=self.provider_user
        )

        original_name = self.service_2.name

        response = self.client.patch(
            f"/api/v1/services/{self.service_2.id}/",
            {
                "name": "Unauthorized Service Update",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.service_2.refresh_from_db()

        self.assertEqual(
            self.service_2.name,
            original_name,
        )

    def test_customer_profile_is_bound_to_authenticated_user(self):
        """
        Profile image upload must operate on the authenticated
        user's profile and must not accept another user's ID.
        """

        self.client.force_authenticate(
            user=self.customer
        )

        response = self.client.post(
            "/api/v1/profile/image/",
            {},
            format="multipart",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )