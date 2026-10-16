from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
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

    def test_service_list_caps_requested_page_size_at_100(self):
        cache.clear()

        # Create 100 additional services.
        for index in range(100):
            Service.objects.create(
                name=f"Pagination Service {index}",
                description="Service for pagination testing",
                location="Hyderabad",
                price=Decimal("500.00"),
                status=True,
                category=self.category,
                provider=self.provider,
            )

        # Request more than the maximum allowed page size.
        response = self.client.get(
            self.url,
            {"page_size": 1000},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        # The maximum page size should be 100.
        self.assertEqual(
            len(response.data["results"]),
            100,
        )

        # There are 101 services, so another page should exist.
        self.assertIsNotNone(
            response.data["next"]
        )

    def test_service_list_cache_miss_then_hit(self):
        # The cache should initially be empty.
        self.assertIsNone(
            cache.get(self.cache_key)
        )

        # First request: cache MISS.
        first_response = self.client.get(
            self.url
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK,
        )

        # The API should now have cached the response.
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

        # Second request: cache HIT.
        second_response = self.client.get(
            self.url
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_200_OK,
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
            status.HTTP_200_OK,
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
        # Populate the cache.
        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
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
            status.HTTP_201_CREATED,
        )

        # Creating a service should invalidate the cache.
        self.assertIsNone(
            cache.get(self.cache_key)
        )

        # The next request should rebuild the cache.
        refreshed_response = self.client.get(
            self.url
        )

        self.assertEqual(
            refreshed_response.status_code,
            status.HTTP_200_OK,
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

        # Verify that the new service appears in the response.
        results = (
            refreshed_response.data.get(
                "results",
                refreshed_response.data,
            )
            if isinstance(
                refreshed_response.data,
                dict,
            )
            else refreshed_response.data
        )

        self.assertTrue(
            any(
                item["name"] == "New Cached Service"
                for item in results
            )
        )

    def test_service_list_cache_is_invalidated_after_service_update(self):
        # Populate the cache.
        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIsNotNone(
            cache.get(self.cache_key)
        )

        # Update the service through the API.
        detail_url = (
            f"{self.url}{self.service.id}/"
        )

        update_response = self.client.patch(
            detail_url,
            {
                "name": "Updated Cache API Service",
            },
            format="json",
        )

        self.assertEqual(
            update_response.status_code,
            status.HTTP_200_OK,
        )

        # The old cached list should be removed.
        self.assertIsNone(
            cache.get(self.cache_key)
        )

        # A fresh request should rebuild the list.
        refreshed_response = self.client.get(
            self.url
        )

        self.assertEqual(
            refreshed_response.status_code,
            status.HTTP_200_OK,
        )

        results = (
            refreshed_response.data.get(
                "results",
                refreshed_response.data,
            )
            if isinstance(
                refreshed_response.data,
                dict,
            )
            else refreshed_response.data
        )

        self.assertTrue(
            any(
                item["name"] == "Updated Cache API Service"
                for item in results
            )
        )

    def test_service_list_cache_is_invalidated_after_service_deletion(self):
        # Populate the cache.
        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIsNotNone(
            cache.get(self.cache_key)
        )

        # Delete the service through the API.
        detail_url = (
            f"{self.url}{self.service.id}/"
        )

        delete_response = self.client.delete(
            detail_url
        )

        self.assertEqual(
            delete_response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

        # Confirm that the service was deleted from the database.
        self.assertFalse(
            Service.objects.filter(
                pk=self.service.pk
            ).exists()
        )

        # The cached list should be removed.
        self.assertIsNone(
            cache.get(self.cache_key)
        )

        # A fresh request should not contain the deleted service.
        refreshed_response = self.client.get(
            self.url
        )

        self.assertEqual(
            refreshed_response.status_code,
            status.HTTP_200_OK,
        )

        results = (
            refreshed_response.data.get(
                "results",
                refreshed_response.data,
            )
            if isinstance(
                refreshed_response.data,
                dict,
            )
            else refreshed_response.data
        )

        self.assertFalse(
            any(
                item["name"] == "Cache API Service"
                for item in results
            )
        )

    @patch(
        "services.views.cache.get",
        side_effect=ConnectionError(
            "Simulated Redis read failure"
        ),
    )
    def test_service_list_works_when_cache_read_fails(
        self,
        mock_cache_get,
    ):
        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertTrue(
            Service.objects.filter(
                pk=self.service.pk
            ).exists()
        )

        mock_cache_get.assert_called_once()

    @patch(
        "services.views.cache.set",
        side_effect=ConnectionError(
            "Simulated Redis write failure"
        ),
    )
    def test_service_list_works_when_cache_write_fails(
        self,
        mock_cache_set,
    ):
        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertTrue(
            Service.objects.filter(
                pk=self.service.pk
            ).exists()
        )

        mock_cache_set.assert_called_once()
