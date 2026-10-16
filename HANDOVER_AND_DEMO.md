# Project Handover and Demo Guide

## 1. Purpose

This document summarizes the current verification results, local startup requirements, demonstration flow, and known limitations for the Django REST Framework mobile service-booking backend.

## 2. Verification Results

The following checks were completed during the current validation session:

| Check | Result |
|---|---|
| Django system check (`python manage.py check`) | Passed — no issues reported |
| Focused reliability, WebSocket, notification queue-resilience, and observability tests | 30 tests passed |
| Individual WebSocket booking-status update test | 1 test passed |
| Booking/regression, notification, and payment journey tests | 13 tests passed |
| Full service test suite (`python manage.py test services.tests`) | 194 tests passed |
| Full service test suite failures/errors | None reported |

The full service test suite completed in approximately 553.1 seconds.

These results establish that the tested service suite passed in the local environment at the time of verification. They do not independently establish production readiness or external push-notification delivery.

## 3. Local Startup Prerequisites

Before demonstrating the application, verify that the required services are available.

1. Activate the project's Python virtual environment.
2. Start the PostgreSQL service and verify the configured database connection.
3. Start the Redis container, if it is stopped:

   ```powershell
   docker start notification-redis
   ```

   If Docker reports that the container is already running, continue to the health check.

4. Verify Redis:

   ```powershell
   docker exec notification-redis redis-cli ping
   ```

   Expected response: `PONG`.

5. Verify Django configuration:

   ```powershell
   python manage.py check
   ```

6. Start the Django ASGI application using the project's configured ASGI server. For a local WebSocket demonstration, use the project's established Daphne command if Daphne is installed and configured:

   ```powershell
   daphne -b 127.0.0.1 -p 8000 config.asgi:application
   ```

   Keep the server terminal open. If port 8000 is already in use, identify the existing process before starting another server.

7. Start a Celery worker in a separate terminal if the demonstration includes asynchronous notification tasks. Use the worker command and settings configured for this project.

Do not display environment secrets, API keys, webhook secrets, or user credentials during the demonstration.

## 4. Suggested Demo Sequence

### A. API and database health

- Show that `python manage.py check` completes without errors.
- Confirm the API responds through the configured local server.
- Use a test account and test data rather than real customer information.

### B. Booking workflow

- Authenticate as a customer.
- Create a booking using valid service and availability data.
- Authenticate as the appropriate provider and confirm the booking.
- Verify that the customer can see the updated booking status.
- Demonstrate authorization checks using an account that should not have access, where suitable.

### C. Payment workflow

- Initiate a payment using the project's configured test or mock payment flow.
- Show the resulting payment status.
- If demonstrating Stripe integration, use Stripe test credentials and the configured test webhook procedure. Do not claim a live payment was processed unless independently verified.

### D. Notifications and WebSockets

- Connect an authenticated client to the booking WebSocket endpoint using a valid booking ID.
- Show the connection-established event.
- Update a booking status and verify the expected event or notification.
- If a notification is not delivered to an external push provider, distinguish database notification creation from external delivery.

### E. Caching and resilience

- Demonstrate a service-list request and repeat the same request to exercise the cache.
- Show the relevant cache tests and invalidation behavior.
- Explain that Redis availability is a prerequisite for the Redis-backed functionality exercised by the project.

## 5. Known Limitations and Operational Notes

- **Redis dependency:** Redis-backed caching and channel-layer operations require Redis to be reachable. Verify Redis before testing WebSockets or cache-dependent flows.
- **Manual failed-event recovery:** `FAILED_EVENT_RECOVERY.md` documents a manual investigation and recovery procedure. This must not be represented as an automated dead-letter queue.
- **External notification delivery:** Database notification records and task execution do not, by themselves, prove delivery to an external push-notification provider.
- **WebSocket verification:** The targeted WebSocket test and the full service test suite passed in the recorded local run. Recheck behavior after changes to ASGI configuration, routing, authentication, or Redis settings.
- **Production configuration:** Run the deployment checks and review HTTPS, secure cookies, secrets, database access, and service monitoring before deployment. A successful Django system check is not a substitute for a production security review.
- **Performance claims:** Do not claim a specific production throughput or performance improvement without reproducible measurements and recorded test conditions.

## 6. Reproducible Final Checks

Run from the project root with the virtual environment activated:

```powershell
python manage.py check
python manage.py test services.tests
git diff --check
git status --short
```

Record the date, environment, test result, and any known failures when repeating validation.

## 7. Handover Checklist

- [ ] PostgreSQL and Redis availability verified.
- [ ] Django system check passed.
- [ ] Full service test suite passed.
- [ ] Booking and payment demonstration completed using test data.
- [ ] WebSocket and notification behavior demonstrated.
- [ ] Manual recovery limitation communicated.
- [ ] Secrets and personal data excluded from screenshots and logs.
- [ ] Modified and untracked files reviewed before committing.
- [ ] Production configuration and deployment checks reviewed separately.

## 8. Current Handover Status

The local verification results listed in this document were reported as passing during the current validation session. Re-run the final checks before committing or releasing the project. Review all modified and untracked files, and do not commit temporary backups or review artifacts without confirming whether they belong in version control.
