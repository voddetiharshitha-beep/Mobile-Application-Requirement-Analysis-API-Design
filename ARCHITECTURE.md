Backend Architecture

1. System Architecture

The backend is a Django REST Framework application that exposes versioned REST APIs under /api/v1/.

Mobile Application / API Client
            |
            v
       Django / DRF
            |
     +------+------+
     |             |
     v             v
   Database     WebSocket
                   |
                Channels
                   |
                 Redis
     |
     +----------------------+
     |                      |
     v                      v
 Business Services        Celery
                            |
                          Redis

Main responsibilities

Django + Django REST Framework: HTTP APIs, authentication, serializers, validation, permissions, and request/response handling.

Database: Persistent storage for users, providers, services, bookings, payments, notifications, and images.

Django Channels: Real-time booking status updates over WebSockets.

Redis: Channel layer for WebSockets, Celery infrastructure, and service-list caching.

Celery: Background processing, especially notification creation.

Service layer: Business logic is separated from API views into dedicated service modules.

2. Application Architecture

The application follows a layered approach:

API / Views
    |
    v
Serializers / Validation
    |
    v
Service Layer
    |
    v
Django Models / Database

Main application components

services/
├── views.py
├── serializers.py
├── models.py
├── urls.py
├── booking_service.py
├── payment_service.py
├── notification_service.py
├── service_service.py
├── tasks.py
├── consumers.py
├── pagination.py
└── exceptions.py

Views

views.py handles HTTP requests, authentication and permissions, serializer usage, service-layer calls, and standardized API responses.

Serializers

serializers.py handles request validation, field validation, business validation directly related to serialized data, and conversion between Django models and API representations.

Service layer

Business operations are separated into dedicated modules:

booking_service.py — booking creation, cancellation, and status transitions.

payment_service.py — payment initiation, processing, and webhook handling.

notification_service.py — dispatching notification tasks.

service_service.py — service creation, update, deletion, and cache invalidation.

This keeps views smaller and reduces duplicated business logic.

3. Database Architecture

The database stores the core business entities and their relationships.

Main relationships

User
 |
 +---- UserProfile
 |
 +---- Provider
 |
 +---- Booking
 |
 +---- Notification

Provider
 |
 +---- ProviderProfile
 |
 +---- Service
 |
 +---- Booking

Category
 |
 +---- Service

Service
 |
 +---- ServiceImage
 |
 +---- Booking

Booking
 |
 +---- Payment
 |
 +---- Notification

Main models

User

Django's built-in authentication user model is used for usernames, email, passwords, authentication, customer identity, and provider account association.

Provider

A provider is associated with a Django user through a one-to-one relationship. Providers own services and are associated with bookings.

Category

Stores service categories.

Service

Stores service name, description, location, price, active status, category, provider, and timestamps.

Booking

Stores customer, provider, service, booking date/time, amount, booking status, and timestamps. Booking status transitions are controlled by the model's can_transition_to() method.

Payment

Each booking has one payment through a one-to-one relationship. Mock payment statuses include PENDING, SUCCESS, FAILED, and REFUNDED.

Notification

Stores user notifications related to booking events, including booking creation, successful payment, confirmation, provider start, completion, and cancellation.

ServiceImage

Stores images belonging to services.

UserProfile

Stores optional user profile information such as the profile image.

4. Authentication

The API uses Django REST Framework with JWT-based authentication.

Authentication endpoints are versioned under:

/api/v1/token/
/api/v1/token/refresh/

Authentication flow

Client
  |
  | username + password
  v
JWT Token Endpoint
  |
  +---- Access Token
  |
  +---- Refresh Token
          |
          v
Authenticated API Requests

Protected endpoints use IsAuthenticated. Public endpoints such as registration use AllowAny.

Object-level authorization is also applied where required. Examples include providers managing their own services, customers accessing their own bookings, and customers being prevented from processing another user's payment.

5. WebSocket Architecture

Django Channels provides real-time communication for booking status updates.

The WebSocket endpoint follows:

/ws/bookings/<booking_id>/

WebSocket flow

Customer
   |
   | WebSocket connection
   v
Django ASGI
   |
   v
BookingStatusConsumer
   |
   v
Redis Channel Layer
   |
   v
Connected customer

When a booking status changes, the booking service sends an event to the booking-specific channel group:

booking_<booking_id>

Example event:

{
    "booking_id": "booking-uuid",
    "status": "in_progress",
    "message": "Booking status changed to in_progress."
}

Django's ASGI configuration allows the application to handle both HTTP requests and WebSocket connections.

6. Celery Architecture

Celery is used for background notification processing.

Notification flow

Django API
    |
    v
Business Service
    |
    v
send_notification()
    |
    v
Celery Task
    |
    v
Redis
    |
    v
Celery Worker
    |
    v
Create Notification
    |
    v
Database

The notification service dispatches the task asynchronously using:

create_notification.delay(...)

This keeps notification processing outside the main API request path.

Celery worker

The worker can be started with:

celery -A config worker --loglevel=info --pool=solo

7. Redis Usage

Redis is used for three main purposes.

7.1 WebSocket channel layer

Django Channels uses Redis to communicate events between application processes and WebSocket connections.

Booking status update
        |
        v
Redis Channel Layer
        |
        v
WebSocket Consumer
        |
        v
Customer

7.2 Celery infrastructure

Redis is used by Celery for asynchronous task communication.

Django
  |
  v
Redis
  |
  v
Celery Worker

7.3 Service-list caching

Redis is used to cache service-list API responses. The cache key is based on the requested API path:

service_list:<request path>

The cache timeout is configurable through Django settings. When services are created, updated, or deleted, the service layer clears the relevant service-list cache.

Redis summary

                  Redis
                 /  |  \
                /   |   \
               v    v    v
          Channels Celery Cache
             |       |      |
          WebSocket Tasks Service Lists

8. API Response Architecture

Successful non-paginated API responses follow:

{
    "success": true,
    "message": "Operation successful.",
    "data": {}
}

Error responses follow:

{
    "success": false,
    "message": "Validation failed.",
    "error_code": "VALIDATION_ERROR",
    "data": {}
}

Paginated endpoints retain Django REST Framework's pagination structure:

{
    "count": 20,
    "next": "...",
    "previous": null,
    "results": []
}

HTTP 204 No Content responses remain empty.

9. Request Flow

A typical booking request follows:

Client
  |
  v
/api/v1/services/bookings/
  |
  v
Authentication
  |
  v
Serializer Validation
  |
  v
Booking Service
  |
  +----> Database
  |
  +----> Celery Notification
  |
  +----> WebSocket Event
  |
  v
Standard API Response

This separates authentication, validation, business logic, persistence, background processing, and real-time communication.

10. Architecture Summary

The backend uses:

Django for the core web framework.

Django REST Framework for REST APIs.

JWT authentication for protected API access.

Django ORM for database access.

Django Channels for WebSockets.

Redis for WebSocket channel communication, Celery infrastructure, and caching.

Celery for background notification processing.

Service modules for business logic separation.

DRF serializers for request validation and API representation.

Custom exception handling for standardized error responses.

The architecture separates API handling, validation, business logic, persistence, background processing, caching, and real-time communication.