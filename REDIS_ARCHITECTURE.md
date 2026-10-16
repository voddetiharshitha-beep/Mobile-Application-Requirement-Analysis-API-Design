# Redis Caching and Scalability Architecture

## 1. Objective

This document describes the Redis architecture, service-list caching, TTL, cache invalidation, performance measurements, rate-limiting review, concurrent-request testing, distributed-lock testing, and operational considerations for the Django REST Framework mobile service booking API.

## 2. Redis Architecture

Redis is configured as the Django cache backend through `django-redis`.

- Application: Django REST Framework
- Cache backend: `django_redis.cache.RedisCache`
- Connection: Environment-based Redis host and port
- Django cache database: Redis database 2
- Service-list cache timeout: 60 seconds
- Cached resource: Service-list API responses

Redis is also used by the project's asynchronous notification and Channels infrastructure. The cache and other Redis workloads should be monitored and configured appropriately for deployment.

PostgreSQL remains the authoritative source for persistent application data.

## 3. Service-List Cache Strategy

The service-list endpoint uses this cache-key pattern:

`service_list:{request.get_full_path()}`

Different query strings and pagination parameters can have separate cache entries.

### Cache miss

1. The API receives a service-list request.
2. Django checks Redis for the corresponding cache key.
3. If the entry is absent, the view obtains the response data.
4. The response is stored in Redis with the configured timeout.
5. The response is returned to the client.

### Cache hit

1. The API receives a repeated request.
2. Django finds the matching cached response.
3. The cached response is returned without repeating the service-list database queries.

### Cache invalidation

The service layer invalidates service-list cache entries after service creation, update, and deletion.

Invalidation uses the `service_list:*` key pattern with the Redis cache backend's `delete_pattern()` method.

This prevents normal service mutations from leaving old service-list responses cached until the TTL expires. The TTL provides a fallback for eventual expiration. Cache invalidation should also cover other code paths that change service data.

## 4. TTL and Cache Consistency

The service-list cache timeout is configured as 60 seconds.

Time to Live (TTL) defines how long a cached entry remains valid before it expires. Repeated requests within that period can reuse the cached result. After expiration, the application obtains fresh data and caches it again.

TTL limits how long cached data may remain stale, but it does not guarantee immediate freshness. Explicit invalidation is needed when relevant data changes.

For service listings, short-lived eventual consistency may be acceptable. For booking status, payment status, authorization decisions, and other critical operations, the application must validate against authoritative data rather than relying solely on potentially stale cache entries.

Where transactions are involved, cache invalidation should occur after successful database commit. If invalidation fails, monitoring and recovery mechanisms should help prevent stale data from persisting unnoticed.

## 5. Performance Comparison

**Test endpoint:**

`GET /api/v1/services/?page=1`

The following results were recorded during the latest local benchmark.

| Metric | Cold cache | Warm cache average |
|---|---:|---:|
| Response time | 222.91 ms | 3.82 ms |
| Database queries | 2 | 0 per request |
| HTTP status | 200 | 200 for all five requests |

**Individual warm-request response times:**

- 3.85 ms
- 3.54 ms
- 3.94 ms
- 4.12 ms
- 3.67 ms

The average warm-cache response time was **3.82 ms**, compared with **222.91 ms** for the cold-cache request.

The measured response-time reduction was approximately **98.28%**.

These are local benchmark results, not a guarantee of production performance. Results may vary depending on system load, cache state, database state, and the test environment.

## 6. Redis Distributed-Lock Test

Redis lock support was verified using the configured `django-redis` cache backend.

Automated test:

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

The service-list cache regeneration path also uses a Redis lock to coordinate cache population when the cache is empty. The lock test verifies basic acquisition, contention, and release. These results do not establish correctness under every production workload or failure condition.

**Scope limitation:** Redis distributed locking is not currently integrated into booking or payment business operations. Those workflows rely on their existing database and transaction safeguards, including booking idempotency constraints and row locking for booking-status updates.

Any future business-operation lock should have a clearly defined concurrency risk, lock key, bounded timeout, safe release behavior, failure handling, and database consistency strategy. Redis locking must not replace database constraints or transaction safeguards.

## 7. Concurrent-Request Testing

Test endpoint:

`GET /api/v1/services/?page=1`

### Warm-cache concurrency

The service-list cache was populated before the concurrent requests were issued. The local test used 20 APIClient requests across 5 worker threads.

| Metric | Result |
|---|---:|
| Total requests | 20 |
| Worker threads | 5 |
| Successful HTTP 200 responses | 20 |
| Failed requests | 0 |
| Average response time | 42.00 ms |
| Fastest response | 4.94 ms |
| Slowest response | 172.78 ms |

All 20 requests returned HTTP 200 in this run.

### Cold-cache concurrency

A separate test cleared the service-list cache before launching five concurrent requests using five worker threads.

| Metric | Result |
|---|---:|
| Total requests | 5 |
| Worker threads | 5 |
| Successful HTTP 200 responses | 5 |
| Failed requests | 0 |
| Average response time | 578.31 ms |
| Fastest response | 450.06 ms |
| Slowest response | 672.75 ms |
| Total database queries | 2 |

All five requests succeeded. The first request recorded two database queries, while the other four recorded zero queries. This result is consistent with coordinated cache regeneration during this run, but it does not prove behavior under every load or failure condition.

These are local APIClient benchmarks, not full network-level load tests. Repeated runs, higher concurrency, real HTTP traffic, and latency percentiles are needed to evaluate production capacity.

## 8. Rate-Limiting Review

The project uses Django REST Framework scoped throttling.

Configured rates to verify against settings and the corresponding views:

- Login: 5 requests per minute
- Registration: 5 requests per minute
- Password-related operations: 5 requests per minute
- Booking: 5 requests per minute
- Payment: 5 requests per minute

The throttle scopes, configured rates, and view assignments should remain consistent. Each protected endpoint should have independent positive and negative tests.

Rate throttling is an application-level safeguard. It does not replace authentication, authorization, payment security, or infrastructure-level protection.

## 9. Recommended Caching Strategy

The following table distinguishes the current service-list implementation from recommendations that have not been separately implemented.

| Data category | Recommended strategy | Suggested TTL | Current status and invalidation |
|---|---|---|---|
| Service lists | Cache frequently requested service-list responses | 60 seconds | Implemented and tested; invalidate after service creation, update, and deletion |
| Service categories | Cache category lists that change infrequently | 5–15 minutes | Recommendation; separate cache not confirmed |
| User session data | Use an appropriate session backend and respect session expiry and logout | Based on session expiry | Redis session caching is not explicitly configured |
| Frequently accessed public data | Cache stable, read-heavy data such as public service details | 1–5 minutes | Recommendation; separate cache not implemented |
| Bookings and payments | Do not treat cached values as authoritative | Not applicable by default | Read current database state for critical operations |

TTL values for resources other than the service list are recommendations, not measured performance requirements. They should be adjusted using actual access patterns, freshness requirements, and performance tests.

Sensitive information, including passwords, access tokens, and payment secrets, must not be cached casually. Any session or authentication cache must use appropriate access controls, expiration, and invalidation.

## 10. Cache Stampede Prevention

A cache stampede occurs when a popular cache entry expires and many simultaneous requests attempt to regenerate it. This can send a sudden burst of queries to PostgreSQL.

Potential mitigation strategies include:

- **Distributed locking:** Allow one worker to regenerate a particular cache entry while other workers wait briefly or use a permitted fallback.
- **TTL jitter:** Add a small random variation to expiration times so many entries do not expire simultaneously.
- **Stale-while-revalidate:** Serve a previously cached value briefly while one worker refreshes it, where freshness requirements allow.
- **Request coalescing:** Combine concurrent requests for the same missing cache key into one regeneration operation.
- **Monitoring:** Track cache misses, regeneration duration, Redis errors, and database load.

The service-list cache regeneration lock is part of the current implementation. The other strategies above should be treated as recommendations unless separately implemented and tested.

A lock should have a bounded expiry and safe release behavior. It must not remain held indefinitely if a worker crashes.

## 11. Testing and Monitoring

Validate the caching strategy with automated tests for:

- Cache miss followed by cache hit.
- Expiration after the configured TTL.
- Invalidation after service creation, update, and deletion.
- Concurrent requests for the same uncached resource.
- Redis unavailability and recovery behavior.
- Response correctness after cached data changes.

Monitor cache hit rate, miss rate, eviction count, Redis memory use, regeneration latency, and PostgreSQL query load.

Performance improvements should be demonstrated by comparing repeated requests with caching disabled and enabled under equivalent test conditions.

## 12. Operational Considerations

- Keep Redis credentials and connection settings in environment variables.
- Monitor Redis availability, memory usage, latency, and evictions.
- Choose an appropriate Redis memory policy for the deployment workload.
- Review cache-key growth and invalidation behavior.
- Avoid caching sensitive or user-specific responses under shared keys.
- Test and document application behavior when Redis is unavailable.
- Use repeated load tests and latency-percentile measurements before production deployment.
- Review Redis authentication, networking, persistence, and high-availability requirements.
- Ensure distributed locks have bounded timeouts and safe release behavior.
- Retain database constraints and transactions for critical business rules.

## 13. Conclusion and Remaining Work

The local implementation demonstrates service-list caching with a 60-second TTL, cache invalidation after service mutations, reduced warm-cache latency in the recorded benchmark, basic Redis lock contention testing, and successful warm-cache and cold-cache concurrent-request runs.

The measured warm-cache response-time reduction was approximately 98.28% in the recorded local benchmark. This figure should not be treated as a production performance guarantee.

The Redis lock coordinates service-list cache regeneration. A Redis lock has not been integrated into a booking or payment business operation; that remains a separate decision requiring a clearly justified concurrency use case.

Remaining work:

- Test and document application behavior when Redis is unavailable.
- Review logging and observability for critical application components.
- Repeat concurrency and performance tests under additional loads.
- Verify rate-limiting settings and endpoint-specific tests.
- Review the working tree before committing changes.