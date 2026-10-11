# Redis Caching and Scalability Architecture

## 1. Objective

This document describes the Redis caching strategy, cache invalidation,
performance measurements, rate-limiting review, concurrent-request testing,
and distributed-lock testing for the Django REST Framework mobile service
booking API.

## 2. Redis Architecture

Redis is configured as the Django cache backend through `django-redis`.

- Application: Django REST Framework
- Cache backend: `django_redis.cache.RedisCache`
- Connection: Environment-based Redis host and port
- Django cache database: Redis database 2
- Service-list cache timeout: 60 seconds
- Cached resource: Service-list API responses

Redis is also used by the project's asynchronous notification and Channels
infrastructure. The cache and other Redis workloads should be monitored and
configured appropriately for deployment.

## 3. Cache Strategy

The service-list endpoint uses the cache key pattern:

`service_list:{request.get_full_path()}`

Different query strings and pagination parameters can have separate cache
entries.

### Cache miss

1. The API receives a service-list request.
2. Django checks Redis for the corresponding cache key.
3. If the entry is absent, the view obtains the response data.
4. The response is stored in Redis with the configured timeout.
5. The response is returned to the client.

### Cache hit

1. The API receives a repeated request.
2. Django finds the matching cached response.
3. The cached response is returned without repeating the service-list
   database queries.

## 4. TTL and Cache Invalidation

The service-list cache timeout is configured as 60 seconds.

The service layer invalidates service-list cache entries after service
creation, update, and deletion.

Invalidation uses the `service_list:*` key pattern with the Redis cache
backend's `delete_pattern()` method.

This prevents normal service mutations from leaving old service-list
responses cached until the TTL expires. The TTL provides a fallback for
eventual expiration.

## 5. Performance Comparison

Test endpoint:

`GET /api/v1/services/?page=1`

Latest recorded local benchmark:

| Metric | Cold cache | Warm cache average |
|---|---:|---:|
| Response time | 183.09 ms | 3.63 ms |
| Database queries | 2 | 0 |
| HTTP status | 200 | 200 |

The five warm-request times were:

- 2.80 ms
- 2.78 ms
- 3.47 ms
- 6.27 ms
- 2.83 ms

The measured average response-time reduction was approximately 98.02%.

These results are from a local benchmark and are not a guarantee of
production performance. Results can vary with system load, cache state,
database state, and the test environment.

## 6. Redis Distributed-Lock Test

Redis lock support was verified using the configured `django-redis`
cache backend.

An automated test is located at:

`services/tests/test_redis_lock.py`

The test uses a unique Redis key and a 30-second lock timeout.

| Check | Result |
|---|---|
| First client acquires the lock | PASS |
| Second client cannot acquire the held lock | PASS |
| Second client acquires the lock after release | PASS |
| Automated Django test | PASS |

Run the test with:

`python manage.py test services.tests.test_redis_lock -v 2`

This test verifies basic lock acquisition, contention, and release against
Redis. It does not establish that a production business operation is
protected by a Redis lock.

The booking workflow currently has separate database-level safeguards:
database transactions, booking idempotency constraints, and row locking
for booking-status updates. A Redis lock has not yet been integrated into
a production business operation.

Before integration, the chosen operation must have a clearly defined
concurrency risk, lock key, timeout, release behavior, failure handling,
and database consistency strategy. Redis locking must not replace database
constraints or transaction safeguards.

## 7. Concurrent-Request Testing

Test endpoint:

`GET /api/v1/services/?page=1`

The service-list cache was populated before the concurrent requests were
issued. The local test used 20 APIClient requests across 5 worker threads.

| Metric | Result |
|---|---:|
| Total requests | 20 |
| Worker threads | 5 |
| Successful HTTP 200 responses | 20 |
| Failed requests | 0 |
| Average response time | 28.41 ms |
| Fastest response | 2.61 ms |
| Slowest response | 80.52 ms |

All 20 requests returned HTTP 200 in this run.

This is a local concurrent APIClient test, not a full network-level load
test. Repeated runs, higher concurrency, real HTTP traffic, and latency
percentiles are needed to evaluate production capacity.

## 8. Rate-Limiting Review

The project uses Django REST Framework scoped throttling.

Configured rates to verify against settings and the corresponding views:

- Login: 5 requests per minute
- Registration: 5 requests per minute
- Password-related operations: 5 requests per minute
- Booking: 5 requests per minute
- Payment: 5 requests per minute

The throttle scopes and view assignments should remain consistent, and
each protected endpoint should have independent positive and negative
tests.

Rate throttling is an application-level safeguard. It does not replace
authentication, authorization, payment security, or infrastructure-level
protection.

## 9. Operational Considerations

- Keep Redis credentials and connection settings in environment variables.
- Monitor Redis availability, memory usage, latency, and evictions.
- Choose an appropriate Redis memory policy for the deployment workload.
- Review cache-key growth and invalidation behavior.
- Avoid caching sensitive or user-specific responses under shared keys.
- Test and document application behavior when Redis is unavailable.
- Use repeated load tests and latency-percentile measurements before
  production deployment.
- Review Redis authentication, networking, persistence, and high
  availability requirements.
- Ensure distributed locks have bounded timeouts and safe release behavior.
- Retain database constraints and transactions for critical business rules.

## 10. Conclusion and Remaining Work

The local implementation demonstrates service-list caching, a 60-second
TTL, cache invalidation after service mutations, reduced warm-cache latency,
basic Redis lock contention, and successful handling of 20 concurrent
service-list requests.

The standalone Redis lock test passes, but a production business operation
has not yet been integrated with a Redis lock. That requirement remains
open until a suitable operation is selected, implemented safely, and tested
under concurrent requests.

Further work includes confirming rate-limit coverage, testing Redis failure
behavior, reviewing the modified backup file, and completing focused
business-operation concurrency testing before committing the changes.
'@ | Set-Content .\REDIS_ARCHITECTURE.md -Encoding utf8
