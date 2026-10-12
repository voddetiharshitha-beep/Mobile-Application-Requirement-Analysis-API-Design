
import logging
import uuid

from django.core.cache import cache
from django.db import connections
from django.http import JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def liveness_view(request):
    """
    Report whether the Django application is running.
    This endpoint does not depend on PostgreSQL or Redis.
    """
    return JsonResponse(
        {"status": "alive"},
        status=200,
    )


@require_GET
def readiness_view(request):
    """
    Check whether the database and Redis are available.

    Return HTTP 200 when both dependencies are healthy.
    Return HTTP 503 when either dependency is unavailable.
    """
    dependencies = {}
    all_healthy = True

    # Check PostgreSQL.
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

        dependencies["database"] = "ok"

    except Exception:
        logger.exception(
            "Readiness check: database unavailable"
        )

        dependencies["database"] = "unavailable"
        all_healthy = False

    # Check Redis by writing, reading, and deleting a temporary key.
    cache_key = f"health-check:{uuid.uuid4().hex}"

    try:
        cache.set(
            cache_key,
            "ok",
            timeout=10,
        )

        cache_value = cache.get(cache_key)

        if cache_value != "ok":
            raise RuntimeError(
                "Cache read/write verification failed"
            )

        dependencies["redis"] = "ok"

    except Exception:
        logger.exception(
            "Readiness check: cache unavailable"
        )

        dependencies["redis"] = "unavailable"
        all_healthy = False

    finally:
        # Clean up the temporary key when possible.
        try:
            cache.delete(cache_key)
        except Exception:
            logger.warning(
                "Readiness check: temporary cache key cleanup failed",
                exc_info=True,
            )

    response_status = (
        200 if all_healthy else 503
    )

    return JsonResponse(
        {
            "status": (
                "ready" if all_healthy else "not_ready"
            ),
            "dependencies": dependencies,
        },
        status=response_status,
    )
