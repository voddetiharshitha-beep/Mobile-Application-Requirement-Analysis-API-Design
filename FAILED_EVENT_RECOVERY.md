# Failed Event Recovery Procedure

## 1. Purpose

This document explains how to investigate and safely recover failed notification tasks in the mobile backend.

The current implementation uses Celery tasks with bounded retries for selected database connection errors. This procedure provides a manual recovery path when a task still fails.

This is a manual recovery process, not an automated dead-letter queue. Recovery depends on available Celery worker logs, the configured result backend when task results are retained, and related booking, service, and notification records.

## 2. Notification Tasks Covered

The notification tasks covered by this procedure are:

- `services.tasks.create_notification`
- `services.tasks.notify_saved_customers_service_unavailable`

Both tasks use bounded retries with exponential backoff and jitter for selected database connection errors. Both use `get_or_create()` to reduce duplicate notification records.

## 3. When to Start Recovery

Start this procedure when:

- A notification task fails after its retries are exhausted.
- A notification task could not be queued because the broker was unavailable.
- A notification is expected but its database record is missing.
- An operator needs to replay a notification task after correcting a failure.

Do not assume a task failed permanently only because an API request timed out. Check task state where available, worker logs, application logs, and database records first.

If a broker failure occurs before a task is queued, a Celery task ID might not exist. Use application logs and related business records to investigate the failed enqueue operation.

## 4. Recovery Steps

### Step 1: Identify the failure

Inspect Celery worker logs, application logs, and the configured Celery result backend where task results are retained.

Record the following information when available:

- Task name and Celery task ID
- Booking ID or service ID
- Notification type
- Correlation ID
- Exception message
- Number of retry attempts
- Final task state

Do not include passwords, access tokens, payment secrets, or unnecessary personal information in incident notes.

### Step 2: Correct the underlying problem

Determine why the task failed before replaying it.

Examples:

- If PostgreSQL is unavailable, restore database connectivity.
- If Redis or the Celery broker is unavailable, restore the required service and verify connectivity.
- If task arguments or referenced records are invalid, correct the underlying data or application issue first.

Do not repeatedly replay a task while the underlying problem remains.

### Step 3: Check whether the notification already exists

Open a Django shell:

```powershell
python manage.py shell
```

For a booking notification, substitute the actual values:

```python
from services.models import Notification

Notification.objects.filter(
    recipient_id=RECIPIENT_ID,
    booking_id=BOOKING_ID,
    notification_type="BOOKING_CREATED",
).exists()
```

If the result is `True`, inspect the existing notification before replaying the task. The operation might have succeeded even if the worker did not report successful completion.

For a saved-service notification, check the recipient, service, and type:

```python
Notification.objects.filter(
    recipient_id=RECIPIENT_ID,
    service_id=SERVICE_ID,
    notification_type="SAVED_SERVICE_UNAVAILABLE",
).exists()
```

Replace placeholder IDs with actual values. Do not paste placeholder names unchanged into the shell.

### Step 4: Replay the task safely

Replay a task only after verifying the original operation and correcting the underlying failure.

For a booking notification, use the actual recipient ID, booking ID, notification type, message, and correlation ID where available:

```python
from services.tasks import create_notification

result = create_notification.apply_async(
    args=[
        RECIPIENT_ID,
        BOOKING_ID,
        "BOOKING_CREATED",
        "Your booking has been created successfully.",
    ],
    kwargs={
        "correlation_id": "ORIGINAL_CORRELATION_ID",
    },
)

print(result.id)
```

For a saved-service-unavailable notification:

```python
from services.tasks import notify_saved_customers_service_unavailable

result = notify_saved_customers_service_unavailable.apply_async(
    args=[SERVICE_ID],
    kwargs={
        "correlation_id": "ORIGINAL_CORRELATION_ID",
    },
)

print(result.id)
```

Replace every placeholder with verified values from the original workflow. Preserve the original correlation ID when available. If it cannot be recovered, use a clearly documented recovery correlation ID instead.

These commands enqueue work; they do not prove the task succeeded. Inspect worker logs, task state where available, and resulting database records after replay.

### Step 5: Verify the result

Verify that:

- The Celery worker processed the task successfully.
- The expected notification record exists.
- Replaying the same logical notification did not create an additional database record.
- Relevant task logs include the task outcome and correlation ID where available.

Record the recovery outcome in the project's incident or operational notes.

## 5. Duplicate Protection

The notification tasks use `get_or_create()`, and the Notification model has database uniqueness constraints for booking and service notifications.

These controls help prevent duplicate database records when a logical notification is processed repeatedly. They do not guarantee successful delivery to an external push notification provider.

Verify the relevant uniqueness constraint before replaying a task with different recipient, booking, service, or notification-type values.

## 6. Recovery Limitations

The current procedure is a manual recovery path, not an automated dead-letter queue.

It depends on sufficient logs and business records to reconstruct the correct task arguments. If the original operation cannot be identified confidently, do not guess the task arguments or replay it blindly.

A future dead-letter queue or persistent failed-event store could retain the task ID, correlation ID, failure reason, retry count, and recovery status. Store only the information needed for recovery and protect sensitive data appropriately.

A broker failure before task submission and a task failure after execution begins are different situations. The recovery procedure must account for both.

## 7. Verification Checklist

- [ ] Failure reason identified from logs and related records.
- [ ] Underlying infrastructure or data problem corrected.
- [ ] Existing notification checked before replay.
- [ ] Original task arguments and correlation ID verified.
- [ ] Replay result checked in worker logs and the database.
- [ ] Duplicate notification records ruled out.
- [ ] Recovery outcome documented.