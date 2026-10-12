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

Remaining work includes:
- Integrate and test a bounded Redis lock for a suitable business operation.
- Test and document application behavior when Redis is unavailable.
- Review logging and observability for critical application components.
- Repeat concurrency and performance tests and record the results.
- Review the working tree before committing changes.
# Caching Strategy

## 1. Caching Objectives

Redis is used to reduce repeated database queries, improve API response times, and reduce load on PostgreSQL. Cache entries should have defined expiration periods and invalidation rules.

The PostgreSQL database remains the authoritative source for persistent application data.

## 2. What Should Be Cached?

| Data | Caching Strategy | Suggested TTL | Invalidation |
|---|---|---|---|
| Popular services | Cache frequently requested service-list responses | 60 seconds | Invalidate when a service is created, updated, or deleted |
| Service categories | Cache category lists that change infrequently | 5–15 minutes | Invalidate when a category is created, updated, or deleted |
| User session data | Cache only suitable session or authentication-related data | Based on session expiry | Invalidate on logout, expiration, or relevant security changes |
| Frequently accessed data | Cache stable, read-heavy data such as public service details | 1–5 minutes | Invalidate when the underlying data changes |
| Bookings and payments | Avoid treating cached values as authoritative | Not applicable by default | Read current database state for critical operations |

TTL values are initial recommendations, not measured performance requirements. They should be adjusted using actual access patterns, freshness requirements, and performance tests.

Sensitive information, including passwords, access tokens, and payment secrets, must not be cached casually. Any session or authentication cache must use appropriate access controls, expiration, and invalidation.

## 3. Time to Live (TTL)

Time to Live (TTL) defines how long a cached entry remains valid before it expires.

For example, a service-list cache may use a TTL of 60 seconds. Repeated requests within that period can reuse the cached result. After expiration, the application obtains fresh data and caches it again.

Benefits include:

- Limiting how long cached data can remain stale.
- Automatically removing expired entries.
- Reducing repeated database queries.

TTL does not guarantee immediate freshness. If data changes before the TTL expires, invalidation may be necessary.

## 4. Cache Invalidation

Cache invalidation removes or refreshes cached data after the underlying database data changes.

For service listings, the application should invalidate affected cache entries after successful service creation, update, or deletion.

Recommended practices:

1. Perform the database operation successfully before invalidating its cache.
2. Invalidate all relevant cache variants, including entries for different query parameters or pagination.
3. Use consistent cache-key naming.
4. Handle cache failures without accidentally reporting a failed database write when the database transaction actually succeeded.
5. Where strict coordination is required, use transaction-aware invalidation or a reliable post-commit mechanism.

Cache invalidation must cover every code path that changes the underlying data, including administrative operations and background tasks.

## 5. Cache Stampede

A cache stampede occurs when a popular cache entry expires and many simultaneous requests attempt to regenerate it. This can send a sudden burst of queries to PostgreSQL.

Mitigation strategies include:

- **Distributed locking:** Allow one worker to regenerate a particular cache entry while other workers wait briefly or use a permitted fallback.
- **TTL jitter:** Add a small random variation to expiration times so many entries do not expire simultaneously.
- **Stale-while-revalidate:** Serve a previously cached value briefly while one worker refreshes it, where the data freshness requirements allow this.
- **Request coalescing:** Combine concurrent requests for the same missing cache key into one regeneration operation.
- **Monitoring:** Track cache misses, regeneration duration, Redis errors, and database load.

A lock should have a bounded expiry and safe release behavior. It must not remain held indefinitely if a worker crashes.

## 6. Cache Consistency

Cache consistency describes how closely cached data reflects the current database state.

This backend uses PostgreSQL as the source of truth and Redis as a performance optimization. Cache invalidation and expiration reduce staleness, but they do not automatically provide strong consistency.

For public service listings, short-lived eventual consistency may be acceptable. For booking status, payment status, authorization decisions, and other critical operations, the application should validate against authoritative data and must not rely solely on potentially stale cache entries.

When using a transaction, cache invalidation should occur only after the database changes have committed successfully. If invalidation fails, monitoring and a recovery mechanism should help prevent stale data from persisting unnoticed.

## 7. Testing and Monitoring

Validate the caching strategy with automated tests for:

- Cache miss followed by cache hit.
- Expiration after the configured TTL.
- Invalidation after service creation, update, and deletion.
- Concurrent requests for the same uncached resource.
- Redis unavailability and recovery behavior.
- Response correctness after cached data changes.

Monitor cache hit rate, miss rate, eviction count, Redis memory use, regeneration latency, and PostgreSQL query load.

Performance improvements should be demonstrated by comparing repeated requests with caching disabled and enabled under equivalent test conditions.