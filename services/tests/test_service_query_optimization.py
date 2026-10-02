from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from services.models import Category, Provider, Service
from services.serializers import ServiceListSerializer


class ServiceQueryOptimizationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="query_test_user",
            password="Test@12345",
        )

        self.category = Category.objects.create(
            name="Cleaning",
        )

        self.provider = Provider.objects.create(
            user=self.user,
            name="Test Provider",
            description="Test provider",
            status=True,
        )

        self.service = Service.objects.create(
            name="Test Cleaning",
            description="Test service description",
            location="Hyderabad",
            price="500.00",
            status=True,
            category=self.category,
            provider=self.provider,
        )

    def test_service_list_query_count(self):
        queryset = (
            Service.objects
            .select_related(
                "category",
                "provider",
            )
            .all()
        )

        with CaptureQueriesContext(connection) as queries:
            services = list(queryset[:20])

            ServiceListSerializer(
                services,
                many=True,
            ).data

        print(
            "\nService list SQL query count:",
            len(queries),
        )

        for query in queries:
            print("\nSQL:")
            print(query["sql"])

        self.assertEqual(
    len(queries),
    1,
    "Service list should execute exactly one SQL query.",
)