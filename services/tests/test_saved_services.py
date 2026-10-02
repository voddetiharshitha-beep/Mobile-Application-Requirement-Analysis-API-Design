from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from services.models import (
    Category,
    Provider,
    SavedService,
    Service,
)

User = get_user_model()


class SavedServiceAPITests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user(
            username="saved_customer",
            email="saved_customer@example.com",
            password="StrongPassword123!",
        )

        cls.other_customer = User.objects.create_user(
            username="other_customer",
            email="other_customer@example.com",
            password="StrongPassword123!",
        )

        cls.provider_user = User.objects.create_user(
            username="saved_provider",
            email="saved_provider@example.com",
            password="StrongPassword123!",
        )

        cls.provider = Provider.objects.create(
            user=cls.provider_user,
            name="Saved Service Provider",
            description="Provider for saved-service tests.",
        )

        cls.category = Category.objects.create(
            name="Saved Service Category",
            description="Category for saved-service tests.",
        )

        cls.service = Service.objects.create(
            name="Saved Test Service",
            description="Service used for saved-service tests.",
            location="Hyderabad",
            price="500.00",
            category=cls.category,
            provider=cls.provider,
        )

        cls.second_service = Service.objects.create(
            name="Second Saved Test Service",
            description="Second service used for tests.",
            location="Hyderabad",
            price="700.00",
            category=cls.category,
            provider=cls.provider,
        )

    def setUp(self):
        self.url = "/api/v1/saved-services/"

    def test_unauthenticated_user_cannot_view_saved_services(self):
        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_customer_can_save_service(self):
        self.client.force_authenticate(
            user=self.customer,
        )

        response = self.client.post(
            self.url,
            {
                "service": str(self.service.id),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            SavedService.objects.filter(
                customer=self.customer,
                service=self.service,
            ).count(),
            1,
        )

    def test_customer_cannot_save_same_service_twice(self):
        self.client.force_authenticate(
            user=self.customer,
        )

        first_response = self.client.post(
            self.url,
            {
                "service": str(self.service.id),
            },
            format="json",
        )

        second_response = self.client.post(
            self.url,
            {
                "service": str(self.service.id),
            },
            format="json",
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            SavedService.objects.filter(
                customer=self.customer,
                service=self.service,
            ).count(),
            1,
        )

    def test_customer_can_view_only_own_saved_services(self):
        SavedService.objects.create(
            customer=self.customer,
            service=self.service,
        )

        SavedService.objects.create(
            customer=self.other_customer,
            service=self.second_service,
        )

        self.client.force_authenticate(
            user=self.customer,
        )

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(response.data),
            1,
        )

        self.assertEqual(
            response.data[0]["service"],
            str(self.service.id),
        )

    def test_customer_can_delete_own_saved_service(self):
        saved_service = SavedService.objects.create(
            customer=self.customer,
            service=self.service,
        )

        self.client.force_authenticate(
            user=self.customer,
        )

        response = self.client.delete(
            f"{self.url}{saved_service.id}/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        self.assertFalse(
            SavedService.objects.filter(
                id=saved_service.id,
            ).exists(),
        )

        self.assertTrue(
            Service.objects.filter(
                id=self.service.id,
            ).exists(),
        )

    def test_customer_cannot_delete_another_users_saved_service(self):
        saved_service = SavedService.objects.create(
            customer=self.other_customer,
            service=self.service,
        )

        self.client.force_authenticate(
            user=self.customer,
        )

        response = self.client.delete(
            f"{self.url}{saved_service.id}/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.assertTrue(
            SavedService.objects.filter(
                id=saved_service.id,
            ).exists(),
        )

    def test_invalid_service_is_rejected(self):
        self.client.force_authenticate(
            user=self.customer,
        )

        response = self.client.post(
            self.url,
            {
                "service": "00000000-0000-0000-0000-000000000000",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_provider_cannot_use_customer_saved_services_api(self):
        self.client.force_authenticate(
            user=self.provider_user,
        )

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_delete_missing_saved_service_returns_404(self):
        self.client.force_authenticate(
            user=self.customer,
        )

        response = self.client.delete(
            f"{self.url}00000000-0000-0000-0000-000000000000/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )