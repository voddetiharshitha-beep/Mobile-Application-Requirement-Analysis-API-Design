
import os
import statistics
import threading
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
from django.db import close_old_connections, connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient


URL = "/api/v1/services/?page=1"
TOTAL_REQUESTS = 5
MAX_WORKERS = 5

# Make all workers approach the endpoint together.
start_barrier = threading.Barrier(MAX_WORKERS)


def make_request(user_id):
    close_old_connections()

    try:
        user = get_user_model().objects.get(pk=user_id)
        client = APIClient()
        client.force_authenticate(user=user)

        start_barrier.wait(timeout=15)

        start = time.perf_counter()

        with CaptureQueriesContext(connection) as queries:
            response = client.get(URL)

        elapsed_ms = (time.perf_counter() - start) * 1000

        return {
            "status": response.status_code,
            "elapsed_ms": elapsed_ms,
            "db_queries": len(queries),
        }

    except Exception as exc:
        return {
            "status": "ERROR",
            "elapsed_ms": 0,
            "db_queries": 0,
            "error": str(exc),
        }

    finally:
        close_old_connections()


@override_settings(
    ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"]
)
def main():
    user = get_user_model().objects.filter(is_active=True).first()

    if user is None:
        print("ERROR: No active user exists in the database.")
        return

    try:
        cache.delete_pattern("service_list:*")

        # Confirm that the cache starts empty for this endpoint.
        if cache.get(f"service_list:{URL}") is not None:
            print("ERROR: Service-list cache was not empty.")
            return

    except Exception as exc:
        print(f"ERROR: Redis cache preparation failed: {exc}")
        return

    print("=" * 65)
    print("COLD-CACHE CONCURRENCY TEST")
    print("=" * 65)
    print(f"Endpoint       : {URL}")
    print(f"Concurrent requests: {TOTAL_REQUESTS}")
    print(f"Worker threads : {MAX_WORKERS}")
    print("Cache          : Cleared; no warm-up request")
    print("Starting all workers together...")
    print()

    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(make_request, user.pk)
            for _ in range(TOTAL_REQUESTS)
        ]

        for future in as_completed(futures):
            results.append(future.result())

    successful = [r for r in results if r["status"] == 200]
    failures = [r for r in results if r["status"] != 200]

    print(f"Successful HTTP 200 : {len(successful)}")
    print(f"Failed requests     : {len(failures)}")

    if successful:
        times = [r["elapsed_ms"] for r in successful]
        print(f"Average response    : {statistics.mean(times):.2f} ms")
        print(f"Fastest response    : {min(times):.2f} ms")
        print(f"Slowest response    : {max(times):.2f} ms")
        print(
            "Total DB queries    : "
            f"{sum(r['db_queries'] for r in successful)}"
        )
        print("Per-request DB queries:")
        for result in sorted(results, key=lambda r: r["elapsed_ms"]):
            print(
                f"  HTTP {result['status']} | "
                f"{result['elapsed_ms']:.2f} ms | "
                f"{result['db_queries']} DB queries"
            )

    if failures:
        print("\nFailure details:")
        for result in failures:
            if result["status"] != 200:
                print(result)

    print("=" * 65)

    if len(successful) == TOTAL_REQUESTS:
        print("RESULT: PASS — all cold-cache concurrent requests returned HTTP 200.")
    else:
        print("RESULT: CHECK REQUIRED — inspect failed requests.")


if __name__ == "__main__":
    main()
