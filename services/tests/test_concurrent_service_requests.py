
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import django

PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import close_old_connections
from django.test import override_settings
from rest_framework.test import APIClient


URL = "/api/v1/services/?page=1"
TOTAL_REQUESTS = 20
MAX_WORKERS = 5


def make_request(user_id):
    """Send one authenticated GET request in an independent worker."""
    close_old_connections()

    try:
        user = get_user_model().objects.get(pk=user_id)
        client = APIClient()
        client.force_authenticate(user=user)

        start = time.perf_counter()
        response = client.get(URL)
        elapsed_ms = (time.perf_counter() - start) * 1000

        return {
            "status": response.status_code,
            "elapsed_ms": elapsed_ms,
        }

    except Exception as exc:
        return {
            "status": "ERROR",
            "elapsed_ms": 0,
            "error": str(exc),
        }

    finally:
        close_old_connections()


@override_settings(
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"]
)
def main():
    User = get_user_model()
    user = User.objects.filter(is_active=True).first()

    if user is None:
        print("ERROR: No active user exists in the database.")
        return

    # Clear the service-list cache before priming it.
    try:
        cache.delete_pattern("service_list:*")
    except Exception as exc:
        print(f"ERROR: Could not clear service-list cache: {exc}")
        return

    # Prime the cache before measuring concurrent requests.
    warm_client = APIClient()
    warm_client.force_authenticate(user=user)
    warm_response = warm_client.get(URL)

    if warm_response.status_code != 200:
        print(
            "ERROR: Could not prime service-list cache. "
            f"HTTP {warm_response.status_code}"
        )
        return

    print("=" * 65)
    print("CONCURRENT SERVICE-LIST REQUEST TEST")
    print("=" * 65)
    print(f"Endpoint       : {URL}")
    print(f"Total requests : {TOTAL_REQUESTS}")
    print(f"Worker threads : {MAX_WORKERS}")
    print("Cache          : Primed before concurrent requests")
    print()

    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(make_request, user.pk)
            for _ in range(TOTAL_REQUESTS)
        ]

        for future in as_completed(futures):
            results.append(future.result())

    successful = [
        result for result in results
        if result["status"] == 200
    ]

    failures = [
        result for result in results
        if result["status"] != 200
    ]

    successful_times = [
        result["elapsed_ms"] for result in successful
    ]

    print(f"Successful HTTP 200 : {len(successful)}")
    print(f"Failed requests     : {len(failures)}")

    if successful_times:
        print(
            "Average response    : "
            f"{statistics.mean(successful_times):.2f} ms"
        )
        print(
            "Fastest response    : "
            f"{min(successful_times):.2f} ms"
        )
        print(
            "Slowest response    : "
            f"{max(successful_times):.2f} ms"
        )

    if failures:
        print()
        print("Failure details:")
        for failure in failures:
            print(failure)

    print("=" * 65)

    if len(successful) == TOTAL_REQUESTS:
        print(
            "RESULT: PASS — all concurrent requests "
            "returned HTTP 200."
        )
    else:
        print(
            "RESULT: CHECK REQUIRED — inspect failed requests."
        )


if __name__ == "__main__":
    main()
