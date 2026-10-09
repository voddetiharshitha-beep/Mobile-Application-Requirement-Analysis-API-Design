# Microservices Concepts & Django Service Decomposition

## 1. Objective

The objective of this task is to understand monolithic, modular monolith, and microservices architectures and evaluate how the existing Django REST Framework mobile service-booking backend could evolve into independently deployable services.

The design identifies potential service boundaries, database ownership, API communication, synchronous and asynchronous workflows, and failure-handling strategies.

The recommended approach is to maintain the existing modular Django application until independent deployment, scaling, or organizational requirements justify extracting specific services.

## 2. Monolithic Architecture

A monolithic architecture packages the main application functionality into one deployable application.

In a Django monolith, authentication, service management, bookings, payments, and notifications may be implemented in different Django apps or Python modules but deployed together.

### Advantages

* Simple deployment and development.
* Straightforward function calls between application modules.
* Easier database transactions within a single database.
* Fewer network communication failures.
* Lower operational and infrastructure complexity.

### Disadvantages

* The application can become difficult to maintain if modules are tightly coupled.
* Most changes are deployed through the same application release.
* Scaling one resource-intensive component independently can be difficult.
* Poorly separated business logic can make testing and maintenance harder.

### Application to this project

The existing Django backend uses a shared application structure with service modules for bookings, payments, and service management. This provides a useful foundation for separating responsibilities without introducing network boundaries prematurely.

## 3. Modular Monolith Architecture

A modular monolith is a single deployable application organized into clearly separated business modules.

Each module has a defined responsibility and communicates with other modules through functions or explicit interfaces instead of relying on unrelated internal implementation details.

### Proposed module organization

* **Identity and access:** Users, authentication, and authorization.
* **Service catalog:** Providers, service listings, categories, and service images.
* **Booking:** Booking creation, cancellation, and lifecycle management.
* **Payment:** Payment initiation, processing, and payment-provider integration.
* **Notifications:** Notification records and delivery workflows.
* **Shared infrastructure:** Configuration, logging, caching, and background-task infrastructure.

### Advantages

* Clear separation of business responsibilities.
* Easier unit testing and code maintenance.
* Lower operational complexity than microservices.
* A practical path toward future service extraction.

### Recommendation

The modular monolith is the recommended current architecture for this project. Existing service modules should remain well-defined and avoid unnecessary cross-module dependencies.

## 4. Microservices Architecture

Microservices architecture separates business capabilities into independently deployable services.

Each service owns its business logic, exposes an explicit communication interface, and manages its own data. Services communicate over a network using APIs or messaging.

### Advantages

* Independent deployment and scaling.
* Better isolation of some failures.
* Teams can develop and release services independently.
* Different services can evolve their implementation independently.

### Disadvantages

* Network calls introduce latency and failure modes.
* Distributed transactions and data consistency become more complex.
* Monitoring, authentication, deployment, and service discovery require additional infrastructure.
* Integration testing and debugging are more difficult.
* Operating multiple services increases cost and maintenance effort.

Microservices should be introduced when there is a clear business or operational benefit, not simply because the application has multiple Django apps.

## 5. Existing Backend Modules

The current backend includes the following relevant modules and capabilities.

| Existing component                                   | Responsibility                                               |
| ---------------------------------------------------- | ------------------------------------------------------------ |
| Django authentication and user/profile functionality | User identity, login, permissions, and profile management    |
| `booking_service.py`                                 | Booking creation, cancellation, and status updates           |
| `payment_service.py`                                 | Payment initiation, processing, and webhook handling         |
| `stripe_service.py`                                  | Stripe integration                                           |
| `service_service.py`                                 | Service creation, updating, deletion, and cache invalidation |
| `notification_service.py`                            | Notification-related operations                              |
| `idempotency_service.py`                             | Idempotent request handling                                  |
| `media_service.py`                                   | Media-related operations                                     |
| Celery tasks                                         | Supported background operations                              |
| Channels/WebSockets                                  | Real-time booking status communication                       |

These components currently belong to the existing Django application. Their presence does not mean that each is already an independent microservice.

## 6. Proposed Independent Services

The following service boundaries are proposed for architectural analysis.

### 6.1 Identity Service

**Responsibilities**

* User registration and identity management.
* Authentication and token-related workflows.
* User roles and account status.
* Authentication-related security policies.

**Data ownership**

Owns user identity, credentials, roles, and account records.

**Communication**

Provides authentication endpoints or token-validation capabilities to other services.

The initial implementation may continue using Django authentication and SimpleJWT. An independent identity service is only justified if deployment or identity-management requirements warrant it.

### 6.2 Service Catalog Service

**Responsibilities**

* Service listings and categories.
* Provider service information.
* Service availability and pricing.
* Service images and catalog-related queries.

**Data ownership**

Owns catalog data, provider service listings, categories, and associated catalog media metadata.

**Communication**

Exposes REST APIs for searching, retrieving, creating, and updating service listings.

### 6.3 Booking Service

**Responsibilities**

* Booking creation and cancellation.
* Booking status transitions.
* Booking history and ownership checks.
* Booking idempotency and booking-related workflow coordination.

**Data ownership**

Owns booking records, booking lifecycle state, and booking idempotency records.

**Communication**

Exposes REST APIs to mobile clients and publishes booking lifecycle events for other services.

### 6.4 Payment Service

**Responsibilities**

* Payment initiation and processing.
* Stripe integration.
* Payment webhook verification.
* Payment status and payment-related idempotency.
* Refund and payment-failure workflows.

**Data ownership**

Owns payment records, provider references, payment statuses, and payment-processing metadata.

**Communication**

Exposes payment APIs and receives verified payment-provider webhooks. It publishes payment status events for interested services.

### 6.5 Notification Service

**Responsibilities**

* Notification creation and delivery.
* Booking and payment notifications.
* Notification retry handling.
* Delivery status and relevant notification history.

**Data ownership**

Owns notification records, delivery attempts, and notification delivery state.

**Communication**

Consumes booking and payment events asynchronously and delivers notifications through the configured delivery channels.

## 7. Proposed Communication Architecture

The following diagram describes the proposed future architecture, not the current deployment.

```text
                  Mobile Application
                          |
                          v
                 API Gateway / Entry
                          |
          +---------------+---------------+
          |               |               |
          v               v               v
    Identity API     Catalog API      Booking API
          |               |               |
          v               v               v
    Identity DB      Catalog DB       Booking DB
                                          |
                                          | Payment request
                                          v
                                     Payment API
                                          |
                                          v
                                      Payment DB
                                          |
                                          v
                                    Stripe API
                                          |
                                          v
                                  Payment Webhook

       Booking and Payment Services
                    |
                    v
             Message Broker
                    |
                    v
            Notification Service
                    |
                    v
              Notification DB
```

### Communication principles

* Mobile clients communicate through a defined API entry point.
* Each service owns its business rules and data.
* Services use REST APIs when an immediate response is required.
* Services publish events when other services need to react to completed business actions.
* Notification delivery is asynchronous so a temporary delivery failure does not need to block a booking request.
* WebSockets may be retained for real-time booking status updates where appropriate.

An API gateway is a proposed architectural component. The current Django application does not need to introduce a separate gateway merely to document this design.

## 8. Database Ownership

The proposed microservices design follows the database-per-service principle.

| Service         | Owned data                                                                      |
| --------------- | ------------------------------------------------------------------------------- |
| Identity        | Users, credentials, roles, and account information                              |
| Service Catalog | Categories, service listings, provider catalog data, and service image metadata |
| Booking         | Bookings, booking lifecycle state, and booking idempotency records              |
| Payment         | Payments, payment provider references, and payment processing state             |
| Notification    | Notifications, delivery attempts, and delivery status                           |

### Database rules

1. A service is the authoritative owner of its business data.
2. Other services must not directly update another service's tables.
3. Cross-service information is obtained through APIs or events.
4. Services should not rely on cross-database SQL joins.
5. Each service should manage its schema and migrations independently.
6. Separate databases or schemas may be introduced gradually, but separate schemas alone do not provide complete service isolation.

The current application uses a shared Django persistence layer. This proposed ownership model would need to be implemented as part of any actual microservice extraction.

## 9. API Communication Design

REST APIs are suitable for synchronous communication where the caller needs an immediate response.

Illustrative future endpoints include:

### Identity Service

* `POST /api/v1/auth/register/`
* `POST /api/v1/auth/token/`
* `POST /api/v1/auth/token/refresh/`

### Service Catalog Service

* `GET /api/v1/services/`
* `GET /api/v1/services/{service_id}/`

### Booking Service

* `POST /api/v1/bookings/`
* `GET /api/v1/bookings/{booking_id}/`
* `POST /api/v1/bookings/{booking_id}/cancel/`

### Payment Service

* `POST /api/v1/payments/`
* `GET /api/v1/payments/{payment_id}/`
* `POST /api/v1/payments/webhook/`

These endpoints illustrate possible service contracts. They do not imply that new routes or separate deployments have already been implemented.

### API security

* Authenticate users through the approved token-validation mechanism.
* Enforce service-level authorization and ownership checks.
* Use HTTPS for external and inter-service communication.
* Keep Stripe secrets and service credentials in environment-based secret configuration.
* Validate webhook signatures or shared secrets and reject unauthorized events.
* Apply rate limits and request validation.
* Avoid passing credentials or sensitive payment information in logs.

## 10. Synchronous and Asynchronous Communication

### Synchronous communication

Synchronous communication waits for a response.

Examples:

* A mobile client requests the service catalog.
* A mobile client creates a booking.
* A client retrieves booking details.
* A payment service calls Stripe when it needs an immediate response from the payment provider.

**Benefits:** Immediate results and straightforward request-response semantics.

**Risks:** Latency, timeouts, and dependency on the availability of the called service.

### Asynchronous communication

Asynchronous communication publishes an event or task that can be processed later.

Examples:

* A booking event triggers notification delivery.
* A verified payment result produces a payment-status event.
* A notification service retries a temporary delivery failure.
* A booking status change is propagated to interested consumers.

**Benefits:** Reduced coupling and improved resilience to temporary downstream failures.

**Risks:** Delayed processing, duplicate delivery, event ordering problems, and eventual consistency.

### Recommended event examples

```text
BookingCreated
BookingCancelled
PaymentInitiated
PaymentSucceeded
PaymentFailed
NotificationRequested
```

Events should include stable identifiers, event types, timestamps, and the relevant business entity ID. They should not include passwords, access tokens, or unnecessary sensitive data.

A message broker can be introduced when independent services are deployed. The existing Celery and Redis infrastructure may support some background workflows, but broker selection and durability guarantees should be evaluated before relying on it for business-critical events.

## 11. Payment and Booking Consistency

Booking and payment records would belong to different services in the proposed architecture. A single database transaction could no longer atomically update both services' databases.

A possible workflow is:

1. The Booking Service creates a booking in a pending state.
2. The Booking Service emits a `BookingCreated` event or requests payment initiation.
3. The Payment Service creates a payment record and initiates the payment-provider workflow.
4. Stripe processes the payment.
5. The Payment Service verifies the webhook or obtains a trusted payment result.
6. The Payment Service publishes a payment result event.
7. The Booking Service consumes the event and updates the booking state.
8. The Notification Service consumes relevant events and sends notifications.

### Consistency safeguards

* Use idempotency keys for booking creation and payment initiation.
* Verify payment webhooks before changing payment status.
* Make event consumers safe to execute more than once.
* Track payment and booking state transitions.
* Use retry policies with limits and backoff.
* Consider a transactional outbox to avoid losing events between a database commit and event publication.
* Use compensating actions or a saga-style workflow for operations that span services.

A payment timeout must not automatically be treated as proof that the payment failed. The payment status should be reconciled with the payment provider before attempting potentially duplicate charges.

## 12. Failure Scenarios and Recovery

| Failure scenario                  | Potential impact                                      | Recommended handling                                                                  |
| --------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Identity Service unavailable      | Users may be unable to authenticate or refresh tokens | Use bounded timeouts, monitoring, and safe token-validation strategies                |
| Catalog Service unavailable       | Service search and detail requests fail               | Apply timeouts, limited retries, and carefully scoped caching where appropriate       |
| Booking Service unavailable       | New bookings and booking updates cannot complete      | Return a controlled error; preserve request idempotency                               |
| Payment provider timeout          | Payment result is uncertain                           | Reconcile with Stripe and avoid duplicate charges                                     |
| Payment webhook duplicated        | Payment event may be processed more than once         | Verify signatures and deduplicate using stable event/provider identifiers             |
| Message broker unavailable        | Events cannot be delivered promptly                   | Persist events where needed, retry publication, and monitor queue health              |
| Notification provider unavailable | Notifications are delayed                             | Retry with backoff and use a dead-letter or failed-delivery mechanism where supported |
| Database unavailable              | A service cannot reliably access its owned records    | Fail safely, monitor database health, and recover without bypassing consistency rules |
| Network timeout between services  | A caller may not know whether the operation completed | Use timeouts, idempotency keys, and status reconciliation                             |
| Event delivered out of order      | State changes may be applied incorrectly              | Validate current state and use event versions or sequence numbers where needed        |

### Resilience practices

* Set explicit connection and response timeouts.
* Retry only appropriate transient failures.
* Use exponential backoff and retry limits.
* Introduce circuit breakers where justified.
* Record correlation IDs for cross-service requests.
* Monitor error rates, queue depth, and processing delays.
* Use dead-letter handling for messages that repeatedly fail.
* Define health checks and service recovery procedures.

## 13. When Should This Django Monolith Become Microservices?

The application should remain a modular monolith while it can be maintained, tested, deployed, and scaled effectively as one unit.

Service extraction becomes more attractive when there is a demonstrated need for:

* Independent deployment schedules.
* Independent scaling for a specific workload.
* Stronger fault isolation.
* Separate ownership by teams.
* Different security or compliance boundaries.
* Independent availability or operational requirements.

The decision should consider the additional cost of distributed tracing, network security, message delivery, deployment automation, data consistency, and incident response.

### Suggested migration order

1. Keep the existing modular Django application working.
2. Establish clear interfaces and ownership for each business module.
3. Improve tests and remove unnecessary cross-module dependencies.
4. Select one capability with a clear independent scaling or deployment benefit.
5. Extract it behind an explicit API or event contract.
6. Give it ownership of its data and migrations.
7. Add observability, authentication, retries, and recovery procedures.
8. Validate the extracted service in staging before migrating production traffic.
9. Repeat only when there is a clear benefit.

Payment and identity require particular care because security, consistency, and failure recovery are critical. The easiest service to extract is not necessarily the most important service to extract first.

## 14. Implementation Scope

This document defines a proposed architecture. It does not claim that independent authentication, booking, payment, catalog, or notification deployments have already been implemented.

The existing Django application, service modules, database configuration, background tasks, and API routes remain the current implementation unless separately changed and tested.

The immediate deliverable is the architecture analysis, proposed communication diagram, service ownership model, API design, and failure-handling plan.

## 15. Acceptance Criteria

| Task                                                | Completion evidence                                               |
| --------------------------------------------------- | ----------------------------------------------------------------- |
| Study monolithic architecture                       | Architecture and trade-offs documented                            |
| Study modular monolith architecture                 | Module boundaries and benefits documented                         |
| Study microservices architecture                    | Independent deployment and distributed-system concerns documented |
| Identify current backend modules                    | Existing Django modules reviewed                                  |
| Select possible independent services                | Identity, Catalog, Booking, Payment, and Notification proposed    |
| Draw communication architecture                     | Proposed service communication diagram included                   |
| Define database ownership                           | Data ownership assigned to each proposed service                  |
| Define API communication                            | Illustrative REST contracts included                              |
| Identify synchronous and asynchronous communication | Request-response and event-driven workflows documented            |
| Identify failure scenarios                          | Failure matrix and resilience practices included                  |
| Document the proposed architecture                  | This document provides the architecture proposal                  |

## 16. Conclusion

The current Django backend already has a useful foundation for modular architecture. Its booking, payment, service-management, notification, media, and validation components provide logical boundaries for future design decisions.

The recommended approach is to retain a well-structured modular monolith until a specific business or operational need justifies extracting a capability into an independently deployed service.

If extraction becomes necessary, each service should have a clearly defined responsibility, explicit API or event contracts, ownership of its data, and documented failure-recovery behavior.

This approach avoids premature distributed-system complexity while preserving a practical path toward microservices when they provide measurable value.
