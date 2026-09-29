# Core Workflow — Customer Service Booking Lifecycle

## 1. Overview

The primary business workflow of the application is the customer service booking lifecycle.

The workflow allows a customer to search for a service, create a booking, complete a mock payment, receive provider confirmation, track the service in real time, and receive confirmation when the service is completed.

The primary workflow is:

```text
Customer
   ↓
Service Search
   ↓
Booking Created
   ↓
Payment
   ↓
Provider Confirmation
   ↓
Service Started
   ↓
Service Completed
```

---

# 2. Core Workflow Architecture

```text
                    Customer
                       │
                       ↓
                Service Search
                       │
                       ↓
                Create Booking
                       │
                       ↓
                    pending
                       │
                       ↓
                 Mock Payment
                       │
             ┌─────────┴─────────┐
             │                   │
          SUCCESS              FAILED
             │                   │
             ↓                   ↓
        confirmed          payment_failed
             │
             ↓
      Provider Starts Service
             │
             ↓
         in_progress
             │
             ↓
      Provider Completes Service
             │
             ↓
          completed
```

A booking can also be cancelled while it is still eligible for cancellation:

```text
pending
   │
   └────────────→ cancelled
```

---

# 3. Customer

The customer is an authenticated application user who wants to find and book a service.

## Customer Actions

The customer can:

* Register an account
* Log in
* Obtain a JWT access token
* Search services
* Filter and sort services
* View service details
* Select a provider/service
* Create a booking
* Initiate a mock payment
* View booking status
* Receive notifications
* Track booking status through WebSocket
* View booking history

## Authentication

Protected operations require authentication.

The general flow is:

```text
Customer
   ↓
Login
   ↓
Username + Password
   ↓
JWT Authentication
   ↓
Access Token
   ↓
Authenticated API Requests
```

---

# 4. Service Search

The customer searches for an available service before creating a booking.

The service API supports operations such as:

* Service listing
* Search
* Filtering
* Sorting
* Pagination
* Service detail retrieval

Example endpoint:

```text
GET /api/v1/services/
```

The general flow is:

```text
Customer
   ↓
Service API
   ↓
Search / Filter / Sort
   ↓
Available Services
   ↓
Customer Selects Service
```

At this stage, a booking has not yet been created.

---

# 5. Booking Creation

After selecting a service, the customer creates a booking.

The booking contains information such as:

* Customer
* Provider
* Service
* Booking date
* Booking time
* Amount
* Booking status

The initial booking state is:

```text
pending
```

The state transition is:

```text
No Booking
    ↓
pending
```

The booking amount is taken from the selected service.

The booking creation operation is handled through the booking service layer.

---

# 6. Booking Created Notification

After a booking is created, the system generates a booking-created notification.

The notification type is:

```text
BOOKING_CREATED
```

Notification processing is handled asynchronously through Celery.

The flow is:

```text
Booking Created
      ↓
Notification Service
      ↓
Celery Task
      ↓
Redis
      ↓
Celery Worker
      ↓
Notification Created
```

This prevents notification processing from unnecessarily blocking the main API request.

---

# 7. Booking State — Pending

Immediately after successful booking creation:

```text
Booking Status = pending
```

The `pending` state means the booking has been created but has not yet reached the confirmed state.

From `pending`, the booking can transition to:

```text
pending
   ├──→ confirmed
   ├──→ cancelled
   └──→ payment_failed
```

A successful payment results in the `confirmed` state.

A cancellation results in the `cancelled` state.

A failed payment can result in the `payment_failed` state.

---

# 8. Payment

The application uses a mock payment workflow.

The customer initiates payment for the booking.

The payment workflow is:

```text
Booking
   ↓
Payment Initiation
   ↓
Payment Created
   ↓
PENDING
   ↓
Mock Payment Processing
```

A payment is associated with a booking.

The payment contains information such as:

* Booking
* Amount
* Transaction ID
* Payment status
* Payment method
* Creation timestamp

The payment method used by this project is:

```text
MOCK
```

---

# 9. Payment States

The payment model supports the following states:

```text
PENDING
SUCCESS
FAILED
REFUNDED
```

The normal successful workflow is:

```text
PENDING
   ↓
SUCCESS
```

A failed payment can result in:

```text
PENDING
   ↓
FAILED
```

The payment status is separate from the booking status.

---

# 10. Successful Payment

When payment succeeds, the booking moves from:

```text
pending
   ↓
confirmed
```

The payment becomes:

```text
SUCCESS
```

The system also performs the following operations:

1. Updates the payment status.
2. Updates the booking status.
3. Sends the booking status update through Django Channels.
4. Creates a payment-successful notification.
5. Creates a booking-confirmed notification.

The flow is:

```text
Payment SUCCESS
      ↓
Booking → confirmed
      ↓
WebSocket Status Update
      ↓
PAYMENT_SUCCESSFUL Notification
      ↓
BOOKING_CONFIRMED Notification
```

---

# 11. Provider Confirmation

After successful payment, the booking reaches:

```text
confirmed
```

This indicates that the booking has been confirmed and can proceed toward service execution.

The normal transition is:

```text
pending
   ↓
confirmed
```

The booking status transition is controlled by the application's booking business logic.

---

# 12. Real-Time Booking Status

The application uses Django Channels and WebSockets to provide real-time booking status updates.

The WebSocket endpoint is:

```text
ws://127.0.0.1:8000/ws/bookings/<booking_id>/
```

The communication flow is:

```text
Booking Status Change
        ↓
Booking Service
        ↓
Django Channels
        ↓
Redis Channel Layer
        ↓
WebSocket Consumer
        ↓
Customer
```

This allows the customer to receive status changes without continuously polling the REST API.

---

# 13. Service Started

When the provider starts the service, the booking changes from:

```text
confirmed
   ↓
in_progress
```

The `in_progress` state indicates that the service is currently being performed.

The system sends a real-time booking status update.

A notification is also generated:

```text
PROVIDER_STARTED
```

The flow is:

```text
Provider Starts Service
        ↓
Booking Status = in_progress
        ↓
Django Channels
        ↓
Customer receives real-time update
        ↓
PROVIDER_STARTED Notification
```

---

# 14. Service Completed

After the provider finishes the service, the booking changes from:

```text
in_progress
   ↓
completed
```

The `completed` state represents the successful end of the primary booking workflow.

The system generates:

```text
BOOKING_COMPLETED
```

notification.

The flow is:

```text
Provider Completes Service
        ↓
Booking Status = completed
        ↓
Django Channels
        ↓
Customer receives status update
        ↓
BOOKING_COMPLETED Notification
```

---

# 15. Complete Booking State Machine

The booking model supports the following status values:

```text
pending
confirmed
in_progress
completed
cancelled
payment_failed
```

The primary successful state transition is:

```text
pending
   ↓
confirmed
   ↓
in_progress
   ↓
completed
```

Alternative states include:

```text
pending
   ↓
cancelled
```

and:

```text
pending
   ↓
payment_failed
```

---

# 16. Valid State Transitions

The application defines controlled booking status transitions.

## From Pending

```text
pending
   ├──→ confirmed
   ├──→ cancelled
   └──→ payment_failed
```

## From Confirmed

```text
confirmed
   └──→ in_progress
```

## From In Progress

```text
in_progress
   └──→ completed
```

## From Completed

```text
completed
   └──→ No further transition
```

## From Cancelled

```text
cancelled
   └──→ No further transition
```

## From Payment Failed

```text
payment_failed
   └──→ No further transition
```

This prevents invalid state changes.

For example:

```text
completed → pending
completed → confirmed
completed → cancelled
```

are not valid transitions.

---

# 17. Notification Flow

Notifications are generated for important workflow events.

The notification types used in the workflow include:

```text
BOOKING_CREATED
PAYMENT_SUCCESSFUL
BOOKING_CONFIRMED
PROVIDER_STARTED
BOOKING_COMPLETED
BOOKING_CANCELLED
```

The notification flow is:

```text
Business Event
      ↓
Notification Service
      ↓
Celery Task
      ↓
Redis
      ↓
Celery Worker
      ↓
Notification
      ↓
Customer
```

---

# 18. Background Processing

Celery is used to process notification creation asynchronously.

The worker is started using:

```powershell
celery -A config worker --loglevel=info --pool=solo
```

The general architecture is:

```text
Django
   ↓
Celery Task
   ↓
Redis
   ↓
Celery Worker
   ↓
Background Processing
```

This keeps background notification processing separate from the main API request handling.

---

# 19. Service Layer

Business operations are separated into service modules.

The relevant service modules include:

```text
services/
├── booking_service.py
├── payment_service.py
├── notification_service.py
└── service_service.py
```

## Booking Service

Responsible for booking-related business operations such as:

* Booking creation
* Booking cancellation
* Booking status transitions
* Real-time booking status updates
* Booking-related notifications

## Payment Service

Responsible for:

* Payment initiation
* Mock payment processing
* Payment webhook processing
* Booking confirmation after successful payment
* Payment-related notifications
* Real-time status updates

## Notification Service

Responsible for sending notification tasks to Celery.

## Service Service

Responsible for service-related business operations such as:

* Service creation
* Service updates
* Service deletion
* Service-list cache invalidation

---

# 20. Database Entities Involved

The core workflow uses several database entities.

```text
User
  ↓
Booking
  ↓
Service
  ↓
Provider
```

Payment is associated with the booking:

```text
Booking
   ↓
Payment
```

Notifications are associated with the customer and booking:

```text
User
   ↓
Notification
   ↓
Booking
```

The simplified relationship is:

```text
Customer/User
      │
      ├────────── Booking ────────── Service
      │                 │              │
      │                 │              │
      │                 ↓              ↓
      │              Payment        Provider
      │
      └────────── Notification
                       │
                       ↓
                    Booking
```

---

# 21. Complete End-to-End Workflow

The complete successful workflow is:

```text
Customer
   ↓
Login
   ↓
Service Search
   ↓
Select Service
   ↓
Create Booking
   ↓
Booking = pending
   ↓
BOOKING_CREATED Notification
   ↓
Initiate Mock Payment
   ↓
Payment = PENDING
   ↓
Payment SUCCESS
   ↓
Booking = confirmed
   ↓
PAYMENT_SUCCESSFUL Notification
   ↓
BOOKING_CONFIRMED Notification
   ↓
Provider Starts Service
   ↓
Booking = in_progress
   ↓
PROVIDER_STARTED Notification
   ↓
Provider Completes Service
   ↓
Booking = completed
   ↓
BOOKING_COMPLETED Notification
```

---

# 22. Real-Time Flow During Booking

The customer can track booking status using WebSockets.

```text
Customer Mobile Application
          │
          │ WebSocket
          ↓
Django Channels
          │
          ↓
Booking Status Consumer
          │
          ↓
Redis Channel Layer
          │
          ↓
Booking Status Update
          │
          ↓
Customer Mobile Application
```

The important booking status updates are:

```text
pending
   ↓
confirmed
   ↓
in_progress
   ↓
completed
```

---

# 23. Core Workflow Summary

The application's primary business workflow is:

```text
Customer
   ↓
Service Search
   ↓
Booking
   ↓
Payment
   ↓
Provider Confirmation
   ↓
Service Started
   ↓
Service Completed
```

The corresponding booking states are:

```text
pending
   ↓
confirmed
   ↓
in_progress
   ↓
completed
```

Alternative states are:

```text
pending → cancelled
pending → payment_failed
```

The workflow combines:

* Django REST Framework for API operations
* JWT for authentication
* Django service modules for business logic
* Django ORM for database operations
* PostgreSQL for persistent data
* Django Channels for real-time booking status
* Redis for messaging infrastructure
* Celery for asynchronous notifications

The primary successful lifecycle is therefore:

```text
Customer
   ↓
Search
   ↓
Book
   ↓
Pay
   ↓
Confirm
   ↓
Start Service
   ↓
Complete Service

