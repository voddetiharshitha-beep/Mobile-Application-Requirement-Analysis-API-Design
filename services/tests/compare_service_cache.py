
import os
import statistics
import time
from pathlib import Path

import django

# Configure Django when this script is run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings
from rest_framework.test import APIClient


@override_settings(
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"]
)
def main():
    User = get_user_model()

    user = User.objects.filter(is_active=True).first()

    if user is None:
        print("ERROR: No active user exists in the database.")
        return

    client = APIClient()
    client.force_authenticate(user=user)

    # Use the same URL for both cold and warm requests.
    url = "/api/v1/services/?page=1"

    # Clear existing service-list responses.
    cache.delete_pattern("service_list:*")

    def measure_request(label):
        with CaptureQueriesContext(connection) as queries:
            start = time.perf_counter()
            response = client.get(url)
            elapsed_ms = (time.perf_counter() - start) * 1000

        result = {
            "label": label,
            "status": response.status_code,
            "time_ms": elapsed_ms,
            "queries": len(queries),
        }

        print(
            f"{label:<18} "
            f"HTTP {result['status']} | "
            f"{result['time_ms']:.2f} ms | "
            f"{result['queries']} database queries"
        )

        return result

    print("=" * 65)
    print("REDIS SERVICE-LIST CACHE COMPARISON")
    print("=" * 65)
    print(f"User: {user.username}")
    print(f"Endpoint: {url}")
    print()

    # First request: cache miss, expected to populate the cache.
    cold = measure_request("Cold cache")

    if cold["status"] != 200:
        print("ERROR: Cold-cache request did not return HTTP 200.")
        return

    # Repeated requests: expected to use the cached response.
    warm_results = []

    for number in range(1, 6):
        result = measure_request(f"Warm request {number}")
        warm_results.append(result)

        if result["status"] != 200:
            print("ERROR: A warm-cache request did not return HTTP 200.")
            return

    warm_average = statistics.mean(
        result["time_ms"] for result in warm_results
    )

    improvement = None
    if cold["time_ms"] > 0:
        improvement = (
            (cold["time_ms"] - warm_average) / cold["time_ms"]
        ) * 100

    print()
    print("=" * 65)
    print("COMPARISON SUMMARY")
    print("=" * 65)
    print(f"Cold-cache response time : {cold['time_ms']:.2f} ms")
    print(f"Cold-cache DB queries    : {cold['queries']}")
    print(f"Average warm response    : {warm_average:.2f} ms")
    print(
        "Average warm DB queries : "
        f"{statistics.mean(r['queries'] for r in warm_results):.2f}"
    )

    if improvement is not None:
        print(f"Response-time reduction  : {improvement:.2f}%")

    print("=" * 65)


if __name__ == "__main__":
    main()
