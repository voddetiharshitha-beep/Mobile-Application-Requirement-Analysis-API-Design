# API Reliability Documentation

## Mobile API Reliability, Offline Sync & Idempotent Requests

---

## 1. API Overview

The Mobile Application Backend provides REST APIs for authentication, services, bookings, payments, notifications, and mobile synchronization.

Base API URL:

```text
/api/v1/
```

Authentication uses JWT Bearer tokens.

Example:

```http
Authorization: Bearer <access_token>
```

The reliability implementation focuses on:

* reliable booking creation
* duplicate request prevention
* idempotent requests
* retry-safe mobile requests
* concurrent request protection
* cursor-based synchronization
* customer/provider data isolation
* consistent API responses

---

# 2. Authentication

## 2.1 Login

### Endpoint

```http
POST /api/v1/token/
```

### Headers

```http
Content-Type: application/json
```

### Request

```json
{
    "username": "customer_username",
    "password": "your_password"
}
```

### Successful Response

```http
200 OK
```

Example:

```json
{
    "access": "<access_token>",
    "refresh": "<refresh_token>"
}
```

The access token must be included in protected API requests.

---

## 2.2 Refresh Token

### Endpoint

```http
POST /api/v1/token/refresh/
```

### Request

```json
{
    "refresh": "<refresh_token>"
}
```

### Successful Response

```http
200 OK
```

Example:

```json
{
    "access": "<new_access_token>"
}
```

---

# 3. Booking APIs

Bookings are the primary APIs covered by the reliability and idempotency implementation.

---

## 3.1 List Bookings

### Endpoint

```http
GET /api/v1/bookings/
```

### Authentication

Required.

```http
Authorization: Bearer <access_token>
```

### Customer behavior

Customers receive only their own bookings.

### Provider behavior

Providers receive only bookings assigned to their provider account.

This prevents users from accessing another user's booking information.

---

## 3.2 Cursor Pagination

The booking list uses cursor-based pagination for reliable mobile synchronization.

Example:

```http
GET /api/v1/bookings/
Authorization: Bearer <access_token>
```

The API returns:

```json
{
    "next": "<next_cursor_url>",
    "previous": null,
    "results": []
}
```

The mobile application should store the `next` cursor and use it to continue synchronization.

### Pagination configuration

```text
Default page size: 20
Maximum page size: 100
Ordering: -updated_at
```

Cursor pagination is preferred over numeric page numbers because records can be created or updated while synchronization is in progress.

---

# 4. Create Booking

## 4.1 Endpoint

```http
POST /api/v1/bookings/
```

### Authentication

Required.

```http
Authorization: Bearer <access_token>
```

### Content Type

```http
Content-Type: application/json
```

---

## 4.2 Idempotency Header

The mobile client should send an idempotency key:

```http
Idempotency-Key: <unique-request-key>
```

Example:

```http
Idempotency-Key: booking-request-12345
```

The key identifies one logical booking operation.

If the mobile client retries because of a network failure, it must reuse the **same idempotency key**.

It must not generate a new key for the same logical request.

---

## 4.3 Request Example

```http
POST /api/v1/bookings/
Authorization: Bearer <access_token>
Content-Type: application/json
Idempotency-Key: booking-request-12345
```

Example body:

```json
{
    "service": "<service_uuid>",
    "booking_date": "2026-10-10",
    "booking_time": "10:00:00"
}
```

---

# 5. Successful Booking Creation

When the booking is created for the first time:

```http
201 Created
```

Example response:

```json
{
    "success": true,
    "message": "Booking created successfully.",
    "data": {
        "id": "<booking_uuid>",
        "customer": "<customer_id>",
        "provider": "<provider_id>",
        "service": "<service_uuid>",
        "booking_date": "2026-10-10",
        "booking_time": "10:00:00",
        "amount": "500.00",
        "status": "pending"
    }
}
```

The actual response fields are determined by the booking serializer.

---

# 6. Duplicate Booking Request

A mobile application may send the same request more than once because of:

* poor network connectivity
* request timeout
* application retry
* duplicate button press
* connection interruption

The client should resend the same:

```http
Idempotency-Key
```

The backend detects the existing idempotency record.

If the original request has already completed, the backend returns the stored response instead of creating another booking.

Example:

```http
200 OK
```

Example:

```json
{
    "success": true,
    "message": "Booking created successfully.",
    "data": {
        "id": "<original_booking_uuid>"
    }
}
```

The important behavior is:

```text
One Idempotency-Key
        ↓
One logical booking
        ↓
Repeated requests do not create duplicates
```

---

# 7. Concurrent Requests

Multiple requests using the same idempotency key may arrive at approximately the same time.

Example:

```text
Request A ───────→ PROCESSING
Request B ───────→ same Idempotency-Key
Request C ───────→ same Idempotency-Key
```

While the first request is being processed, subsequent requests are rejected as in-progress requests.

### Response

```http
409 Conflict
```

Example:

```json
{
    "success": false,
    "message": "This booking request is already being processed. Please retry using the same Idempotency-Key.",
    "error_code": "IDEMPOTENCY_IN_PROGRESS"
}
```

The mobile application should retry using the **same idempotency key**.

---

# 8. Idempotency States

The idempotency mechanism supports three important states.

## PROCESSING

The request is currently being processed.

A duplicate request receives:

```http
409 Conflict
```

---

## COMPLETED

The request completed successfully.

A repeated request receives the stored response.

A second booking is not created.

---

## FAILED

The previous attempt failed.

The idempotency record can be returned to processing so that the mobile application can retry the same logical operation.

---

# 9. Idempotency Flow

The complete booking flow is:

```text
Mobile Client
     |
     | POST /bookings/
     | Idempotency-Key
     v
Check Idempotency Record
     |
     +---- COMPLETED ----> Return stored response
     |
     +---- PROCESSING ---> 409 Conflict
     |
     +---- FAILED -------> Allow retry
     |
     +---- NEW ----------> Process booking
                              |
                              v
                         Create Booking
                              |
                              v
                      Store API Response
                              |
                              v
                           COMPLETED
```

---

# 10. Booking Detail

### Endpoint

```http
GET /api/v1/bookings/<booking_id>/
```

### Authentication

Required.

```http
Authorization: Bearer <access_token>
```

The authenticated user must have permission to access the booking.

---

# 11. Cancel Booking

### Endpoint

```http
POST /api/v1/bookings/cancel/
```

### Authentication

Required.

```http
Authorization: Bearer <access_token>
```

The request must contain the booking information expected by the current booking cancellation serializer/view.

The cancellation operation must respect booking ownership and allowed booking state transitions.

---

# 12. Booking Status

### Endpoint

```http
POST /api/v1/bookings/status/
```

### Authentication

Required.

```http
Authorization: Bearer <access_token>
```

Booking status changes must respect the application's booking workflow.

Supported booking states include:

```text
pending
confirmed
in_progress
completed
cancelled
payment_failed
```

Invalid status transitions must be rejected by the backend.

---

# 13. Error Handling

The API uses HTTP status codes to communicate request results.

Common responses include:

| Status                      | Meaning                                            |
| --------------------------- | -------------------------------------------------- |
| `200 OK`                    | Successful request or successful idempotent replay |
| `201 Created`               | New booking/resource created                       |
| `400 Bad Request`           | Invalid request data                               |
| `401 Unauthorized`          | Authentication required/invalid                    |
| `403 Forbidden`             | User does not have permission                      |
| `404 Not Found`             | Resource does not exist or is unavailable          |
| `409 Conflict`              | Idempotent request is currently processing         |
| `429 Too Many Requests`     | API rate limit exceeded                            |
| `500 Internal Server Error` | Unexpected server error                            |

---

# 14. Authentication and Authorization

Protected endpoints require:

```http
Authorization: Bearer <access_token>
```

The backend enforces ownership rules.

### Customer

A customer can access their own bookings.

### Provider

A provider can access bookings assigned to their provider account.

This authorization must remain active during synchronization and retry operations.

Idempotency does not bypass authorization.

---

# 15. Offline Synchronization

Mobile applications may lose network connectivity while retrieving booking records.

The client should:

1. Request the first booking page.
2. Store the returned cursor.
3. Process the returned records.
4. Save the synchronization progress.
5. Resume using the stored cursor if connectivity is interrupted.
6. Continue until the API returns no next cursor.

Example:

```text
GET /api/v1/bookings/
        |
        v
Receive results + next cursor
        |
        v
Store cursor
        |
   Network failure
        |
        v
Reconnect
        |
        v
Request stored next cursor
        |
        v
Continue synchronization
```

---

# 16. Synchronization Response

Example:

```json
{
    "next": "https://example.com/api/v1/bookings/?cursor=<cursor>",
    "previous": null,
    "results": [
        {
            "id": "<booking_uuid>",
            "booking_date": "2026-10-10",
            "booking_time": "10:00:00",
            "status": "confirmed"
        }
    ]
}
```

The client should not assume that the response contains a `count` field because cursor pagination provides cursor navigation rather than traditional numbered-page metadata.

---

# 17. Retry Rules for Mobile Clients

## Network timeout

If the client does not receive a response:

```text
Reuse the same Idempotency-Key.
```

Do not create a new logical booking request.

---

## 409 Conflict

If the API returns:

```http
409 Conflict
```

the request is currently being processed.

The client should wait and retry using the same idempotency key.

---

## Successful Replay

If the original request has completed, the backend returns the stored result.

The client should treat that response as the result of the original booking operation.

---

## Validation Error

For a genuinely invalid new request, correct the request data before retrying.

---

# 18. Postman Testing

The API can be demonstrated using Postman.

## Test 1 — Login

```http
POST /api/v1/token/
```

Provide valid credentials and copy the returned access token.

---

## Test 2 — Create Booking

Set:

```http
Authorization: Bearer <access_token>
Idempotency-Key: postman-booking-001
Content-Type: application/json
```

Send the booking request.

Expected:

```http
201 Created
```

---

## Test 3 — Repeat Same Request

Send the same request again with:

```http
Idempotency-Key: postman-booking-001
```

Expected:

```http
200 OK
```

The backend must not create another booking.

---

## Test 4 — Concurrent Request

Send multiple requests with the same idempotency key while the original request is processing.

Expected for an in-progress duplicate:

```http
409 Conflict
```

---

## Test 5 — Booking List

```http
GET /api/v1/bookings/
```

Expected:

```http
200 OK
```

Verify that:

* customer sees only their bookings
* provider sees only assigned bookings
* response uses cursor pagination

---

## Test 6 — Pagination

Follow the `next` URL returned by the booking list.

Verify that the next set of results is returned.

---

# 19. Positive Test Cases

The following scenarios should succeed:

| Test                                  | Expected Result                        |
| ------------------------------------- | -------------------------------------- |
| Valid login                           | `200 OK`                               |
| Valid booking                         | `201 Created`                          |
| Retry completed booking with same key | `200 OK`                               |
| Valid booking list                    | `200 OK`                               |
| Valid cursor pagination               | `200 OK`                               |
| Customer views own booking            | Allowed                                |
| Provider views assigned booking       | Allowed                                |
| Failed request retry                  | Allowed according to idempotency state |

---

# 20. Negative Test Cases

The following scenarios should be rejected appropriately:

| Test                                          | Expected Result                          |
| --------------------------------------------- | ---------------------------------------- |
| Missing authentication                        | `401 Unauthorized`                       |
| Invalid authentication                        | `401 Unauthorized`                       |
| Invalid booking data                          | `400 Bad Request`                        |
| Unauthorized booking access                   | `403/404` according to endpoint behavior |
| Duplicate request while processing            | `409 Conflict`                           |
| Excessive requests                            | `429 Too Many Requests`                  |
| Invalid status transition                     | `400`/appropriate validation error       |
| Access to another customer's booking          | Rejected                                 |
| Provider accessing another provider's booking | Rejected                                 |

---

# 21. Automated Test Verification

The final Django services test suite was executed using:

```powershell
python manage.py test services -v 2
```

Final result:

```text
Ran 136 tests

OK
```

Therefore:

```text
136 tests passed
0 failures
0 errors
```

The test suite covers reliability, authorization, booking workflows, payments, notifications, throttling, validation, and idempotency behavior.

---

# 22. Mobile Client Implementation Rules

The mobile client should follow these rules:

1. Generate one idempotency key per logical booking operation.
2. Persist the key while the operation is pending.
3. Reuse the key after network failures.
4. Never generate a new key simply because the first request timed out.
5. Store synchronization cursors.
6. Resume synchronization from the last successful cursor.
7. Handle `409 Conflict` appropriately.
8. Handle authentication failures separately.
9. Never bypass authorization when synchronizing data.
10. Treat the backend response as the source of truth for booking state.

---

# 23. API Reliability Summary

The backend provides protection against common mobile reliability problems:

```text
Network Failure
      |
      v
Retry Request
      |
      v
Same Idempotency-Key
      |
      v
Backend Checks Existing Request
      |
      +---- Completed ----> Return Original Result
      |
      +---- Processing ---> 409 Conflict
      |
      +---- Failed -------> Retry Processing
      |
      +---- New ----------> Create Booking
```

For synchronization:

```text
Request Records
      |
      v
Cursor Pagination
      |
      v
Store Cursor
      |
      v
Network Interruption
      |
      v
Resume With Cursor
      |
      v
Continue Synchronization
```

---

# 24. Final Status

| Acceptance Requirement                | Status    |
| ------------------------------------- | --------- |
| Objective and research notes          | Completed |
| Django implementation                 | Completed |
| Positive cases                        | Completed |
| Negative cases                        | Completed |
| Automated tests                       | Completed |
| Reliability API documentation         | Completed |
| Offline synchronization documentation | Completed |
| Idempotency documentation             | Completed |
| Postman testing procedure             | Completed |
| Final Git verification                | Pending   |
| Final Git commit                      | Pending   |

## Final Verification

The reliability implementation has passed the final services regression suite:

```text
136 tests passed
0 failures
0 errors
```

The API documentation provides the information required to demonstrate the reliability implementation independently.
