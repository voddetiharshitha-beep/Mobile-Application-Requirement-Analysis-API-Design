# WebSocket Event Contract

## 1. Overview

The Mobile Application Backend provides real-time booking updates through WebSockets using Django Channels.

WebSocket connections allow authenticated customers and providers to receive booking status changes without repeatedly polling the REST API.

### WebSocket Endpoint

```text
ws://<host>/ws/bookings/<booking_id>/
```

For HTTPS deployments, the WebSocket endpoint should use:

```text
wss://<host>/ws/bookings/<booking_id>/
```

### Current Implementation

The WebSocket endpoint is handled by:

```text
services/consumers.py
```

using:

```text
BookingStatusConsumer
```

The WebSocket route is defined in:

```text
services/routing.py
```

---

# 2. Authentication

WebSocket connections require an authenticated Django user.

The consumer checks:

1. A user exists in the WebSocket scope.
2. The user is authenticated.
3. The user is authorized to access the requested booking.

Unauthenticated users are rejected.

Unauthorized users who are authenticated but do not belong to the booking are also rejected.

### Close Codes

| Close Code | Meaning                                      |
| ---------- | -------------------------------------------- |
| `4001`     | Authentication required                      |
| `4003`     | User is not authorized to access the booking |

---

# 3. Booking Access Rules

A WebSocket connection is allowed when the authenticated user is one of the following:

* The customer who owns the booking.
* The provider assigned to the booking.

Other authenticated users cannot subscribe to the booking's WebSocket channel.

---

# 4. Event Naming Convention

Events use a dot-separated naming convention.

Current events:

```text
connection.established
booking.status_changed
heartbeat.ping
heartbeat.pong
```

The event name is provided in the JSON `event` field.

---

# 5. Event: connection.established

## Direction

Server → Client

## Purpose

Confirms that the WebSocket connection has been successfully authenticated, authorized, and established.

## Payload

```json
{
  "event": "connection.established",
  "booking_id": "uuid",
  "status": "connected",
  "message": "Real-time booking status connected."
}
```

## Fields

| Field        | Type   | Description                       |
| ------------ | ------ | --------------------------------- |
| `event`      | string | Event name                        |
| `booking_id` | string | UUID of the booking               |
| `status`     | string | Connection status                 |
| `message`    | string | Human-readable connection message |

## Example

```json
{
  "event": "connection.established",
  "booking_id": "7c8d9e10-1234-4567-8901-abcdef123456",
  "status": "connected",
  "message": "Real-time booking status connected."
}
```

---

# 6. Event: booking.status_changed

## Direction

Server → Client

## Purpose

Notifies connected clients that the booking status has changed.

This event is published when the booking status changes through the booking or payment workflow.

## Payload

```json
{
  "event": "booking.status_changed",
  "booking_id": "uuid",
  "status": "confirmed",
  "message": "Booking status changed to confirmed."
}
```

## Fields

| Field        | Type   | Description                   |
| ------------ | ------ | ----------------------------- |
| `event`      | string | Event name                    |
| `booking_id` | string | UUID of the booking           |
| `status`     | string | New booking status            |
| `message`    | string | Human-readable status message |

## Example

```json
{
  "event": "booking.status_changed",
  "booking_id": "7c8d9e10-1234-4567-8901-abcdef123456",
  "status": "confirmed",
  "message": "Booking status changed to confirmed."
}
```

---

# 7. Booking Status Values

The booking model currently supports the following status values:

| Status           | Meaning                                           |
| ---------------- | ------------------------------------------------- |
| `pending`        | Booking has been created but is not yet confirmed |
| `confirmed`      | Booking has been confirmed                        |
| `in_progress`    | Provider has started the service                  |
| `completed`      | Service has been completed                        |
| `cancelled`      | Booking has been cancelled                        |
| `payment_failed` | Payment processing failed                         |

The `booking.status_changed` event uses the new value of the booking status.

For example:

```json
{
  "event": "booking.status_changed",
  "booking_id": "7c8d9e10-1234-4567-8901-abcdef123456",
  "status": "cancelled",
  "message": "Booking status changed to cancelled."
}
```

---

# 8. Event: heartbeat.ping

## Direction

Client → Server

## Purpose

Allows the client to confirm that the WebSocket connection is still active.

## Payload

```json
{
  "event": "heartbeat.ping"
}
```

The server recognizes this event and responds with `heartbeat.pong`.

---

# 9. Event: heartbeat.pong

## Direction

Server → Client

## Purpose

Confirms that the server received the heartbeat request and the WebSocket connection is active.

## Payload

```json
{
  "event": "heartbeat.pong",
  "booking_id": "uuid",
  "status": "connected"
}
```

## Example

Client sends:

```json
{
  "event": "heartbeat.ping"
}
```

Server responds:

```json
{
  "event": "heartbeat.pong",
  "booking_id": "7c8d9e10-1234-4567-8901-abcdef123456",
  "status": "connected"
}
```

---

# 10. Multiple Device Support

A user may connect to the same booking from multiple devices.

For example:

```text
Customer Phone
      |
      | WebSocket
      |
      +---- booking_123
      |
      | WebSocket
      |
Customer Tablet
```

Both connections subscribe to the same booking channel.

When a booking status changes, the event is broadcast to the booking group.

Therefore, both connected devices receive the same status event.

Example:

```json
{
  "event": "booking.status_changed",
  "booking_id": "7c8d9e10-1234-4567-8901-abcdef123456",
  "status": "confirmed",
  "message": "Booking status changed to confirmed."
}
```

This allows multiple active devices to remain synchronized.

---

# 11. Presence Tracking

The WebSocket consumer tracks active connections for authenticated users using Redis-backed cache storage.

The presence key follows this pattern:

```text
websocket_presence:<user_id>
```

The value represents the number of active WebSocket connections for the user.

For example:

```text
websocket_presence:25 = 2
```

means that user `25` currently has two active WebSocket connections.

When a connection is established:

```text
connection count + 1
```

When a connection is disconnected:

```text
connection count - 1
```

When the count reaches zero, the presence key is removed.

This supports multiple-device connections without treating one device disconnecting as the user going completely offline.

---

# 12. Disconnect Handling

When a WebSocket disconnects, the consumer:

1. Removes the connection from the booking channel group.
2. Decreases the user's active WebSocket connection count.
3. Deletes the presence key when no active connections remain.

This prevents stale connections from remaining subscribed to booking events.

---

# 13. Reconnection Behavior

Mobile applications may temporarily lose network connectivity.

A client should therefore support reconnecting to the same booking WebSocket endpoint.

Example:

```text
Connected
   |
Network lost
   |
Disconnected
   |
Reconnect
   |
Authentication + authorization
   |
Connected again
```

After reconnecting successfully, the client receives:

```json
{
  "event": "connection.established",
  "booking_id": "uuid",
  "status": "connected",
  "message": "Real-time booking status connected."
}
```

The client can then continue receiving future booking events.

The REST API remains the authoritative source for the current booking state. A mobile client should refresh the booking through the REST API after reconnecting if it needs to recover any events that may have occurred while disconnected.

---

# 14. Duplicate Event Handling

A single booking status transition produces one WebSocket status event from the corresponding status update operation.

For example:

```text
pending
   |
   | one transition
   v
confirmed
```

produces one:

```text
booking.status_changed
```

event.

The WebSocket layer does not use client-generated event IDs for deduplication.

Therefore, clients should treat the booking state from the REST API as authoritative when recovering from network interruptions.

---

# 15. Booking Cancellation

Cancellation uses the same standard booking status event.

Example:

```json
{
  "event": "booking.status_changed",
  "booking_id": "7c8d9e10-1234-4567-8901-abcdef123456",
  "status": "cancelled",
  "message": "Booking status changed to cancelled."
}
```

A separate `booking.cancelled` event is not currently emitted by the WebSocket implementation.

---

# 16. Payment Success

Successful payment confirmation also updates the booking status and broadcasts the standard booking status event.

Example:

```json
{
  "event": "booking.status_changed",
  "booking_id": "7c8d9e10-1234-4567-8901-abcdef123456",
  "status": "confirmed",
  "message": "Booking status changed to confirmed."
}
```

A separate `payment.succeeded` WebSocket event is not currently emitted.

Payment-specific information continues to be handled by the payment REST API and notification system.

---

# 17. Celery Notification Integration

Booking status changes can trigger asynchronous notification processing through Celery.

The architecture separates:

```text
Booking workflow
       |
       +---- WebSocket event
       |
       +---- Celery notification
```

The WebSocket event provides real-time information to currently connected clients.

Celery handles asynchronous notification creation and processing.

This prevents the WebSocket connection from being responsible for persistent notification processing.

---

# 18. Event Flow

The general booking status update flow is:

```text
Mobile Client
      |
      | REST API request
      v
Django Booking Service
      |
      +----------------------+
      |                      |
      v                      v
Database Update         WebSocket Group
                             |
                             v
                       Connected Devices
                             |
                             v
                    booking.status_changed
```

When an asynchronous notification is also required:

```text
Django Booking Service
      |
      +----------------------+
      |                      |
      v                      v
WebSocket Event          Celery Task
                             |
                             v
                       Notification
                             |
                             v
                         Database
```

---

# 19. Client Event Handling

A mobile client should inspect the `event` field before processing a WebSocket message.

Example:

```text
if event == "connection.established":
    mark_socket_connected()

if event == "booking.status_changed":
    update_booking_status()

if event == "heartbeat.pong":
    update_connection_health()
```

Unknown events should not cause the client to crash.

A recommended client behavior is:

```text
Receive message
      |
      v
Read event
      |
      +---- Known event ----> Process event
      |
      +---- Unknown event --> Ignore/log safely
```

---

# 20. Current Event Contract Summary

| Event                    | Direction       | Implemented | Purpose                                                 |
| ------------------------ | --------------- | ----------: | ------------------------------------------------------- |
| `connection.established` | Server → Client |         Yes | Confirms WebSocket connection                           |
| `booking.status_changed` | Server → Client |         Yes | Sends booking status changes                            |
| `heartbeat.ping`         | Client → Server |         Yes | Checks connection health                                |
| `heartbeat.pong`         | Server → Client |         Yes | Responds to heartbeat                                   |
| `booking.cancelled`      | Server → Client |          No | Covered by `booking.status_changed`                     |
| `payment.succeeded`      | Server → Client |          No | Payment success is represented by booking status change |
| `notification.created`   | Server → Client |          No | Notifications are handled separately                    |
| `presence.connected`     | Server → Client |          No | Presence is tracked internally                          |

Only events marked **Implemented: Yes** are part of the current WebSocket API contract.

---

# 21. Reliability Requirements

The WebSocket implementation is designed to support:

* Authenticated connections.
* Booking-level authorization.
* Multiple devices per user.
* Redis-backed connection presence.
* Heartbeat messages.
* Clean disconnect handling.
* Booking status broadcasts.
* Reconnection.
* Single-event verification for a single status transition.
* Integration with Celery notification processing.

The WebSocket system complements the REST API rather than replacing it.

The REST API remains the authoritative source for persistent booking state.

---

# 22. Testing

The WebSocket behavior is covered by:

```text
services/tests/test_websocket.py
```

The test suite verifies:

* Customer connection.
* Provider connection.
* Booking event delivery.
* Unauthorized access rejection.
* Anonymous access rejection.
* Booking status broadcasts.
* Cancellation broadcasts.
* Payment-success broadcasts.
* Heartbeat ping/pong.
* Celery notification integration.
* Multiple-device event delivery.
* Disconnect and reconnect behavior.
* Duplicate-event protection for a single status transition.

The WebSocket test suite currently contains 13 tests.

---

# 23. Future Extensions

The following events may be introduced in future versions if the mobile application requires more granular real-time events:

```text
booking.created
booking.cancelled
payment.succeeded
payment.failed
notification.created
presence.connected
presence.disconnected
```

If these events are introduced, their payload contracts should be versioned and documented before being released to mobile clients.

---

# 24. Versioning

The current WebSocket contract is associated with the API version:

```text
v1
```

Future breaking changes should use an explicit versioning strategy rather than silently changing existing payload fields.

For example:

```text
/ws/v1/bookings/<booking_id>/
```

could be introduced for a future version if required.

Existing clients should continue to receive the currently documented event structure until a compatible migration strategy is provided.

---

# 25. Summary

The WebSocket architecture provides a reliable real-time communication layer for booking updates.

The current implementation provides:

```text
Authentication
      +
Authorization
      +
Presence Tracking
      +
Heartbeat
      +
Booking Status Events
      +
Multiple Device Support
      +
Reconnect Support
      +
Celery Notification Integration
```

The primary real-time event is:

```text
booking.status_changed
```

The REST API remains the source of truth for persistent booking state, while WebSockets provide immediate updates to connected mobile clients.
