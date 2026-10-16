# Scalable Mobile Backend Architecture

## Objective

Design a scalable backend for a mobile application targeting one million users. The system must support service search, bookings, payments, notifications, provider communication, and real-time updates.

The architecture separates critical synchronous operations from background processing, protects important business data, and supports horizontal scaling. One million users is a design target, not a verified capacity claim; actual capacity must be established through representative load testing.

## 1. Architecture Diagram

```text
                    Mobile Application
                            |
                            v
                     Load Balancer
                            |
                            v
                       API Gateway
                            |
                            v
              Django REST API (Multiple Instances)
                            |
            +---------------+----------------+
            |               |                |
            v               v                v
       Auth Logic      Booking Logic     Payment Logic
            |               |                |
            +---------------+----------------+
                            |
                +-----------+-----------+
                |                       |
                v                       v
          PostgreSQL                  Redis
       Authoritative Data        Cache / Coordination
                |
                v
       Transactional Business Data

Django API
    |
    +----> Redis / Celery Broker
                 |
                 v
           Celery Workers
                 |
       +---------+----------+
       |         |          |
       v         v          v
 Notifications  Emails   Background Jobs
       |
       v
 Push Notification Provider

          Django Channels / WebSockets
                       |
                       v
              Real-Time Updates
           to Authorized Clients
```

**Diagram note:** The load balancer, API gateway, and multiple application instances describe the proposed production architecture. Their actual deployment must be verified separately. Redis is used for caching and coordination, while PostgreSQL remains the authoritative store for critical business data.

## 2. Component Responsibilities

- **Load Balancer:** Distributes incoming requests across healthy application instances. Health checks and deployment configuration determine which instances receive traffic.
- **API Gateway:** Provides a central entry point for routing, request limits, and security policies. A dedicated gateway must be deployed and configured if this responsibility is to be handled by separate infrastructure.
- **Django REST API:** Handles business logic, authentication, permissions, input validation, and API responses.
- **Authentication:** Manages user registration, login, and JWT-based authentication.
- **Booking Logic:** Manages booking creation, availability validation, status transitions, and booking consistency.
- **Payment Logic:** Integrates with the payment provider, records payment state, and validates payment webhooks.
- **Notification Logic:** Coordinates notifications triggered by booking and service events.
- **PostgreSQL:** Stores users, providers, services, bookings, payments, and other persistent application records.
- **Redis:** Caches service listings and supports configured cache, throttling, and coordination use cases.
- **Celery:** Processes background tasks, including notification-related work.
- **Django Channels / WebSockets:** Delivers real-time events to authenticated and authorized customers and providers.
- **Monitoring and Logging:** Collects operational information needed to investigate errors, latency, database performance, cache behavior, and background task failures.

## 3. Request Flow

1. The mobile application sends an API request.
2. In the proposed production deployment, the load balancer forwards the request to a healthy Django instance through the configured entry point.
3. Django authenticates the user and validates the request.
4. The relevant application logic processes the operation.
5. For service-list requests, Django checks the configured Redis cache.
6. On a cache hit, the cached response data can be returned without repeating the database query. On a cache miss, Django queries PostgreSQL and caches the result according to the configured policy.
7. Booking and payment changes are persisted to PostgreSQL using appropriate transaction and integrity controls.
8. Background work is submitted to Celery where asynchronous processing is appropriate.
9. Authorized WebSocket clients receive applicable real-time events.
10. Django returns the HTTP response to the mobile application.

The exact sequence depends on the endpoint. Not every request needs Redis, Celery, or WebSockets.

## 4. Scalability and Reliability

### 4.1 Horizontal Scaling

- Run multiple Django application instances behind a load balancer when required.
- Keep application instances stateless where practical so requests can be distributed between instances.
- Scale Celery workers independently according to task volume and processing time.
- Scale WebSocket-serving processes separately from ordinary HTTP traffic when required.
- Size database connections and worker counts together to avoid overwhelming PostgreSQL.

Multiple instances and separate scaling processes are production deployment strategies; they should not be described as deployed unless the corresponding infrastructure has been configured and verified.

### 4.2 Caching Strategy

- Cache frequently requested service listings in Redis.
- Use cache keys that distinguish relevant query parameters.
- Apply a time-to-live (TTL) so cached entries expire.
- Invalidate affected service-list cache entries after service creation, updates, or deletion.
- Test cache misses, cache hits, expiration, and invalidation.
- Measure cold-cache and warm-cache performance under the same conditions.

The current service-list cache is configured with a 60-second timeout. Benchmark results from a local development environment are useful for comparison, but they do not establish production capacity.

### 4.3 Database Consistency

- Keep PostgreSQL as the authoritative store for bookings and payments.
- Use database transactions and constraints to protect critical state changes.
- Use appropriate row locking when concurrent operations could conflict.
- Use idempotency controls to reduce duplicate booking or payment operations.
- Review indexes against real query patterns and execution plans.
- Consider connection pooling and read replicas as production scaling options only after evaluating workload and consistency requirements.

### 4.4 Fault Tolerance

- Configure timeouts for external services.
- Use bounded retries with appropriate backoff for retryable failures.
- Make retried operations safe through idempotency where applicable.
- Handle Redis, database, payment-provider, and task-processing failures explicitly.
- Monitor failed background tasks and ensure important failures can be investigated and recovered.
- Do not treat a successful task enqueue as proof that the task completed or that a payment succeeded.

### 4.5 Performance and Observability

Monitor and evaluate:

- API response latency and error rates.
- PostgreSQL query latency, connection usage, and slow queries.
- Redis availability, cache hit/miss behavior, and latency.
- Celery queue depth, task duration, retries, and failures.
- WebSocket connection counts and disconnects.
- Resource usage under representative concurrent workloads.

Run load tests with realistic request distributions and data volumes before claiming support for one million users. Record the test environment, concurrency, duration, error rate, and measured throughput.

## 5. Asynchronous Architecture

### 5.1 Purpose

Asynchronous processing moves suitable work outside the immediate HTTP request. It allows the API to respond without waiting for every secondary operation to finish.

The application should use synchronous processing for operations that require an immediate, authoritative result and asynchronous processing for work that can safely happen afterward.

### 5.2 Architecture Flow

```text
Mobile Application
        |
        v
Django REST API
        |
        +------> PostgreSQL
        |        Critical business data
        |
        +------> Redis / Celery Broker
                       |
                       v
                 Celery Workers
                       |
          +------------+-------------+
          |            |             |
          v            v             v
    Notifications    Emails     Other Jobs
          |
          v
   Push Notification Provider

Django Channels / WebSockets
        |
        v
Real-Time Events to Authorized Clients
```

Redis acts as the Celery broker when configured as such. Celery workers consume queued tasks and execute them independently of the original request. The precise behavior depends on the task implementation and runtime configuration.

### 5.3 Synchronous vs. Asynchronous Operations

**Suitable for synchronous processing:**

- User authentication and permission checks.
- Request validation.
- Service search and retrieval.
- Booking creation and availability validation.
- Critical booking state changes.
- Payment request validation and persistence of authoritative payment state.

**Suitable for asynchronous processing:**

- Booking-related notification delivery.
- Email and push notification delivery.
- Notifications when a saved service becomes unavailable.
- Reminder processing and scheduled work.
- Image processing or bulk work, when implemented and configured for the relevant workflow.

A task should be moved to a background worker only when its failure and completion behavior are understood. Critical operations must not be considered successful merely because a background task was queued.

### 5.4 Booking and Payment Reliability

- Persist critical booking and payment state in PostgreSQL.
- Use transactions and database constraints to protect consistency.
- Use idempotency controls for operations that may be retried.
- Dispatch follow-up tasks after a database transaction commits, for example by using Django's `transaction.on_commit()` where appropriate.
- Validate payment webhooks and verify their authenticity before changing payment state.
- Make background tasks safe to retry where possible.

For stronger delivery guarantees, a transactional outbox can be considered. An outbox records the event in the same database transaction as the business change, then a separate process publishes it. This reduces the risk of committing a business change while losing the associated event.

The transactional outbox should be treated as a design option unless it has been implemented and tested in the project.

### 5.5 Retries and Failure Handling

Background tasks should have clearly defined failure behavior:

- Apply bounded retries only to errors that may recover.
- Use backoff to avoid repeatedly overwhelming an unavailable dependency.
- Configure appropriate network and operation timeouts.
- Prevent duplicate side effects when a task is retried.
- Record failures and make exhausted retries visible for investigation.
- Monitor queue depth, processing duration, and retry counts.

Retry policies, monitoring dashboards, and recovery workflows must be documented as implemented only after they have been verified in the running application.

### 5.6 Existing Implementation and Limitations

The project includes Celery task definitions for:

- `services.tasks.create_notification`
- `services.tasks.notify_saved_customers_service_unavailable`

The project has also used Redis as the Celery broker, with a worker observed connecting to the broker during development.

These task definitions and development observations do not, by themselves, prove that every notification is delivered reliably in production. Worker availability, broker persistence, retries, monitoring, external notification-provider integration, and recovery behavior must be assessed separately.

Features such as a transactional outbox, advanced task monitoring, and stronger delivery guarantees should be treated as future improvements unless their implementation and tests confirm otherwise.

### 5.7 Independent Scaling

- Scale Django API instances according to HTTP traffic.
- Scale Celery workers according to queued task volume and task duration.
- Scale WebSocket processes according to concurrent connections and message throughput.
- Monitor PostgreSQL and Redis capacity as application traffic grows.
- Use load testing to identify the actual bottleneck before increasing infrastructure.

## 6. Production Scaling Roadmap

The following are potential production improvements, not claims that these capabilities are already configured:

1. Deploy multiple Django instances behind a load balancer.
2. Configure health checks, centralized logs, and application metrics.
3. Evaluate PgBouncer or another connection-pooling approach if database connection counts require it.
4. Evaluate PostgreSQL replication and failover requirements based on availability goals.
5. Establish automated backups and periodically test database restoration.
6. Define Celery retry, monitoring, and failed-task recovery policies.
7. Consider a transactional outbox for reliable delivery of important domain events.
8. Run representative load tests and document measured capacity and bottlenecks.

These deployment and database-recovery topics should be documented in more detail in `DATABASE_DESIGN.md` or the appropriate operations documentation.

## 7. Conclusion

This architecture provides a foundation for a scalable, secure, and reliable mobile backend. Django REST Framework handles API requests, PostgreSQL stores authoritative business data, Redis supports caching and configured coordination use cases, Celery processes background tasks, and Django Channels/WebSockets supports real-time communication.

Critical booking and payment operations require database consistency, validation, and idempotency. Secondary work can be processed asynchronously when its failure and retry behavior are handled correctly.

The architecture targets growth toward one million users, but the achievable capacity depends on workload, infrastructure, database performance, cache effectiveness, worker capacity, and operational reliability. Representative load testing and production monitoring are required before claiming that capacity has been achieved.
