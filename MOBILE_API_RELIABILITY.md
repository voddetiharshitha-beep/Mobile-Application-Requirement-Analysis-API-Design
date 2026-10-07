# Mobile API Reliability, Offline Sync & Idempotent Requests

## 1. Objective

This document describes the reliability improvements implemented for the mobile application backend.

The goal is to provide reliable API behavior when mobile clients experience:

* unstable network connections
* request retries
* duplicate requests
* interrupted synchronization
* changing datasets
* concurrent requests
* temporary request failures

The implementation focuses on booking APIs and mobile synchronization requirements while preserving authorization and API consistency.

---

## 2. Reliability Features Implemented

The backend now provides:

* cursor-based pagination
* stable synchronization ordering
* idempotent booking creation
* duplicate-request protection
* concurrent-request protection
* failed-request retry support
* customer booking isolation
* provider booking isolation
* database-backed idempotency records
* consistent API responses

---

## 3. Offline Synchronization

Mobile clients may lose connectivity while downloading or synchronizing records.

The backend uses cursor pagination for synchronization-oriented endpoints.

Implementation:

`services/sync_pagination.py`

```python
from rest_framework.pagination import CursorPagination


class SyncCursorPagination(CursorPagination):
    """
    Cursor pagination for mobile synchronization endpoints.

    Provides stable pagination for datasets that may change
    while the mobile client is downloading records.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    ordering = "-updated_at"
```

### Pagination behavior

The synchronization pagination uses:

* default page size: 20 records
* maximum page size: 100 records
* ordering: `-updated_at`
* cursor-based navigation

Cursor pagination returns:

```json
{
    "next": "...",
    "previous": null,
    "results": []
}
```

The mobile client should store the `next` cursor and use it to continue synchronization.

This avoids relying on numeric page numbers that may become unstable when records are added or updated during synchronization.

---

## 4. Idempotent Booking Requests

Mobile applications may send the same request more than once because of:

* network timeouts
* connection interruptions
* user retry actions
* client-side retries
* duplicate button presses
* concurrent requests

Booking creation therefore supports the `Idempotency-Key` request header.

Example:

```http
POST /api/v1/bookings/
Idempotency-Key: mobile-booking-request-12345
Authorization: Bearer <access-token>
Content-Type: application/json
```

The same idempotency key should be reused when the mobile client retries the same logical request.

---

## 5. Idempotency Request Flow

The booking API follows this sequence:

1. Receive the booking request.
2. Read the `Idempotency-Key`.
3. Check whether the request has already been processed.
4. If the request is already completed, return the stored response.
5. If another request is currently processing the same key, return a conflict response.
6. If a previous attempt failed, allow the request to be retried.
7. Otherwise process the booking.
8. Store the final response against the idempotency record.

This prevents duplicate booking creation during mobile retries.

---

## 6. Idempotency States

The idempotency system uses the following states:

### PROCESSING

The request is currently being processed.

A duplicate request receives:

```http
409 Conflict
```

with an error indicating that the request is already being processed.

### COMPLETED

The original request successfully completed.

A retry using the same idempotency key returns the stored response instead of creating another booking.

### FAILED

The previous attempt failed.

The same idempotency key can be retried after the failed state is reset to processing.

This allows temporary failures to recover without requiring the mobile application to generate a different request identity.

---

## 7. Duplicate Request Protection

Duplicate requests using the same idempotency key do not create multiple bookings.

The idempotency record stores information about the request and its resulting response.

This provides protection against mobile retry behavior and repeated submissions.

The original successful response is returned for subsequent requests using the same completed idempotency key.

---

## 8. Concurrent Request Protection

The backend also handles concurrent requests using the same idempotency key.

If one request is already processing, another request using the same key does not create another booking.

The second request receives:

```http
409 Conflict
```

and the client can retry using the same idempotency key.

This is particularly important for mobile applications where multiple network operations can overlap.

---

## 9. Validation and Idempotency Ordering

The idempotency check is performed before serializer validation for an existing idempotency key.

This is important for mobile retries.

For example, the original request may have successfully created a booking but the mobile client may not have received the response because of a network interruption.

A retry should return the original stored response instead of being rejected because the booking slot is no longer available.

Therefore the implementation checks the idempotency record before executing normal booking validation and creation logic.

---

## 10. Authorization and Data Isolation

Reliability improvements must not bypass authorization.

Customer and provider booking visibility remains isolated.

### Customer

A customer can only list bookings belonging to that customer.

### Provider

A provider can only list bookings assigned to that provider account.

The booking list implementation uses the authenticated user's role and ownership to restrict the queryset.

This prevents synchronization endpoints from exposing another user's booking information.

---

## 11. API Response Consistency

Successful booking creation returns a response containing:

```json
{
    "success": true,
    "message": "Booking created successfully.",
    "data": {}
}
```

When an already-completed idempotent request is retried, the previously stored response is returned.

This allows the mobile application to treat retries consistently.

---

## 12. Automated Testing

The reliability implementation was tested using the Django automated test suite.

The tests cover:

* successful booking creation
* duplicate idempotency requests
* concurrent idempotency requests
* failed-request retry
* completed-request replay
* customer booking isolation
* provider booking isolation
* cursor pagination behavior
* invalid requests
* authorization behavior
* booking workflow behavior
* payment behavior
* notification behavior
* API throttling
* input validation

---

## 13. Regression Testing

During the final regression run, two issues were identified and corrected.

### Provider booking visibility

The booking list initially filtered all users by `customer`.

The queryset was corrected so providers can see bookings assigned to their own provider account.

### Cursor pagination response

The synchronization pagination uses DRF `CursorPagination`.

Cursor pagination does not provide a `count` field in the response.

The affected test was therefore corrected to validate the `results` collection instead.

---

## 14. Final Test Result

The complete `services` test suite was executed with:

```powershell
python manage.py test services -v 2
```

Final result:

```text
Ran 136 tests

OK
```

Therefore:

* 136 tests passed
* 0 failures
* 0 errors

The final regression suite confirms that the reliability changes did not break the existing services functionality.

---

## 15. Test Database Reliability

During final testing, PostgreSQL temporarily retained the Django test database because active database sessions were present.

The active test database sessions were checked using PostgreSQL system views.

After confirming that no active sessions remained, the temporary test database was safely removed.

The production/development database was not deleted.

This ensured that the test environment was clean without affecting the application's real database.

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
8. Resume synchronization from the last successful cursor after a network interruption.
9. Avoid generating a new idempotency key for a retry of the same logical operation.

---

## 17. Production Recommendations

For production deployment:

* use PostgreSQL as the persistent database
* use Redis for cache and distributed application components
* monitor API response times
* monitor database query performance
* monitor Redis availability
* monitor failed idempotent requests
* monitor repeated `409 Conflict` responses
* log important reliability events without exposing sensitive information
* configure appropriate API throttling
* monitor Celery worker health
* monitor WebSocket/notification infrastructure
* periodically review synchronization performance

---

## 18. Demo Flow

The reliability implementation can be demonstrated using the following flow:

### Demo 1 — Normal booking

1. Authenticate.
2. Create a booking.
3. Receive `201 Created`.
4. Verify the booking exists.

### Demo 2 — Duplicate request

1. Send a booking request with an `Idempotency-Key`.
2. Send the same request again with the same key.
3. Confirm that a duplicate booking is not created.
4. Confirm that the stored response is returned.

### Demo 3 — Concurrent request

1. Send multiple requests using the same idempotency key.
2. Confirm that only one request creates the booking.
3. Confirm that another request receives the in-progress conflict response.

### Demo 4 — Offline synchronization

1. Request the booking list.
2. Store the returned cursor.
3. Simulate a network interruption.
4. Resume using the stored cursor.
5. Continue downloading records without relying on numeric page numbers.

### Demo 5 — Authorization isolation

1. Authenticate as a customer.
2. Verify only that customer's bookings are visible.
3. Authenticate as a provider.
4. Verify only bookings assigned to that provider are visible.

---

## 19. Acceptance Criteria

| Requirement                                         | Status                                 |
| --------------------------------------------------- | -------------------------------------- |
| Objective and research notes completed              | Completed                              |
| Implementation completed in existing Django project | Completed                              |
| Positive and negative cases tested                  | Completed                              |
| Automated tests added and passing                   | Completed                              |
| API/reliability documentation updated               | Completed                              |
| Git changes reviewed and traceable                  | Pending final commit                   |
| Demo-ready and independently explainable            | Completed after final Git verification |

---

## 20. Final Status

The Mobile API Reliability, Offline Sync & Idempotent Requests implementation is functionally complete.

The final automated regression suite passed:

```text
136 tests passed
0 failures
0 errors
```

The remaining project step is final Git verification and creation of a clear, traceable commit.
