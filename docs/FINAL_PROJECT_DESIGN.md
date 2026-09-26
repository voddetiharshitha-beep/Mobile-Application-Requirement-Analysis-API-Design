# Final Real-World Mobile Backend Project

## Design and Implementation Documentation

**Project:** Mobile Application Requirement Analysis

**Backend:** Django REST Framework

**Database:** PostgreSQL

**Authentication:** JWT

**Background Processing:** Celery

**Queue / Cache:** Redis

**Real-Time Communication:** Django Channels / WebSocket

---

# 1. Final Project Requirement

A customer should register using the mobile application, search services, select a provider, book a service, complete a mock payment, receive notifications, track the booking status in real time, and view booking history.

The provider should be able to manage services and update booking status.

The administrator should be able to monitor the entire system.

The final implementation covers the complete backend workflow, including authentication, authorization, services, service images, bookings, mock payments, notifications, background processing, real-time booking status updates, security verification, administration, and performance verification.

---

# 2. ER Diagram

The system contains the following main entities:

* User
* UserProfile
* Provider
* ProviderProfile
* Category
* Service
* ServiceImage
* Booking
* Payment
* Notification

## Entity Relationships

```text
User
 │
 ├── UserProfile
 │
 ├── Provider
 │      │
 │      └── ProviderProfile
 │
 ├── Booking
 │
 └── Notification

Category
 │
 └── Service
        │
        ├── ServiceImage
        │
        └── Booking
               │
               └── Payment
```

## Detailed Relationships

```text
User 1 ───── 0..1 UserProfile

User 1 ───── 0..1 Provider

Provider 1 ───── 0..1 ProviderProfile

Category 1 ───── * Service

Provider 1 ───── * Service

Service 1 ───── * ServiceImage

User 1 ───── * Booking

Provider 1 ───── * Booking

Service 1 ───── * Booking

Booking 1 ───── 0..1 Payment

User 1 ───── * Notification

Booking 1 ───── * Notification
```

---

# 3. Main Entity Fields

## User

```text
id
username
email
password
is_staff
is_superuser
```

## UserProfile

```text
id
user
image
created_at
updated_at
```

## Provider

```text
id
user
name
description
status
created_at
updated_at
```

## ProviderProfile

```text
id
provider
name
status
created_at
updated_at
```

## Category

```text
id
name
description
status
created_at
updated_at
```

## Service

```text
id
name
description
location
price
status
category
provider
created_at
updated_at
```

## ServiceImage

```text
id
service
image
uploaded_at
```

## Booking

```text
id
customer
provider
service
booking_date
booking_time
amount
status
created_at
updated_at
```

## Payment

```text
id
booking
amount
transaction_id
payment_status
payment_method
created_at
```

## Notification

```text
id
recipient
booking
notification_type
is_read
created_at
```

---

# 4. API Specification

## Base URL

```text
/api/v1/
```

All protected APIs require JWT authentication unless otherwise specified.

---

# 5. Authentication APIs

## Register

```http
POST /api/v1/register/
```

**Purpose:**

Register a new user.

**Authentication:**

```text
Not required
```

---

## Login

```http
POST /api/v1/token/
```

**Purpose:**

Obtain JWT access and refresh tokens.

**Authentication:**

```text
Not required
```

---

## Refresh Token

```http
POST /api/v1/token/refresh/
```

**Purpose:**

Generate a new access token using a refresh token.

**Authentication:**

```text
Not required
```

---

# 6. Profile API

## Upload Profile Image

```http
POST /api/v1/profile/image/
```

**Authentication:**

```text
JWT required
```

**Purpose:**

Upload or update the authenticated user's profile image.

---

# 7. Service APIs

## List Services

```http
GET /api/v1/services/
```

## Create Service

```http
POST /api/v1/services/
```

## View Service

```http
GET /api/v1/services/{id}/
```

## Update Service

```http
PUT/PATCH /api/v1/services/{id}/
```

## Delete Service

```http
DELETE /api/v1/services/{id}/
```

**Authentication:**

```text
JWT required
```

Provider authorization is applied when creating, updating, or deleting provider-owned services.

---

# 8. Service Search, Filtering, Sorting and Pagination

The Service API supports searching, filtering, sorting, and pagination.

## Search by Service Name

The implemented API uses the `name` query parameter.

Example:

```http
GET /api/v1/services/?name=clean
```

## Supported Filters

```text
name
category
provider
location
price
min_price
max_price
status
```

## Sorting

Supported ordering values are:

```text
price
-price
created_at
-created_at
```

These represent:

```text
price          → Price ascending
-price         → Price descending
created_at     → Oldest
-created_at    → Newest
```

## Pagination

The API supports:

```text
page
page_size
```

Example:

```http
GET /api/v1/services/?page=1&page_size=2
```

The Service API uses page-number pagination with:

```text
Default page size: 10
Maximum page size: 100
```

Pagination was verified successfully.

---

# 9. Service Image APIs

## List Service Images

```http
GET /api/v1/services/{service_id}/images/
```

## Upload Service Image

```http
POST /api/v1/services/{service_id}/images/
```

## Delete Service Image

```http
DELETE /api/v1/services/{service_id}/images/{image_id}/
```

**Authentication:**

```text
JWT required
```

Providers can upload and delete images belonging to their own services.

Service image upload was successfully tested.

---

# 10. Booking APIs

## List/Create Bookings

```http
GET /api/v1/bookings/

POST /api/v1/bookings/
```

Customers can create bookings and view their own bookings.

Providers can view bookings assigned to them.

---

## View Booking

```http
GET /api/v1/bookings/{id}/
```

Customers can access their own bookings.

---

## Update Booking

```http
PUT/PATCH /api/v1/bookings/{id}/
```

Only valid booking changes are permitted.

The backend prevents modification of completed or cancelled bookings.

---

## Cancel Booking

```http
POST /api/v1/bookings/{id}/cancel/
```

The backend prevents:

```text
Cancelled booking → Cancel again
Completed booking → Cancel
```

---

## Update Booking Status

```http
POST /api/v1/bookings/{id}/status/
```

The provider uses this endpoint to update the booking status.

Supported provider workflow:

```text
PENDING
   ↓
CONFIRMED
   ↓
IN_PROGRESS
   ↓
COMPLETED
```

The status update also triggers the appropriate real-time and notification workflows.

---

# 11. Payment APIs

## Initiate Mock Payment

```http
POST /api/v1/services/payments/initiate/
```

A mock payment transaction is created with a generated transaction ID.

Example transaction format:

```text
MOCK-XXXXXXXXXXXX
```

---

## Process Mock Payment

```http
POST /api/v1/services/payments/{id}/process/
```

The payment belongs to the authenticated customer and must be in the pending state before processing.

---

## Payment Webhook

```http
POST /api/v1/services/payments/webhook/
```

The webhook does not require normal JWT authentication.

Instead, it is protected using:

```text
X-Webhook-Secret
```

The configured webhook secret is validated before processing.

## Payment Statuses

```text
PENDING
SUCCESS
FAILED
REFUNDED
```

When payment succeeds:

```text
Payment
   ↓
SUCCESS
   ↓
Booking
   ↓
CONFIRMED
   ↓
Notifications generated
```

Both `PAYMENT_SUCCESSFUL` and `BOOKING_CONFIRMED` notifications were verified.

---

# 12. Notification API

## List Notifications

```http
GET /api/v1/services/notifications/
```

**Authentication:**

```text
JWT required
```

Users receive notifications belonging to their account.

## Notification Types

The system implements the following six notification types:

```text
BOOKING_CREATED

PAYMENT_SUCCESSFUL

BOOKING_CONFIRMED

PROVIDER_STARTED

BOOKING_COMPLETED

BOOKING_CANCELLED
```

All six notification types were implemented and verified.

---

# 13. Background Processing

Celery is used for background notification processing.

The workflow is:

```text
Django API
    ↓
Create Celery Task
    ↓
Redis
    ↓
Celery Worker
    ↓
Create Notification
    ↓
Notification stored in Database
```

Celery worker configuration was successfully verified.

The notification task is:

```text
services.tasks.create_notification
```

Celery version used during verification:

```text
5.6.3
```

---

# 14. WebSocket / Real-Time Booking Status

The system provides real-time booking status updates using Django Channels and WebSocket.

## WebSocket Endpoint

```text
ws://127.0.0.1:8000/ws/bookings/{booking_id}/
```

## Real-Time Workflow

```text
Provider updates booking
        ↓
Django processes status
        ↓
Booking status saved
        ↓
WebSocket group notification
        ↓
Customer receives real-time status
```

The implemented WebSocket consumer sends booking status information containing:

```json
{
    "booking_id": "booking-uuid",
    "status": "confirmed",
    "message": "Booking status changed to confirmed."
}
```

The real-time booking status workflow was successfully tested.

---

# 15. Role / Permission Matrix

| Operation              | Customer    | Provider                  | Admin |
| ---------------------- | ----------- | ------------------------- | ----- |
| Register               | Yes         | Yes, through registration | No    |
| Login                  | Yes         | Yes                       | Yes   |
| View profile           | Own profile | Own profile               | Yes   |
| Upload profile image   | Yes         | Yes                       | Yes   |
| View services          | Yes         | Yes                       | Yes   |
| Search services        | Yes         | Yes                       | Yes   |
| Create service         | No          | Yes                       | Yes   |
| Update own service     | No          | Yes                       | Yes   |
| Delete own service     | No          | Yes                       | Yes   |
| Upload service image   | No          | Own services              | Yes   |
| Create booking         | Yes         | No                        | Yes   |
| View own bookings      | Yes         | No                        | Yes   |
| Cancel own booking     | Yes         | No                        | Yes   |
| View provider bookings | No          | Yes                       | Yes   |
| Confirm booking        | No          | Yes                       | Yes   |
| Start service          | No          | Yes                       | Yes   |
| Complete service       | No          | Yes                       | Yes   |
| Initiate payment       | Yes         | No                        | Yes   |
| Process own payment    | Yes         | No                        | Yes   |
| View notifications     | Yes         | Yes                       | Yes   |
| View all users         | No          | No                        | Yes   |
| View all providers     | No          | No                        | Yes   |
| View all services      | No          | No                        | Yes   |
| View all bookings      | No          | No                        | Yes   |
| View all payments      | No          | No                        | Yes   |
| View all notifications | No          | No                        | Yes   |

## Authorization Principle

```text
Customer
    ↓
Customer-owned resources only

Provider
    ↓
Provider-owned resources
and provider operations

Admin
    ↓
System-wide administrative access
```

---

# 16. Booking State Diagram

```text
                    ┌─────────────┐
                    │   PENDING   │
                    └──────┬──────┘
                           │
              ┌────────────┼─────────────┐
              │            │             │
              ▼            ▼             ▼
        CONFIRMED      CANCELLED    PAYMENT_FAILED
              │
              ▼
        IN_PROGRESS
              │
              ▼
         COMPLETED
```

## Valid State Transitions

```text
PENDING
  ├──> CONFIRMED
  ├──> CANCELLED
  └──> PAYMENT_FAILED

CONFIRMED
  ├──> IN_PROGRESS
  └──> CANCELLED

IN_PROGRESS
  └──> COMPLETED
```

The implementation validates booking status transitions.

The backend also prevents modification of completed and cancelled bookings and prevents completed bookings from being cancelled.

---

# 17. System Architecture

```text
                         ┌─────────────────┐
                         │   Mobile App    │
                         │  Android / iOS  │
                         └────────┬────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                 REST API                  WebSocket
                    │                           │
                    ▼                           ▼
          ┌─────────────────────────────────────────┐
          │           Django Backend                │
          │                                         │
          │ Authentication                          │
          │ Authorization                           │
          │ Service APIs                            │
          │ Booking APIs                            │
          │ Payment APIs                            │
          │ Notification APIs                       │
          │ File Upload APIs                        │
          │ WebSocket / Channels                    │
          └───────────────┬──────────────┬──────────┘
                          │              │
                          ▼              ▼
                  ┌──────────────┐  ┌──────────────┐
                  │  PostgreSQL  │  │    Redis     │
                  │   Database   │  │ Cache/Queue  │
                  └──────────────┘  └───────┬──────┘
                                            │
                              ┌─────────────┴─────────────┐
                              │                           │
                              ▼                           ▼
                       Django Cache                Celery Worker
                                                       │
                                                       ▼
                                              Background Tasks
                                                       │
                                                       ▼
                                                 Notifications
```

Redis is used for:

```text
Django API caching
Celery message broker
Celery result backend
Django Channels real-time communication
```

---

# 18. Customer Workflow

```text
Register
   ↓
Login
   ↓
JWT Authentication
   ↓
Profile
   ↓
Search Services
   ↓
View Service
   ↓
Select Provider
   ↓
Create Booking
   ↓
Mock Payment
   ↓
Payment Confirmation
   ↓
Payment / Booking Notifications
   ↓
Real-Time Booking Status
   ↓
Service Completion
   ↓
Booking History
```

The customer workflow was implemented and tested through the backend APIs.

---

# 19. Provider Workflow

```text
Login
   ↓
JWT Authentication
   ↓
Create Service
   ↓
Upload Service Image
   ↓
Receive Booking
   ↓
Accept Booking
   ↓
Start Service
   ↓
Complete Service
```

The provider workflow was fully verified.

The verified booking status progression was:

```text
PENDING
   ↓
CONFIRMED
   ↓
IN_PROGRESS
   ↓
COMPLETED
```

---

# 20. Admin Workflow

```text
Admin Login
     ↓
Django Admin Dashboard
     ↓
View Users
     ↓
View Providers
     ↓
View Services
     ↓
View Bookings
     ↓
View Payments
     ↓
View Notifications
     ↓
Manage User Profiles
```

The Django Admin interface was successfully verified.

The administrator account was verified as:

```text
is_staff = True
is_superuser = True
```

Provider accounts were verified as non-administrative users.

---

# 21. Security Design and Verification

The API uses JWT authentication.

Protected resources require:

```text
Authorization: Bearer <access_token>
```

Security verification covered:

```text
Unauthenticated → Protected API
Customer → Provider API
Provider → Admin API
User A → User B Booking
```

## Verification Results

| Security Test                   | Result |
| ------------------------------- | ------ |
| Unauthenticated → Protected API | PASS   |
| Customer → Provider API         | PASS   |
| Provider → Admin                | PASS   |
| User A → User B Booking         | PASS   |

Object-level authorization ensures that users cannot access resources belonging to other users.

The backend returned appropriate authentication or authorization errors for unauthorized access.

---

# 22. Performance Verification

Performance verification covered:

```text
Database query count
Pagination
Search performance
Redis cache usage
API response time
```

## 22.1 Database Query Optimization

The Service List API uses:

```python
select_related("category", "provider")
```

A test without `select_related()` produced:

```text
Database queries: 7
```

The optimized query using `select_related()` produced:

```text
Database queries: 1
```

Result:

```text
7 queries → 1 query
```

This represents approximately:

```text
86% fewer database queries
```

for the tested Service List scenario.

---

# 23. Pagination Verification

The Service API was tested using:

```http
GET /api/v1/services/?page=1&page_size=2
```

Verified result:

```text
Total services: 3
Results on page: 2
Next page: available
Previous page: null
```

Pagination is therefore functioning correctly.

---

# 24. Search Performance

The Service API search was tested using:

```http
GET /api/v1/services/?name=clean
```

Measured local development response time:

```text
Approximately 36.96 ms
```

The test was performed with a small local dataset, so this value is a development baseline rather than a production benchmark.

---

# 25. API Response Time

Before cache optimization, five local Service List requests produced:

```text
Request 1: 31.68 ms
Request 2:  8.08 ms
Request 3: 11.82 ms
Request 4: 12.69 ms
Request 5: 12.46 ms
```

The first request was slower than the subsequent requests.

---

# 26. Redis Cache Implementation

Django Redis caching was added using `django-redis`.

Cache configuration:

```text
Redis server: 127.0.0.1:6379
Django cache database: Redis DB 2
Cache duration: 60 seconds
```

Redis cache connectivity was verified successfully.

The following cache operation was tested:

```text
Django
  ↓
Redis SET
  ↓
Redis GET
  ↓
Cached value returned successfully
```

The Service List API now uses Redis caching.

The cache key includes the complete request URL so that different:

```text
filters
sorting
pagination
search parameters
```

receive separate cache entries.

The service cache is also cleared when services are created, updated, or deleted.

---

# 27. Cached API Performance Test

After clearing the Redis cache, five Service List requests were measured:

```text
Request 1: 26.22 ms
Request 2: 13.54 ms
Request 3: 12.21 ms
Request 4: 10.53 ms
Request 5: 15.56 ms
```

The results demonstrate that Redis caching is functioning, but the local development measurements do not show a consistent latency reduction because the test dataset contains only three services and local request overhead is significant.

Therefore, the documented optimization is:

```text
Database optimization:
7 queries → 1 query

Caching optimization:
Redis caching implemented and verified
```

The cache should provide greater benefits as the dataset and request volume increase.

---

# 28. Background Processing Verification

Celery was used for asynchronous notification processing.

Verified workflow:

```text
Booking / Payment / Status Event
            ↓
      Celery Task
            ↓
          Redis
            ↓
     Celery Worker
            ↓
   Create Notification
            ↓
        Database
```

The following six notification events were implemented and verified:

```text
1. BOOKING_CREATED

2. PAYMENT_SUCCESSFUL

3. BOOKING_CONFIRMED

4. PROVIDER_STARTED

5. BOOKING_COMPLETED

6. BOOKING_CANCELLED
```

Celery background processing was successfully verified.

---

# 29. Real-Time Verification

Django Channels and Redis were used for real-time booking status communication.

The WebSocket endpoint:

```text
ws://127.0.0.1:8000/ws/bookings/{booking_id}/
```

was successfully tested.

A verified WebSocket event contained:

```json
{
    "booking_id": "3de88a0a-6252-4ede-98cf-0fc49ffb6e0f",
    "status": "confirmed",
    "message": "Booking status changed to confirmed."
}
```

This confirms that booking status changes can be delivered to connected clients in real time.

---

# 30. Implementation Verification Summary

## Customer Flow

```text
Registration              ✓
Login                     ✓
JWT Authentication        ✓
Service Search            ✓
Service Filtering         ✓
Service Pagination        ✓
Booking Creation          ✓
Mock Payment              ✓
Payment Confirmation      ✓
Notifications             ✓
Real-Time Status          ✓
Booking History           ✓
```

## Provider Flow

```text
Provider Login            ✓
Create Service            ✓
Upload Service Image      ✓
Receive Booking           ✓
Confirm Booking           ✓
Start Service             ✓
Complete Service          ✓
```

## Admin Flow

```text
Admin Login               ✓
User Management           ✓
Provider Management       ✓
Service Management        ✓
Booking Monitoring        ✓
Payment Monitoring        ✓
Notification Monitoring   ✓
User Profile Management   ✓
```

## Security

```text
Authentication             ✓
Authorization              ✓
Object-Level Protection   ✓
Customer Isolation         ✓
Provider Isolation         ✓
Admin Protection           ✓
```

## Infrastructure

```text
Redis                      ✓
Celery                     ✓
Django Cache               ✓
Django Channels            ✓
WebSocket                  ✓
```

---

# 31. Final Completion Checklist

| Requirement                       | Status   |
| --------------------------------- | -------- |
| Final Requirement                 | Complete |
| ER Diagram                        | Complete |
| Entity Relationships              | Complete |
| API Specification                 | Complete |
| Authentication                    | Complete |
| Profile API                       | Complete |
| Service CRUD                      | Complete |
| Service Search                    | Complete |
| Service Filtering                 | Complete |
| Service Sorting                   | Complete |
| Pagination                        | Complete |
| Service Image Upload              | Complete |
| Service Image Management          | Complete |
| Booking API                       | Complete |
| Booking Validation                | Complete |
| Booking State Management          | Complete |
| Mock Payment                      | Complete |
| Payment Webhook                   | Complete |
| Notification System               | Complete |
| Celery Background Processing      | Complete |
| Real-Time WebSocket Status        | Complete |
| Provider Workflow                 | Complete |
| Admin Workflow                    | Complete |
| Security Verification             | Complete |
| Database Query Optimization       | Complete |
| Redis Cache                       | Complete |
| Performance Verification          | Complete |
| Final Implementation Verification | Complete |

---

# 32. Final Project Workflow

The complete implemented backend workflow is:

```text
                    CUSTOMER
                       │
                       ▼
                  Registration
                       │
                       ▼
                     Login
                       │
                       ▼
                JWT Authentication
                       │
                       ▼
                Search Services
                       │
                       ▼
                Select Provider
                       │
                       ▼
                 Create Booking
                       │
                       ▼
                 Mock Payment
                       │
                       ▼
              Payment Confirmation
                       │
              ┌────────┴────────┐
              ▼                 ▼
        Notifications      Booking Confirmed
                                  │
                                  ▼
                           Provider Starts
                                  │
                                  ▼
                           IN_PROGRESS
                                  │
                                  ▼
                            COMPLETED
                                  │
                                  ▼
                         Real-Time Update
                                  │
                                  ▼
                          Booking History


                    PROVIDER
                       │
                       ▼
                     Login
                       │
                       ▼
                Create Service
                       │
                       ▼
              Upload Service Image
                       │
                       ▼
                Receive Booking
                       │
                       ▼
                Confirm Booking
                       │
                       ▼
                 Start Service
                       │
                       ▼
               Complete Service


                     ADMIN
                       │
                       ▼
                 Admin Dashboard
                       │
        ┌──────────────┼───────────────┐
        ▼              ▼               ▼
      Users        Providers        Services
        │              │               │
        └──────────────┼───────────────┘
                       ▼
                   Bookings
                       │
                       ▼
                   Payments
                       │
                       ▼
                 Notifications
```

---

# 33. Final Design and Implementation Conclusion

The Mobile Application Requirement Analysis project implements a complete mobile backend workflow using Django REST Framework.

The final backend provides:

```text
JWT Authentication
        +
Role-Based Authorization
        +
Service Management
        +
Service Image Management
        +
Service Search / Filtering
        +
Pagination / Sorting
        +
Booking Management
        +
Mock Payment Processing
        +
Payment Webhook
        +
Celery Background Processing
        +
Redis
        +
Notifications
        +
Django Channels / WebSocket
        +
Real-Time Booking Status
        +
Django Admin
        +
Security Verification
        +
Performance Optimization
```

The major workflows were implemented and verified independently.

Performance verification demonstrated a reduction in database queries from:

```text
7 queries → 1 query
```

through the use of `select_related()`.

Redis caching was also implemented and verified for the Service List API.

The six required notification types were implemented and verified using Celery background processing.

The provider workflow was verified from service creation through booking completion.

The admin interface was verified for system monitoring and management.

Security tests confirmed that unauthorized users cannot access protected resources outside their permitted scope.

The final implementation therefore satisfies the required customer, provider, administrator, payment, notification, real-time communication, security, and performance requirements of the project.
