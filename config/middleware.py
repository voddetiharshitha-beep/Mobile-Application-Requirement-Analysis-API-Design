
import json
import logging
import re
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone


request_id_context = ContextVar("request_id", default="-")


class RequestIDMiddleware:
    """Attach a safe request ID to each HTTP request and response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied_id = request.headers.get("X-Request-ID", "")

        # Accept only a short, safe identifier; otherwise generate one.
        if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", supplied_id):
            request_id = supplied_id
        else:
            request_id = str(uuid.uuid4())

        request.request_id = request_id
        token = request_id_context.set(request_id)
        started = time.monotonic()

        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id

            logging.getLogger("request").info(
                "HTTP request completed",
                extra={
                    "http_method": request.method,
                    "http_path": request.path,
                    "status_code": response.status_code,
                    "duration_ms": round(
                        (time.monotonic() - started) * 1000, 2
                    ),
                },
            )
            return response
        finally:
            request_id_context.reset(token)


class RequestIDLogFilter(logging.Filter):
    """Add the current request ID to each log record."""

    def filter(self, record):
        record.request_id = request_id_context.get()
        return True


class JSONLogFormatter(logging.Formatter):
    """Format logs as structured JSON lines."""

    def format(self, record):
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }

        for field in (
            "http_method",
            "http_path",
            "status_code",
            "duration_ms",
            "correlation_id",
        ):
            if hasattr(record, field):
                data[field] = getattr(record, field)

        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)

        return json.dumps(data, ensure_ascii=False)
