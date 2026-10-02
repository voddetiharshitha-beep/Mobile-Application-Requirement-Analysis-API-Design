from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from services.models import Category, Provider, Service


@override_settings(
    SERVICE_LIST_CACHE_TIMEOUT=60,
)
class ServiceCacheAPITest(TestCase):

    def setUp(self):
        cache.clear()

        self.client = APIClient()

        self.user = User.objects.create_user(
            username="cache_api_user",
            password="Test@12345",
        )

        self.client.force_authenticate(
            user=self.user
        )

        self.category = Category.objects.create(
            name="Cache API Category",
        )

        self.provider = Provider.objects.create(
            user=self.user,
            name="Cache API Provider",
            description="Cache API provider",
            status=True,
        )

        self.service = Service.objects.create(
            name="Cache API Service",
            description="Cache API service",
            location="Hyderabad",
            price=Decimal("500.00"),
            status=True,
            category=self.category,
            provider=self.provider,
        )

        self.url = "/api/v1/services/"

        self.cache_key = (
            "service_list:/api/v1/services/"
        )

    def tearDown(self):
        cache.clear()

    def test_service_list_cache_miss_then_hit(self):
        # Cache should initially be empty.
        self.assertIsNone(
            cache.get(self.cache_key)
        )

        # First request = cache MISS.
        first_response = self.client.get(
            self.url
        )

        self.assertEqual(
            first_response.status_code,
            200,
        )

        # The API should now have stored the response.
        cached_data = cache.get(
            self.cache_key
        )

        self.assertIsNotNone(
            cached_data
        )

        self.assertEqual(
            cached_data,
            first_response.data,
        )

        # Second request = cache HIT.
        second_response = self.client.get(
            self.url
        )

        self.assertEqual(
            second_response.status_code,
            200,
        )

        self.assertEqual(
            second_response.data,
            first_response.data,
        )

    def test_service_list_cache_has_ttl(self):
        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        ttl = cache.ttl(
            self.cache_key
        )

        self.assertGreater(
            ttl,
            0,
        )

        self.assertLessEqual(
            ttl,
            60,
        )

    def test_service_list_cache_is_invalidated_after_service_creation(self):
        # First request populates the cache.
        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        cached_before = cache.get(
            self.cache_key
        )

        self.assertIsNotNone(
            cached_before
        )

        # Create another service through the API.
        create_response = self.client.post(
            self.url,
            {
                "name": "New Cached Service",
                "description": "New service",
                "location": "Hyderabad",
                "price": "700.00",
                "status": True,
                "category": str(
                    self.category.id
                ),
            },
            format="json",
        )

        self.assertEqual(
            create_response.status_code,
            201,
        )

        # Creating a service should invalidate
        # the Service List cache.
        cached_after = cache.get(
            self.cache_key
        )

        self.assertIsNone(
            cached_after
        )

        # The next request rebuilds the cache.
        refreshed_response = self.client.get(
            self.url
        )

        self.assertEqual(
            refreshed_response.status_code,
            200,
        )

        refreshed_cache = cache.get(
            self.cache_key
        )

        self.assertIsNotNone(
            refreshed_cache
        )

        self.assertEqual(
            refreshed_cache,
            refreshed_response.data,
        )