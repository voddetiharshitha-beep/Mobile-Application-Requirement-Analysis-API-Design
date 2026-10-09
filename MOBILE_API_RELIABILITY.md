# Mobile API Reliability, Offline Sync & Idempotent Requests

## 1. Objective

This document describes the reliability improvements implemented for the mobile application backend.

The goal is to provide reliable API behavior when mobile clients experience:

* Unstable network connections
* Request retries
* Duplicate requests
* Interrupted synchronization
* Changing datasets
* Concurrent requests
* Temporary request failures

The implementation focuses on booking APIs and mobile synchronization requirements while preserving authorization, data isolation, and API consistency.

---

## 2. Reliability Features Implemented

The backend provides the following reliability features:

* Cursor-based pagination
* Stable synchronization ordering
* Idempotent booking creation
* Duplicate-request protection
* Concurrent-request protection
* Failed-request retry support
* Customer booking isolation
* Provider booking isolation
* Database-backed idempotency records
* Consistent API responses
* Automated regression testing

---

## 3. Offline Synchronization

Mobile clients may lose connectivity while downloading or synchronizing records. Cursor pagination supports synchronization by allowing clients to continue fetching records using a cursor rather than relying on numeric page numbers.

**Implementation file:** `services/sync_pagination.py`

The synchronization pagination configuration is:

```python
from rest_framework.pagination import CursorPagination


class SyncCursorPagination(CursorPagination):
    """
    Cursor pagination for mobile synchronization endpoints.

    Provides cursor-based navigation for datasets that may
    change while the mobile client is downloading records.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-updated_at"
```

### Pagination behavior

The configuration specifies:

* Default page size: 20 records
* Maximum page size: 100 records
* Ordering: `-updated_at`
* Navigation: cursor-based pagination

A paginated response follows this general structure:

```json
{
  "next": "...",
  "previous": null,
  "results": []
}
```

The mobile client should store the `next` cursor and use it to request the next batch of records. After a network interruption, the client can resume from its last successfully processed cursor.

Cursor pagination avoids relying on numeric page numbers, which can become unstable when records are added or updated during synchronization.

**Important:** Cursor pagination alone does not guarantee a complete offline synchronization snapshot when records change during synchronization. Clients should also account for updates, deletions, and any server-side synchronization rules.

---

## 4. Idempotent Booking Requests

Mobile applications may send the same request more than once because of:

* Network timeouts
* Connection interruptions
* User retry actions
* Client-side retries
* Duplicate button presses
* Concurrent requests

Booking creation supports the `Idempotency-Key` request header to prevent duplicate booking creation when the same logical request is retried.

Example:

```http
POST /api/v1/bookings/
Idempotency-Key: mobile-booking-request-12345
Authorization: Bearer <access-token>
Content-Type: application/json
```

The mobile client should generate a unique idempotency key for each logical booking operation and reuse that key when retrying the same operation.

A new key should be generated for a genuinely new booking request, not for a retry of an existing request.

---

## 5. Idempotency Request Flow

The booking API follows this general sequence:

1. Receive the booking request.
2. Read the `Idempotency-Key`.
3. Check whether the request has already been processed.
4. If the request is completed, return the stored response.
5. If another request is currently processing the same key, return a conflict response.
6. If a previous attempt failed and retry is permitted, allow the request to be processed again.
7. Otherwise, validate and process the booking.
8. Store the final response against the idempotency record.

This flow helps prevent duplicate bookings caused by mobile retries and interrupted network responses.

---

## 6. Idempotency States

The idempotency system uses the following states.

### PROCESSING

The request is currently being processed.

A duplicate request using the same idempotency key while processing is in progress receives:

```http
409 Conflict
```

The response indicates that the request is already being processed.

### COMPLETED

The original request has completed successfully.

A retry using the same completed idempotency key returns the stored response rather than creating another booking.

### FAILED

The previous attempt failed.

Where the implementation permits retry, the same idempotency key can be reused after the failed state is reset to processing.

This allows recoverable failures to be retried without requiring the mobile application to generate a different request identity.

---

## 7. Duplicate Request Protection

Duplicate requests using the same idempotency key are protected against creating multiple bookings.

The idempotency record stores information about the request and its resulting response.

This provides protection against:

* Repeated submissions
* Mobile client retries
* Network timeouts after a request has reached the server
* Repeated requests after the original response has been lost

After a request has completed successfully, subsequent requests using the same completed idempotency key return the stored response according to the implementation's idempotency rules.

---

## 8. Concurrent Request Protection

The backend handles concurrent requests that use the same idempotency key.

If one request is already processing, another request using that key must not independently create a second booking.

The concurrent request receives:

```http
409 Conflict
```

The client can retry using the same idempotency key when appropriate.

The concurrency test verifies that concurrent requests using the same key do not create duplicate bookings.

This is important for mobile applications, where multiple network operations may overlap because of retries or repeated user actions.

---

## 9. Validation and Idempotency Ordering

For an existing idempotency key, the implementation checks the idempotency record before normal serializer validation where required by the request flow.

This behavior is important for mobile retries.

For example, the original request may have successfully created a booking, but the mobile client may not have received the response because of a network interruption. A subsequent retry should return the original stored response instead of attempting to create the booking again.

This avoids unnecessarily rejecting a completed retry because the original booking has already affected availability.

New requests must still undergo the normal validation and authorization checks.

---

## 10. Authorization and Data Isolation

Reliability improvements must not bypass authorization or expose another user's booking information.

### Customer access

A customer can list bookings belonging to that customer.

### Provider access

A provider can list bookings assigned to that provider account.

The booking list implementation uses the authenticated user's role and ownership to restrict the queryset.

This ensures that synchronization and booking APIs respect the application's data-isolation requirements.

---

## 11. API Response Consistency

Successful booking creation returns a response following this general structure:

```json
{
  "success": true,
  "message": "Booking created successfully.",
  "data": {}
}
```

When an already-completed idempotent request is retried, the previously stored response is returned according to the implementation.

This allows the mobile client to handle retries consistently and avoid treating a repeated request as a new booking operation.

---

## 12. Automated Testing

The reliability implementation was tested using the Django automated test suite.

Testing covered the following areas:

* Successful booking creation
* Duplicate idempotency requests
* Concurrent idempotency requests
* Failed-request retry behavior
* Completed-request replay
* Customer booking isolation
* Provider booking isolation
* Cursor pagination behavior
* Invalid requests
* Authorization behavior
* Booking workflow behavior
* Payment behavior
* Notification behavior
* API throttling
* Input validation

The complete `services` test suite was run after Redis connectivity was restored.

---

## 13. Regression Testing

During regression testing, issues were identified and corrected.

### Provider booking visibility

The booking list initially filtered all users by `customer`.

The queryset was corrected so providers can see bookings assigned to their own provider account, while customer booking visibility remains restricted to the authenticated customer.

### Cursor pagination response

The synchronization pagination uses Django REST Framework's `CursorPagination`.

Cursor pagination does not provide a `count` field in its standard response format. The affected test was corrected to validate the `results` collection instead.

### Test environment and Redis connectivity

Some earlier test failures occurred while Redis was unavailable at `127.0.0.1:6379`.

Redis connectivity was restored and verified before the successful final regression run.

This allowed the services suite to run with the required supporting service available.

---

## 14. Final Test Result

The complete `services` test suite was executed with:

```powershell
python manage.py test services -v 2
```

**Final result:**

```text
Ran 149 tests in 548.791s

OK
```

The final regression result confirms:

* 149 tests ran successfully.
* 0 test failures.
* 0 test errors.
* The complete `services` test suite passed.

Additional verification confirmed that the concurrent idempotency test passed independently and that the payment journey tests passed.

These results provide evidence that the reliability changes and existing services functionality passed the final automated regression suite.

---

## 15. Test Database Reliability

During an earlier testing session, PostgreSQL temporarily retained the Django test database because active database sessions were present.

The active test database sessions were checked using PostgreSQL system views. After confirming that no active sessions remained, the temporary test database was safely removed.

The production/development database was not deleted.

This was a test-environment cleanup activity and was separate from the application reliability implementation.

---

## 16. Mobile Client Recommendations

The mobile client should:

1. Generate a unique idempotency key for every logical booking request.
2. Persist the key while the request is pending.
3. Reuse the same key when retrying the same request.
4. Treat `201 Created` as a newly created booking.
5. Treat a successful replay response as the result of the original request.
6. Handle `409 Conflict` by waiting and retrying with the same idempotency key when appropriate.
7. Store synchronization cursors while downloading records.
8. Resume synchronization from the last successfully processed cursor after a network interruption.
9. Avoid generating a new idempotency key for a retry of the same logical operation.
10. Handle authentication failures, validation errors, and other non-retryable responses separately from temporary failures.

---

## 17. Production Recommendations

For production deployment:

* Use PostgreSQL as the persistent database.
* Use Redis for caching and distributed application components.
* Monitor API response times.
* Monitor database query performance.
* Monitor Redis availability.
* Monitor failed idempotent requests.
* Monitor repeated `409 Conflict` responses.
* Log important reliability events without exposing sensitive information.
* Configure appropriate API throttling.
* Monitor Celery worker health.
* Monitor WebSocket and notification infrastructure.
* Periodically review synchronization performance.
* Ensure idempotency records have a documented retention and cleanup policy.
* Verify that database constraints and transaction handling support the required concurrency guarantees.

---

## 18. Demo Flow

The reliability implementation can be demonstrated using the following scenarios.

### Demo 1 — Normal booking

1. Authenticate.
2. Create a booking.
3. Receive `201 Created`.
4. Verify that the booking exists.

### Demo 2 — Duplicate request

1. Send a booking request with an `Idempotency-Key`.
2. Send the same request again with the same key.
3. Confirm that a duplicate booking is not created.
4. Confirm that the stored response is returned.

### Demo 3 — Concurrent request

1. Send multiple requests using the same idempotency key.
2. Confirm that duplicate bookings are not created.
3. Confirm that a concurrent request can receive the in-progress conflict response.

### Demo 4 — Offline synchronization

1. Request the booking list.
2. Store the returned cursor.
3. Simulate a network interruption.
4. Resume using the stored cursor.
5. Continue downloading records without relying on numeric page numbers.

### Demo 5 — Authorization isolation

1. Authenticate as a customer.
2. Verify that only that customer's bookings are visible.
3. Authenticate as a provider.
4. Verify that only bookings assigned to that provider are visible.

---

## 19. Acceptance Criteria

| Requirement                                              | Status                                                                              |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Objective and research notes completed                   | Completed                                                                           |
| Implementation completed in the existing Django project  | Completed                                                                           |
| Positive and negative cases tested                       | Completed                                                                           |
| Automated tests added and passing                        | Completed                                                                           |
| API and reliability documentation prepared               | Completed                                                                           |
| Full `services` regression suite passed                  | Completed — 149 tests                                                               |
| Concurrent idempotency test passed independently         | Completed                                                                           |
| Redis connectivity verified for final regression testing | Completed                                                                           |
| Git changes reviewed and traceable                       | Existing release branch verified; documentation update must be committed if changed |
| Demo-ready and independently explainable                 | Ready for review and demonstration                                                  |

---

## 20. Final Status

The Mobile API Reliability, Offline Sync & Idempotent Requests implementation is functionally complete.

The final automated regression suite passed:

```text
python manage.py test services -v 2

Ran 149 tests in 548.791s

OK
```

Final verification confirms:

* All 149 tests in the `services` suite passed.
* The concurrent idempotency test passed independently.
* Payment journey tests passed.
* Redis connectivity was restored and verified.
* The `release/1.0.0` branch was previously confirmed synchronized with `origin/release/1.0.0`.
* The working tree was previously confirmed clean before the proposed documentation update.

**Documentation and Git note:** The existing release was verified before this document was updated. If this revised document is saved, review `git diff --check` and `git diff -- MOBILE_API_RELIABILITY.md`, then commit and push the documentation change if you want it included in the release branch.

The reliability implementation and its test evidence are ready for review and demonstration.
