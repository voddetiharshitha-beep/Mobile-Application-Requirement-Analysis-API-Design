from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from services.models import Category, Provider, ProviderProfile, Service


class AdminJourneyTests(TestCase):

    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="admin_test",
            email="admin@example.com",
            password="AdminPassword123!",
        )

        self.category = Category.objects.create(
            name="Admin Test Category",
            description="Admin test category",
            status=True,
        )

        self.provider_user = User.objects.create_user(
            username="admin_provider",
            email="provider@example.com",
            password="TestPassword123!",
        )

        self.provider = Provider.objects.create(
            user=self.provider_user,
            name="Admin Test Provider",
            description="Admin test provider",
            status=True,
        )

        self.provider_profile = ProviderProfile.objects.create(
            provider=self.provider,
            name="Admin Provider Profile",
            description="Admin provider profile",
            status=True,
        )

        self.service = Service.objects.create(
            name="Admin Test Service",
            description="Admin test service",
            location="Hyderabad",
            price=Decimal("500.00"),
            status=True,
            category=self.category,
            provider=self.provider,
        )

        self.client.force_login(self.admin_user)

    def test_admin_can_access_admin_site(self):
        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 200)

    def test_admin_can_view_category(self):
        response = self.client.get(
            reverse("admin:services_category_changelist")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin Test Category")

    def test_admin_can_view_provider(self):
        response = self.client.get(
            reverse("admin:services_provider_changelist")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin Test Provider")

    def test_admin_can_view_provider_profile(self):
        response = self.client.get(
            reverse("admin:services_providerprofile_changelist")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin Provider Profile")

    def test_admin_can_view_service(self):
        response = self.client.get(
            reverse("admin:services_service_changelist")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin Test Service")