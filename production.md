# Project Technical Design

## 1. Architecture

### 1.1 System Overview

The Mobile Service Booking Application follows a modular client-server architecture.

The system allows customers to:

* Register and log in.
* Create and manage their profile.
* Search available services.
* View service and provider details.
* Create and manage bookings.
* Make and track payments.
* Receive notifications.
* Communicate with service providers.
* Track booking status.

Service providers can:

* Create and manage their provider profile.
* Create and manage services.
* Manage service availability.
* View customer bookings.
* Accept, reject, and update booking status.
* Communicate with customers.

Administrators can manage users, providers, services, bookings, payments, notifications, and system data.

### 1.2 High-Level Architecture

```text
                    ┌──────────────────────┐
                    │     Mobile Client    │
                    │   Customer / Provider│
                    └──────────┬───────────┘
                               │
                               │ HTTPS / REST API
                               ▼
                    ┌──────────────────────┐
                    │     API Layer        │
                    │     Django + DRF     │
                    └──────────┬───────────┘
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
             ▼                 ▼                 ▼
      ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
      │ PostgreSQL  │   │    Redis    │   │   Celery    │
      │  Database   │   │ Cache/Queue │   │ Background  │
      └─────────────┘   └─────────────┘   │   Tasks     │
                                          └─────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ External Integrations│
                    │ Payment / Email /    │
                    │ Notification Services│
                    └──────────────────────┘
```

### 1.3 Technology Stack

| Layer                      | Technology               |
| -------------------------- | ------------------------ |
| Mobile Client              | Mobile application       |
| Backend                    | Python / Django          |
| API                        | Django REST Framework    |
| Authentication             | JWT                      |
| Database                   | PostgreSQL               |
| Cache                      | Redis                    |
| Background Tasks           | Celery                   |
| Real-Time Communication    | WebSocket                |
| API Documentation          | OpenAPI / Swagger        |
| Containerization           | Docker                   |
| Web Server / Reverse Proxy | Nginx                    |
| Deployment                 | Cloud/container platform |

### 1.4 Communication

The mobile application communicates with the backend using HTTPS and REST APIs.

WebSocket communication is used for real-time chat.

```text
Mobile App
    │
    ├── HTTPS → REST API
    │
    └── WebSocket → Real-Time Chat
                         │
                         ▼
                     Django
                         │
                         ▼
                    PostgreSQL
```

---

# 2. Modules

The system is divided into the following modules.

## 2.1 Authentication Module

Responsibilities:

* User registration.
* User login.
* User logout.
* JWT access and refresh tokens.
* Password management.
* Role-based access control.
* Account activation/deactivation.

## 2.2 User Profile Module

Responsibilities:

* Create profile.
* View profile.
* Update profile.
* Store phone number.
* Store address.
* Store profile image where supported.

## 2.3 Service Provider Module

Responsibilities:

* Provider registration.
* Provider profile management.
* Business information.
* Service availability.
* Provider booking management.
* Accept/reject bookings.
* Update booking status.

## 2.4 Services Module

Responsibilities:

* Create services.
* View services.
* View service details.
* Update services.
* Delete services.
* Set service price.
* Set service availability.

## 2.5 Search Module

Responsibilities:

* Search services.
* Filter services.
* Search by location.
* Filter by availability.
* Filter by price.
* Sort service results.

Example:

```text
GET /api/v1/services/?search=cleaning&location=hyderabad&available=true
```

## 2.6 Booking Module

Responsibilities:

* Create bookings.
* View bookings.
* View booking details.
* Booking history.
* Accept/reject bookings.
* Cancel bookings.
* Update booking status.
* Track booking progress.

Booking statuses:

```text
PENDING
ACCEPTED
REJECTED
IN_PROGRESS
COMPLETED
CANCELLED
```

## 2.7 Payment Module

Responsibilities:

* Create payment records.
* Process payments through an external payment provider.
* Track payment status.
* Store transaction information.
* Handle refunds where supported.

Payment statuses:

```text
PENDING
SUCCESS
FAILED
REFUNDED
```

## 2.8 Notification Module

Responsibilities:

* Booking notifications.
* Booking status notifications.
* Payment notifications.
* System notifications.
* Notification history.
* Mark notifications as read.

## 2.9 Chat Module

Responsibilities:

* Customer-provider communication.
* Send messages.
* Receive messages.
* Message history.
* Booking-specific conversations.
* Real-time communication using WebSockets.

## 2.10 Admin Module

Responsibilities:

* Manage users.
* Manage service providers.
* Manage services.
* Manage bookings.
* Manage payments.
* Manage notifications.
* Activate/deactivate accounts.
* Monitor system activity.

---

# 3. Database

PostgreSQL is used as the primary relational database.

## 3.1 Main Entities

### User

```text
User
----------------
id (PK)
name
email
role
password
is_active
created_at
updated_at
```

### Profile

```text
Profile
----------------
id (PK)
user_id (FK)
phone
address
profile_image
created_at
updated_at
```

Relationship:

```text
User 1 ───── 1 Profile
```

### ServiceProvider

```text
ServiceProvider
----------------
id (PK)
user_id (FK)
business_name
description
availability
created_at
updated_at
```

Relationship:

```text
User 1 ───── 0..1 ServiceProvider
```

### Service

```text
Service
----------------
id (PK)
provider_id (FK)
name
description
price
availability
created_at
updated_at
```

Relationship:

```text
ServiceProvider 1 ───── M Service
```

### Booking

```text
Booking
----------------
id (PK)
customer_id (FK)
service_id (FK)
provider_id (FK)
booking_date
status
created_at
updated_at
```

Relationships:

```text
Customer 1 ───── M Booking

Service 1 ───── M Booking

ServiceProvider 1 ───── M Booking
```

### Payment

```text
Payment
----------------
id (PK)
booking_id (FK)
amount
status
transaction_id
created_at
updated_at
```

Relationship:

```text
Booking 1 ───── 1 Payment
```

### Notification

```text
Notification
----------------
id (PK)
user_id (FK)
booking_id (FK)
title
message
is_read
created_at
```

Relationships:

```text
User 1 ───── M Notification

Booking 1 ───── M Notification
```

### ChatMessage

```text
ChatMessage
----------------
id (PK)
booking_id (FK)
sender_id (FK)
receiver_id (FK)
message
created_at
```

Relationships:

```text
Booking 1 ───── M ChatMessage

User 1 ───── M ChatMessage (sender)

User 1 ───── M ChatMessage (receiver)
```

## 3.2 Database Relationship Summary

```text
User
 │
 ├──── Profile
 │
 ├──── ServiceProvider
 │          │
 │          └──── Service
 │                    │
 └─────────────── Booking ───── Payment
                       │
                       ├──── Notification
                       │
                       └──── ChatMessage
```

---

# 4. APIs

The API uses REST architecture.

Base URL:

```text
/api/v1/
```

JWT authentication is used for protected endpoints.

Authentication header:

```text
Authorization: Bearer <access_token>
```

## 4.1 Authentication APIs

| Method | Endpoint                      | Purpose           |
| ------ | ----------------------------- | ----------------- |
| POST   | `/api/v1/auth/register/`      | Register user     |
| POST   | `/api/v1/auth/login/`         | Login             |
| POST   | `/api/v1/auth/logout/`        | Logout            |
| POST   | `/api/v1/auth/token/refresh/` | Refresh JWT token |

## 4.2 Profile APIs

| Method | Endpoint           | Purpose                  |
| ------ | ------------------ | ------------------------ |
| GET    | `/api/v1/profile/` | View profile             |
| POST   | `/api/v1/profile/` | Create profile           |
| PUT    | `/api/v1/profile/` | Update profile           |
| PATCH  | `/api/v1/profile/` | Partially update profile |
| DELETE | `/api/v1/profile/` | Delete profile           |

## 4.3 Provider APIs

| Method    | Endpoint                  | Purpose          |
| --------- | ------------------------- | ---------------- |
| GET       | `/api/v1/providers/`      | List providers   |
| GET       | `/api/v1/providers/{id}/` | Provider details |
| POST      | `/api/v1/providers/`      | Create provider  |
| PUT/PATCH | `/api/v1/providers/{id}/` | Update provider  |
| DELETE    | `/api/v1/providers/{id}/` | Delete provider  |

## 4.4 Service APIs

| Method    | Endpoint                 | Purpose         |
| --------- | ------------------------ | --------------- |
| GET       | `/api/v1/services/`      | List services   |
| GET       | `/api/v1/services/{id}/` | Service details |
| POST      | `/api/v1/services/`      | Create service  |
| PUT/PATCH | `/api/v1/services/{id}/` | Update service  |
| DELETE    | `/api/v1/services/{id}/` | Delete service  |

Search example:

```text
GET /api/v1/services/?search=cleaning&location=hyderabad&available=true
```

## 4.5 Booking APIs

| Method    | Endpoint                                 | Purpose                |
| --------- | ---------------------------------------- | ---------------------- |
| GET       | `/api/v1/bookings/`                      | List customer bookings |
| POST      | `/api/v1/bookings/`                      | Create booking         |
| GET       | `/api/v1/bookings/{id}/`                 | View booking           |
| PUT/PATCH | `/api/v1/bookings/{id}/`                 | Update booking         |
| DELETE    | `/api/v1/bookings/{id}/`                 | Cancel/delete booking  |
| GET       | `/api/v1/provider/bookings/`             | Provider bookings      |
| PATCH     | `/api/v1/provider/bookings/{id}/status/` | Update booking status  |

## 4.6 Payment APIs

| Method | Endpoint                        | Purpose         |
| ------ | ------------------------------- | --------------- |
| POST   | `/api/v1/payments/`             | Create payment  |
| GET    | `/api/v1/payments/`             | List payments   |
| GET    | `/api/v1/payments/{id}/`        | Payment details |
| POST   | `/api/v1/payments/{id}/refund/` | Refund payment  |

## 4.7 Notification APIs

| Method | Endpoint                           | Purpose              |
| ------ | ---------------------------------- | -------------------- |
| GET    | `/api/v1/notifications/`           | List notifications   |
| GET    | `/api/v1/notifications/{id}/`      | Notification details |
| PATCH  | `/api/v1/notifications/{id}/read/` | Mark as read         |
| DELETE | `/api/v1/notifications/{id}/`      | Delete notification  |

## 4.8 Chat APIs

| Method | Endpoint                          | Purpose        |
| ------ | --------------------------------- | -------------- |
| GET    | `/api/v1/bookings/{id}/messages/` | Get messages   |
| POST   | `/api/v1/bookings/{id}/messages/` | Send message   |
| GET    | `/api/v1/messages/{id}/`          | View message   |
| DELETE | `/api/v1/messages/{id}/`          | Delete message |

WebSocket:

```text
WS /ws/bookings/{booking_id}/
```

## 4.9 Admin APIs

| Method | Endpoint                       | Purpose          |
| ------ | ------------------------------ | ---------------- |
| GET    | `/api/v1/admin/users/`         | Manage users     |
| GET    | `/api/v1/admin/providers/`     | Manage providers |
| GET    | `/api/v1/admin/services/`      | Manage services  |
| GET    | `/api/v1/admin/bookings/`      | Manage bookings  |
| GET    | `/api/v1/admin/payments/`      | Manage payments  |
| DELETE | `/api/v1/admin/users/{id}/`    | Delete user      |
| DELETE | `/api/v1/admin/services/{id}/` | Delete service   |

---

# 5. Roles

The application contains three primary roles.

## 5.1 Admin

Admin has system-level permissions.

Admin can:

* Manage users.
* Manage customers.
* Manage service providers.
* Manage services.
* Manage bookings.
* Manage payments.
* Manage notifications.
* Activate/deactivate accounts.
* View system information.

## 5.2 Customer

Customer is the mobile user who searches for and books services.

Customer can:

* Register.
* Login.
* Manage their profile.
* Search services.
* View service details.
* Create bookings.
* View booking history.
* Cancel permitted bookings.
* Make payments.
* View notifications.
* Communicate with providers.
* Track booking status.

## 5.3 Service Provider

Service Provider provides services to customers.

Provider can:

* Register as a provider.
* Manage provider profile.
* Create services.
* Update services.
* Delete permitted services.
* Manage availability.
* View bookings for their services.
* Accept or reject bookings.
* Update booking status.
* Communicate with customers.
* Receive notifications.

---

# 6. Business Rules

## User Rules

1. A user must register before accessing protected features.
2. Email addresses must be unique.
3. Phone numbers must follow the application's validation rules.
4. Every user must have an assigned role.
5. Users can update their own profile unless an administrator performs the operation.

## Service Provider Rules

6. Only Service Providers or Admins can create services.
7. A provider can update or delete only their own services unless the user is an Admin.
8. A service must belong to an active provider.
9. Only available services can be booked.
10. A provider cannot book their own service.
11. A service must contain a valid name, description, price, and availability status.

## Booking Rules

12. Only Customers can create service bookings.
13. A booking must reference an existing customer, service, and provider.
14. A customer cannot book an unavailable service.
15. Booking date/time must be valid and cannot be in the past.
16. New bookings start with `PENDING` status.
17. A provider can accept or reject bookings for their own services.
18. A cancelled booking cannot be completed.
19. A completed booking cannot be cancelled.
20. Users can access only bookings they are authorized to view or modify.

## Payment Rules

21. Payment must be associated with a valid booking.
22. Payment amount must be valid and non-negative.
23. A successful payment cannot be processed twice for the same booking.
24. Payment status must be tracked.
25. Refunds are allowed only according to the application's refund rules.

## Notification Rules

26. Customers receive notifications when booking status changes.
27. Providers receive notifications when customers create bookings.
28. Users can see only their own notifications.
29. Users can mark their own notifications as read.

## Chat Rules

30. Only the customer and provider associated with a booking can access its conversation.
31. Chat messages cannot be empty.
32. Unauthorized users cannot access another booking's conversation.

## Booking Status Workflow

Normal workflow:

```text
PENDING
   │
   ├── ACCEPTED
   │      │
   │      └── IN_PROGRESS
   │              │
   │              └── COMPLETED
   │
   ├── REJECTED
   │
   └── CANCELLED
```

Allowed transitions must be validated by the backend.

Invalid examples:

```text
CANCELLED  → COMPLETED
COMPLETED  → CANCELLED
REJECTED   → COMPLETED
```

---

# 7. Security

Security is implemented at the API and application levels.

## 7.1 Authentication

JWT-based authentication is used for protected APIs.

```text
Authorization: Bearer <access_token>
```

Access tokens are short-lived and refresh tokens are used to obtain new access tokens.

## 7.2 Authorization

Role-based permissions ensure that users can perform only operations allowed for their role.

Example:

```text
Admin              → System management
Customer           → Own bookings and customer features
Service Provider   → Own services and provider bookings
```

## 7.3 Password Security

* Passwords must never be stored as plain text.
* Django's password hashing mechanism should be used.
* Password validation should enforce appropriate security requirements.
* Password reset operations must use secure verification.

## 7.4 API Security

The API should:

* Use HTTPS in production.
* Validate all incoming data.
* Require authentication for protected endpoints.
* Apply role-based permissions.
* Prevent unauthorized object access.
* Return safe error responses.
* Avoid exposing sensitive information.

## 7.5 Database Security

* Use environment variables for database credentials.
* Do not commit passwords or secret keys to source control.
* Use restricted database users.
* Apply database migrations through controlled deployment processes.
* Validate foreign-key relationships.

## 7.6 Input Validation

All user input must be validated before processing.

Examples:

```text
Email       → Valid email format
Password    → Required security rules
Price       → Numeric and non-negative
Booking     → Valid service/provider/customer
Message     → Must not be empty
```

## 7.7 Object-Level Authorization

Users must not be able to access another user's private data by changing an object ID.

For example:

```text
Customer A
    ↓
Booking 101 → Allowed

Customer A
    ↓
Booking 202 owned by Customer B → Denied
```

## 7.8 Security Headers and Production Protection

Production deployment should use:

* HTTPS.
* Secure cookies where applicable.
* CSRF protection where applicable.
* CORS restrictions.
* Security headers.
* Debug mode disabled.
* Secret keys stored outside source code.

---

# 8. External Integrations

The system can integrate with external services to provide additional functionality.

## 8.1 Payment Gateway

A third-party payment gateway can be integrated for online payments.

Example flow:

```text
Customer
   │
   ▼
Create Booking
   │
   ▼
Payment API
   │
   ▼
External Payment Gateway
   │
   ├── SUCCESS
   │
   └── FAILED
```

The application should store:

* Payment ID.
* Booking ID.
* Transaction ID.
* Amount.
* Payment status.
* Payment timestamp.

The actual payment credentials must be stored securely as environment variables.

## 8.2 Email Service

An external email service can be used for:

* Registration confirmation.
* Password reset.
* Booking confirmation.
* Booking status changes.
* Payment notifications.

Background processing can be used so email delivery does not block API requests.

## 8.3 Push Notification Service

A push notification provider can be used to send mobile notifications for:

* New bookings.
* Booking acceptance/rejection.
* Booking status updates.
* Payment results.
* Important system messages.

## 8.4 Redis

Redis can be used internally for:

* Caching frequently accessed service data.
* Temporary data.
* Celery task queues.
* Real-time application support.

## 8.5 Celery

Celery can process background tasks such as:

* Sending emails.
* Sending notifications.
* Processing non-immediate tasks.
* Scheduled maintenance tasks.

## 8.6 WebSocket Service

WebSocket communication is used for real-time chat.

```text
Customer
   │
   │ WebSocket
   ▼
Django WebSocket Layer
   │
   ▼
Provider
```

Only authorized booking participants can connect to the relevant booking conversation.

## 8.7 Maps/Location Service

If location-based service discovery is required, a mapping/location provider can be integrated for:

* Provider locations.
* Customer locations.
* Distance calculation.
* Location-based service search.
* Address validation.

---

# Technical Design Summary

The Mobile Service Booking Application uses a modular backend architecture with Django and Django REST Framework. PostgreSQL provides persistent relational storage, Redis supports caching and asynchronous processing, Celery handles background tasks, and WebSockets provide real-time communication.

The application separates responsibilities between Admin, Customer, and Service Provider roles. REST APIs provide access to authentication, profiles, providers, services, search, bookings, payments, notifications, and administration.

Security is enforced using JWT authentication, role-based authorization, object-level permissions, input validation, secure password storage, HTTPS, and protected configuration.

External integrations such as payment gateways, email services, push notifications, mapping services, Redis, Celery, and WebSockets can extend the application's functionality while keeping the core system modular and maintainable.
