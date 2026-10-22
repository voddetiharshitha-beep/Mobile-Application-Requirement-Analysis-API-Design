# Mobile Backend Event Pipeline Reliability

## 1. Purpose

This document defines the event lifecycle, event contracts, validation
rules, API error behavior, correlation identifiers, and failure recovery
expectations for the mobile backend.

The objective is to improve the reliability, traceability, and testability
of booking, payment, and notification workflows.

This document describes the target behavior. Existing implementation
details must be verified against the source code and automated tests
before they are considered implemented.

## 2. System Components

| Component | Responsibility |
|---|---|
| Mobile application | Sends authenticated API requests and displays results |
| Django REST API | Authenticates requests, validates input, and returns responses |
| PostgreSQL | Persists bookings, payments, notifications, and related records |
| Business service layer | Applies booking and payment business rules |
| Celery | Executes supported background tasks |
| Redis | Supports configured caching, task brokering, and Channels communication |
| Django Channels | Delivers authorized real-time WebSocket updates |
| Notification tasks | Create persisted notification records; external delivery must be verified separately |
| Logging and monitoring | Helps trace requests, failures, retries, and outcomes |

The exact responsibility of each component depends on the current
configuration and implementation.

## 3. Mobile Event Lifecycle

### 3.1 Booking workflow

1. The customer submits a booking request from the mobile application.
2. Django authenticates the user and validates the request.
3. The business service applies booking rules.
4. PostgreSQL stores the booking within the appropriate transaction.
5. The backend initiates the required follow-up work.
6. Supported background tasks process notification work.
7. The background task creates a notification record when it succeeds; external push delivery must be verified separately.
8. Authorized WebSocket clients receive booking status updates when published.
9. Logs record relevant outcomes and identifiers for troubleshooting.

A successful database write does not, by itself, guarantee successful
background processing or notification delivery.

### 3.2 Payment workflow

1. The customer initiates payment through the API.
2. The backend validates the request and payment state.
3. The configured payment integration processes or verifies the operation.
4. The backend validates the payment result or webhook.
5. The payment and booking states are updated according to business rules.
6. Relevant notification or real-time update work is initiated.
7. The outcome is logged and made available to authorized clients.

Payment timeouts require reconciliation because the provider may have
processed a payment even when the backend did not receive the response.

### 3.3 WebSocket workflow

1. The mobile client opens the booking WebSocket connection.
2. The backend authenticates the connection and authorizes access to the booking.
3. The consumer joins the permitted booking group.
4. The backend publishes supported status updates.
5. The client receives updates while connected.
6. On disconnection or reconnection, the client can retrieve the latest
   booking state through the authorized API.

WebSocket delivery should not be treated as durable storage. The database
remains the source of truth for booking status.

## 4. Event Contract

### 4.1 Standard event envelope

The following is a proposed event envelope for internal event processing.
It is not a claim that all current tasks already use this format.

Example:

    {
      "event_id": "evt-example-001",
      "event_type": "booking.confirmed",
      "event_version": 1,
      "correlation_id": "corr-example-001",
      "occurred_at": "2026-10-12T10:30:00Z",
      "payload": {
        "booking_id": "booking-uuid",
        "status": "confirmed"
      }
    }

### 4.2 Field definitions

| Field | Requirement | Purpose |
|---|---|---|
| event_id | Required; unique per logical event | Supports duplicate-delivery detection |
| event_type | Required; allowlisted string | Identifies the event's meaning |
| event_version | Required positive integer | Supports controlled schema evolution |
| correlation_id | Required for traceable workflows | Connects related operations |
| occurred_at | Required timestamp in UTC | Records when the event occurred |
| payload | Required object | Contains event-specific data |

A booking event should contain a valid booking identifier and an allowed
booking status. A payment event should contain the appropriate payment
identifier and a recognized payment outcome.

The exact payload schema must be selected for each event type.

### 4.3 Event naming

Use consistent names, such as:

- booking.created
- booking.confirmed
- booking.cancelled
- payment.initiated
- payment.completed
- payment.failed
- notification.requested
- notification.sent
- notification.failed

These names are proposed conventions. Confirm which events actually exist
before documenting them as emitted by the application.

## 5. Validation Rules

Event consumers should validate the following before performing side effects:

1. The event is a valid object with all required fields.
2. The event ID and correlation ID are non-empty and conform to the
   configured identifier format.
3. The event type is supported.
4. The event version is supported.
5. The timestamp is valid and uses the agreed UTC representation.
6. The payload matches the schema for its event type.
7. Referenced booking and payment records exist when required.
8. The requested state transition is permitted by business rules.
9. The authenticated actor is authorized for the operation where applicable.
10. Invalid data is rejected or recorded for investigation instead of
    being retried indefinitely.

Validation must not replace authorization checks or payment verification.

## 6. Event ID, Correlation ID, and Idempotency

### Event ID

Identifies one logical event. Retries of that event must preserve the
same event ID.

Consumers can use a persistent record and a database uniqueness constraint
to detect repeated deliveries. An identifier alone does not prevent
duplicate processing.

### Correlation ID

Connects related work within one request or business workflow.

For example, booking creation, payment processing, and notification
processing may share a correlation ID while having different event IDs.

The correlation ID should be propagated to relevant logs and background
tasks. Incoming correlation IDs must be validated and treated as
untrusted input; they must not be used as authorization credentials.

### Idempotency

An idempotency key identifies a client operation that must not produce
duplicate business effects when safely retried.

Event IDs and idempotency keys serve different purposes and should not
automatically be treated as interchangeable.

## 7. API Error Contract

API errors should use a consistent structure compatible with the
project's existing response conventions.

Illustrative example:

    {
      "error": {
        "code": "VALIDATION_ERROR",
        "message": "The request contains invalid data.",
        "details": {
          "booking_date": ["A valid date is required."]
        },
        "correlation_id": "corr-example-001"
      }
    }

The example defines a target contract, not necessarily the current response format.

The current exception handler returns an error object containing success: false, message, and error_code. The example above would require a separate implementation change.

### Expected HTTP behavior

| Condition | Expected response |
|---|---|
| Malformed or invalid request | 400 Bad Request |
| Missing or invalid authentication | 401 Unauthorized |
| Authenticated user lacks permission | 403 Forbidden, or 404 where resource hiding is intentional |
| Resource does not exist | 404 Not Found |
| Idempotency key conflicts with a different operation | 409 Conflict |
| Rate limit exceeded | 429 Too Many Requests |
| Temporary service failure | Appropriate 5xx response when the request cannot be completed |

Use the existing API conventions and DRF exception handling when
implementing these behaviors. Do not expose secrets, stack traces,
payment credentials, or sensitive personal information in errors.

## 8. Correlation ID Handling

The intended request flow is:

1. Accept a valid incoming correlation ID if the API contract permits it,
   or generate a new unpredictable identifier.
2. Attach the identifier to the request's logging context.
3. Include it in relevant application logs.
4. Propagate it to supported background tasks and event envelopes.
5. Include it in API error responses where appropriate.
6. Reuse it to find related booking, payment, and notification activity.

Do not reuse one global correlation ID across unrelated requests.

The current HTTP middleware uses X-Request-ID for request tracing and adds it to the response and request logs. End-to-end propagation through Celery tasks and WebSocket messages has not yet been verified.

If an incoming identifier is missing or invalid, apply a documented
validation or regeneration policy. Avoid trusting arbitrary header values.

## 9. Failure Scenarios and Recovery

| Failure | Impact | Expected recovery |
|---|---|---|
| Invalid event schema | Event cannot be processed safely | Reject or quarantine; investigate without endless retries |
| PostgreSQL transaction failure | Business operation may not be persisted | Roll back incomplete changes and return an appropriate error |
| Redis unavailable | Cache, broker, or Channels behavior may be affected | Apply a component-specific recovery strategy; do not assume every Redis use has the same fallback |
| Celery task fails temporarily | Background processing is delayed | Retry eligible work with bounded exponential backoff and jitter |
| Celery retries are exhausted | Task remains unsuccessful | Record failure and provide an inspection and recovery procedure |
| Duplicate event delivery | Side effects could occur more than once | Deduplicate using persistent event-processing state and safe transaction boundaries |
| Notification provider timeout | Delivery outcome may be uncertain | Retry transient errors safely and reconcile uncertain outcomes where supported |
| Payment provider timeout | Payment may have succeeded without a received response | Check provider state before retrying an operation that could charge again |
| WebSocket disconnect | Client may miss a real-time update | Reconnect and fetch the latest authorized resource state |
| Invalid state transition | Booking or payment state may become inconsistent | Reject the transition and record relevant diagnostic information |

### Recovery principles

- Retry transient failures, not permanent validation errors.
- Apply bounded attempts, backoff, jitter, and suitable timeouts.
- Preserve the logical event ID when retrying delivery.
- Prevent duplicate business effects through idempotent processing.
- Record exhausted retries and provide a safe replay procedure.
- Do not acknowledge durable work before the required persistence guarantees
  have been satisfied.
- Treat payment uncertainty as a reconciliation problem, not as proof
  that the payment failed.
- Keep the database as the source of truth for persisted business state.

## 10. Logging and Observability Requirements

Relevant logs should include, where applicable:

- correlation_id
- event_id
- event_type
- booking_id or payment_id
- task name and retry attempt
- processing outcome
- error category
- elapsed processing time

Use structured logging where possible. Avoid logging passwords, tokens,
payment secrets, or unnecessary personal information.

Useful operational measurements include task failure count, retry count,
retry exhaustion count, event processing duration, notification delivery
outcomes, and API error rates.

## 11. Day 1 Verification Checklist

Use this checklist when investigating and recovering a failed event or notification task.

- [ ] Failure reason identified from logs and related records.
- [ ] Underlying infrastructure or data problem corrected.
- [ ] Existing notification checked before replay.
- [ ] Original task arguments and correlation ID verified.
- [ ] Replay result checked in worker logs and the database.
- [ ] Duplicate notification records ruled out.
- [ ] Recovery outcome documented.

## 12. Implementation Status

This document defines the event reliability design and verification requirements. It does not, by itself, prove that retries, event deduplication, correlation-ID propagation, dead-letter handling, or all recovery mechanisms have been implemented.

These behaviors must be verified through source-code inspection and automated tests before they are marked complete.

## 13. Failed Event Recovery

The manual notification-task recovery procedure is documented in [FAILED_EVENT_RECOVERY.md](FAILED_EVENT_RECOVERY.md).

It covers failure investigation, duplicate checks, safe task replay, and post-recovery verification.

This is a manual recovery procedure. It must not be described as an automated dead-letter queue unless such a mechanism has been implemented and verified.
## 14. Payment Webhook Idempotency and State Transitions

### Behavior

The payment webhook endpoint validates the configured webhook secret, payment ID, transaction ID, and payment status.

- A valid SUCCESS event transitions the payment to SUCCESS and confirms its booking.
- A valid FAILED event transitions the payment to FAILED.
- A duplicate event with the same status returns HTTP 200 without repeating the payment transition.
- A conflicting event after a final status returns HTTP 409 with error code `PAYMENT_STATUS_CONFLICT`.
- An invalid webhook secret returns HTTP 401.
- Invalid payloads and mismatched transaction IDs are rejected.

### Concurrency and consistency

Payment processing uses a database transaction and `select_for_update()` to recheck the current status before applying a transition.

Notifications and WebSocket updates are scheduled using `transaction.on_commit()` so they are not dispatched for a transaction that rolls back

### Verification

Latest focused verification for the idempotency changes:

- `python manage.py test services.tests.test_idempotency_reliability` — 7 tests passed, including same-key replay, conflicting payload rejection, duplicate requests during processing, retry after failure, expired-key reuse, response-loss retry, and concurrent duplicate requests.
- `python manage.py test services.tests.test_payment_journey` — 9 tests passed, including payment webhook behavior and payment state-transition regression coverage.

The test results above were observed in the local configured test environment. Rerun the commands after further changes. Previously recorded image-upload retry results are separate from this verification.

### Limitations

Idempotency records expire after 24 hours. Expired `COMPLETED` and `FAILED` records may be reused; expired `PROCESSING` records are not automatically reclaimed because the original operation might still be running. Database uniqueness and row locking protect the record-reuse path, subject to the configured database's transaction and locking behavior.

These tests do not prove that all event types are deduplicated through a durable event inbox, that every out-of-order callback is handled, or that external notification providers deliver exactly once. The failed-event recovery procedure remains manual, not an automated dead-letter queue. Payment-provider signature verification and production webhook configuration require separate review.
