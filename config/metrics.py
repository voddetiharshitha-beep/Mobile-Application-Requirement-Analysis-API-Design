
import time

from django.http import HttpResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)


# Count completed HTTP requests using bounded labels.
HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP responses, excluding metrics scrapes.",
    ["method", "status_class"],
)

# Count HTTP server errors (5xx).
HTTP_SERVER_ERRORS = Counter(
    "http_server_errors_total",
    "Total HTTP server errors (5xx).",
    ["method"],
)

# Measure HTTP request duration in seconds.
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method"],
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
    ),
)

# Count notification pipeline outcomes using bounded labels.
NOTIFICATION_EVENTS = Counter(
    "notification_events_total",
    "Total notification pipeline events by event type and outcome.",
    ["event", "outcome"],
)

ALLOWED_NOTIFICATION_EVENTS = {
    "queue",
    "processing",
}

ALLOWED_NOTIFICATION_OUTCOMES = {
    "queued",
    "failed",
    "created",
    "duplicate",
    "retryable_error",
}


def record_notification_event(event, outcome):
    """Record a notification event with bounded Prometheus labels."""
    normalized_event = (
        event if event in ALLOWED_NOTIFICATION_EVENTS else "other"
    )
    normalized_outcome = (
        outcome
        if outcome in ALLOWED_NOTIFICATION_OUTCOMES
        else "other"
    )

    NOTIFICATION_EVENTS.labels(
        event=normalized_event,
        outcome=normalized_outcome,
    ).inc()


def record_http_request(method, status_code, duration_seconds):
    """Record metrics for one completed HTTP request."""
    allowed_methods = {
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "HEAD",
        "OPTIONS",
    }

    normalized_method = (
        method if method in allowed_methods else "OTHER"
    )
    status_class = f"{status_code // 100}xx"

    HTTP_REQUESTS.labels(
        method=normalized_method,
        status_class=status_class,
    ).inc()

    if status_code >= 500:
        HTTP_SERVER_ERRORS.labels(
            method=normalized_method,
        ).inc()

    HTTP_REQUEST_DURATION.labels(
        method=normalized_method,
    ).observe(max(0.0, duration_seconds))


class PrometheusMetricsMiddleware:
    """Collect HTTP metrics without counting metrics scrapes."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.rstrip("/") == "/metrics":
            return self.get_response(request)

        started = time.monotonic()

        try:
            response = self.get_response(request)
        except Exception:
            record_http_request(
                request.method,
                500,
                time.monotonic() - started,
            )
            raise

        record_http_request(
            request.method,
            response.status_code,
            time.monotonic() - started,
        )

        return response


def metrics_view(request):
    """Expose metrics in Prometheus text format."""
    return HttpResponse(
        generate_latest(),
        content_type=CONTENT_TYPE_LATEST,
    )
