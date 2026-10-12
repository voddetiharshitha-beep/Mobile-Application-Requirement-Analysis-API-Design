# Incident Troubleshooting Guide

## 1. Purpose

This document describes how to identify, investigate, and recover from failures in the Django mobile service-booking backend.

The application depends on Django, PostgreSQL, Redis, Celery, and the external Stripe payment service.

## 2. Dependency Map

| Dependency | Purpose | Impact of failure |
|---|---|---|
| Django application | API endpoints and business logic | API requests may fail |
| PostgreSQL | Users, services, bookings, payments, and notifications | Database-backed operations may fail |
| Redis | Service-list caching and other configured Redis-backed features | Cache access and Redis-dependent features may fail |
| Celery | Background notification processing | Background tasks may be delayed or fail |
| Stripe | External payment processing | Payment operations may fail or time out |

## 3. Health Checks

### Liveness

Endpoint: `GET /health/live/`

Expected result: HTTP 200 with `{"status": "alive"}`.

This confirms that the application can respond. It does not prove that all dependencies are healthy.

### Readiness

Endpoint: `GET /health/ready/`

Expected healthy result: HTTP 200, with database and Redis both reported as `ok`.

If a required dependency is unavailable, the endpoint should return HTTP 503 and identify the unavailable dependency.

### PowerShell verification

From the project directory, with the virtual environment activated:

`python manage.py check`

Test the endpoints using Django's test client:

`python manage.py shell -c "from django.test import Client; c=Client(); print(c.get('/health/live/', HTTP_HOST='localhost').status_code); r=c.get('/health/ready/', HTTP_HOST='localhost'); print(r.status_code, r.json())"`

## 4. Request IDs and Logs

Each HTTP response should include an `X-Request-ID` header. Structured JSON logs should include the request ID, HTTP method, path, status code, and request duration.

When investigating an incident:

1. Record the failing endpoint and approximate time.
2. Record the response status and `X-Request-ID`.
3. Find the matching request log.
4. Check application and dependency logs around the same time.
5. Avoid sharing passwords, tokens, payment secrets, or sensitive customer data in logs or incident reports.

A request ID helps correlate logs; it does not itself guarantee that all background-task logs carry the same ID.

## 5. PostgreSQL Failure

### Symptoms

- Database connection errors or timeouts.
- API operations that read or write database records fail.
- Readiness returns HTTP 503 with the database marked unavailable.

### Diagnostics

Check Django configuration:

`python manage.py check`

On Windows, check the PostgreSQL service:

`Get-Service *postgres*`

Check whether the configured database port is reachable:

`Test-NetConnection 127.0.0.1 -Port 5432`

Use the actual configured host and port if they differ from these defaults.

### Recovery

1. Check PostgreSQL service status and database logs.
2. Verify the database host, port, credentials, and database name.
3. Restore database availability before retrying failed operations.
4. Check whether a booking or payment was already created before repeating a write request.

Do not automatically retry every database error indefinitely.

## 6. Redis Failure

### Symptoms

- Cache access errors.
- Readiness returns HTTP 503 with Redis marked unavailable.
- Redis-dependent throttling, channels, or background infrastructure may be affected, depending on configuration.

### Diagnostics

Check the container:

`docker ps -a --filter "name=notification-redis"`

Check Redis connectivity:

`docker exec notification-redis redis-cli ping`

Expected response: `PONG`.

Check the host port:

`Test-NetConnection 127.0.0.1 -Port 6379`

### Recovery

1. Check whether the Redis container is running.
2. Inspect logs with `docker logs notification-redis`.
3. Restore Redis connectivity and recheck readiness.
4. Confirm that cache entries are repopulated correctly.

The service-list cache is designed to fall back to database-backed responses when cache reads or writes fail. This behavior does not guarantee that every Redis-dependent feature can continue during an outage.

## 7. Celery Failure

### Symptoms

- Notifications are delayed or missing.
- Tasks remain queued or workers are unavailable.
- Task execution errors appear in worker logs.

### Diagnostics

Check running containers and processes:

`docker ps`

Inspect Celery startup and worker logs using the command or service manager used to start the worker.

Verify that the worker can connect to its configured broker and that the broker is reachable.

### Recovery

1. Confirm the configured broker is available.
2. Restart the worker using the project's normal startup procedure if necessary.
3. Inspect failed tasks and worker logs.
4. Check whether the notification already exists before manually replaying a task.

Notification creation uses `get_or_create()` and database uniqueness constraints to help prevent duplicates. Do not assume automatic Celery retries are enabled unless the task configuration explicitly enables them.

## 8. Stripe Payment Failure or Timeout

### Symptoms

- Payment requests fail or return a safe external-service error.
- Requests take longer than expected.
- The Stripe service reports an error or a network timeout.

### Configuration

The current Stripe client is configured with a 10-second HTTP timeout and two network retries.

Payment-intent creation requires an idempotency key and passes it to Stripe.

### Recovery

1. Check Stripe availability and application logs.
2. Verify that the configured API key is valid without exposing it.
3. Record the internal payment reference and relevant request ID.
4. If the result is uncertain after a timeout, check the existing payment record and reconcile with Stripe before attempting a new payment.
5. Reuse the same Stripe idempotency key for a retry of the same logical payment operation.

Never create a new payment attempt with a fresh idempotency key simply because the original request timed out. The external service may already have processed it.

## 9. Retry and Idempotency Rules

Retries are appropriate only when the operation is safe to repeat.

- Use bounded retries for transient network errors where supported.
- Do not blindly retry validation errors, authorization failures, or permanent business-rule failures.
- Reuse the original idempotency key for retries of the same logical payment or booking request.
- Check existing records after an uncertain response before creating new records.
- Use database transactions and uniqueness constraints where needed to protect state.
- Avoid adding automatic retries to tasks that perform non-idempotent side effects without first making those effects safe.

## 10. Incident Checklist

- [ ] Record the start time and affected endpoint.
- [ ] Capture the HTTP status and request ID.
- [ ] Check `/health/live/` and `/health/ready/`.
- [ ] Identify the failed dependency.
- [ ] Review application, database, Redis, worker, or external-service logs.
- [ ] Restore dependency availability.
- [ ] Verify whether the original operation completed before retrying it.
- [ ] Re-run the relevant tests.
- [ ] Verify that normal requests and health checks work again.
- [ ] Record the cause, recovery action, and any follow-up work.

## 11. Verification Status

The following checks have been run during development:

- Django system check passed.
- Liveness and readiness endpoints returned HTTP 200 while PostgreSQL and Redis were available.
- Four health-check tests passed, including simulated PostgreSQL, Redis, and combined dependency failures.
- Stripe tests cover client timeout/retry configuration, required idempotency keys, and safe error conversion.
- Redis service-list cache fail-open tests passed in earlier verification.

Before treating resilience work as complete, also verify Celery failure behavior, booking idempotency, distributed-lock concurrency, and the full regression suite.
