# Database Design

## 1. Overview

The **Saved Services** feature allows authenticated customers to save services that they may want to access later.

A `SavedService` record represents the relationship between:

* A customer (`User`)
* A service (`Service`)

The same customer can save multiple services, and the same service can be saved by multiple customers.

---

## 2. Entity: SavedService

### Purpose

`SavedService` stores which services have been saved by which customers.

### Fields

| Field        | Type                 | Description                              |
| ------------ | -------------------- | ---------------------------------------- |
| `id`         | UUID                 | Primary key for the saved-service record |
| `customer`   | ForeignKey → User    | Customer who saved the service           |
| `service`    | ForeignKey → Service | Service that was saved                   |
| `created_at` | DateTime             | Date and time when the service was saved |

---

## 3. Primary Key

The `SavedService` table uses:

```text
id
```

as its primary key.

The ID is a UUID to provide a unique identifier for every saved-service record.

Example:

```text
550e8400-e29b-41d4-a716-446655440000
```

---

## 4. Customer Relationship

The `customer` field has a foreign-key relationship with Django's `User` model.

```text
SavedService.customer → User
```

Relationship:

```text
User 1 ─────────── M SavedService
```

This means:

* One customer can save many services.
* Each saved-service record belongs to one customer.
* If a customer is deleted, their saved-service records are also deleted.

---

## 5. Service Relationship

The `service` field has a foreign-key relationship with the existing `Service` model.

```text
SavedService.service → Service
```

Relationship:

```text
Service 1 ─────────── M SavedService
```

This means:

* One service can be saved by many customers.
* Each saved-service record refers to one service.
* If a service is deleted, its saved-service records are also deleted.

---

## 6. Created Date

The `created_at` field stores when the customer saved the service.

```text
created_at = DateTimeField(auto_now_add=True)
```

The value is automatically created when the `SavedService` record is inserted.

This allows the API to display saved services in the order they were saved.

---

## 7. Unique Constraint

A customer must not be able to save the same service multiple times.

Therefore, a unique constraint is required on:

```text
customer + service
```

Conceptually:

```text
UNIQUE(customer_id, service_id)
```

Example:

| Customer   | Service   | Allowed        |
| ---------- | --------- | -------------- |
| Customer A | Service 1 | Yes            |
| Customer A | Service 1 | No — duplicate |
| Customer A | Service 2 | Yes            |
| Customer B | Service 1 | Yes            |

This ensures that the same service can be saved by different customers while preventing duplicate saves by the same customer.

---

## 8. Database Index

An index should be created for customer and creation date:

```text
(customer, -created_at)
```

This supports efficient queries such as:

```text
Get all saved services belonging to the current customer,
ordered by most recently saved.
```

This is important because the saved-services list will normally be filtered by the authenticated customer.

---

## 9. Entity Relationship Diagram

### Text ER Diagram

```text
                    ┌──────────────────┐
                    │       User       │
                    │──────────────────│
                    │ id (PK)          │
                    │ username         │
                    │ ...              │
                    └────────┬─────────┘
                             │
                             │ 1
                             │
                             │ M
                    ┌────────▼─────────┐
                    │   SavedService   │
                    │──────────────────│
                    │ id (PK)          │
                    │ customer_id (FK) │
                    │ service_id (FK)  │
                    │ created_at       │
                    └────────┬─────────┘
                             │
                             │ M
                             │
                             │ 1
                    ┌────────▼─────────┐
                    │     Service      │
                    │──────────────────│
                    │ id (PK)          │
                    │ provider_id (FK) │
                    │ category_id (FK) │
                    │ name             │
                    │ price            │
                    │ ...              │
                    └────────┬─────────┘
                             │
                             │ M
                             │
                             │ 1
                    ┌────────▼─────────┐
                    │     Provider     │
                    │──────────────────│
                    │ id (PK)          │
                    │ user_id (FK)     │
                    │ ...              │
                    └──────────────────┘
```

### Relationship Summary

```text
User       1 ─────── M SavedService
Service    1 ─────── M SavedService
Provider   1 ─────── M Service
```

Therefore:

```text
User M ─────── M Service
       through
     SavedService
```

---

## 10. Proposed Django Model

```python
import uuid

from django.contrib.auth.models import User
from django.db import models


class SavedService(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="saved_services",
    )

    service = models.ForeignKey(
        "Service",
        on_delete=models.CASCADE,
        related_name="saved_by_customers",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "service"],
                name="unique_saved_service",
            ),
        ]

        indexes = [
            models.Index(
                fields=["customer", "-created_at"],
                name="saved_service_customer_created",
            ),
        ]

    def __str__(self):
        return f"{self.customer.username} - {self.service}"
```

---

## 11. Delete Behavior

### Customer Deleted

```text
User
  │
  └── SavedService records
          ↓
       deleted
```

`on_delete=models.CASCADE` ensures that saved-service records belonging to the deleted customer are removed.

The actual `Service` records are not affected.

### Service Deleted

```text
Service
  │
  └── SavedService records
          ↓
       deleted
```

Deleting a service removes the saved-service relationships associated with it.

The customer's account is not affected.

---

## 12. Data Integrity Rules

The database design enforces the following rules:

1. Every `SavedService` must belong to an existing customer.
2. Every `SavedService` must reference an existing service.
3. A customer cannot save the same service more than once.
4. Different customers can save the same service.
5. Removing a saved service does not delete the actual service.
6. Deleting a customer removes their saved-service relationships.
7. Deleting a service removes its saved-service relationships.
8. `created_at` is automatically generated.
9. UUID is used as the primary key.
10. Database constraints protect against duplicate saved-service records.

---

## 13. Example Data

Example database records:

| id     | customer   | service       | created_at |
| ------ | ---------- | ------------- | ---------- |
| UUID-1 | Customer A | Home Cleaning | 2026-10-02 |
| UUID-2 | Customer A | Plumbing      | 2026-10-02 |
| UUID-3 | Customer B | Home Cleaning | 2026-10-02 |

This demonstrates that:

* Customer A saved two different services.
* Customer B also saved Home Cleaning.
* Home Cleaning can therefore be saved by multiple customers.
* Customer A cannot create another record for Home Cleaning.

---

## 14. Database Design Summary

The `SavedService` entity provides a normalized many-to-many relationship between customers and services.

```text
User
 │
 │ 1:M
 ▼
SavedService
 ▲
 │ M:1
 │
Service
```

The design uses:

* UUID primary key
* Foreign keys
* Cascade deletion
* Unique constraint
* Database index
* Automatic creation timestamp

This design supports the functional requirements of the Saved Services feature while maintaining data integrity and efficient customer-specific queries.
---

# 15. PostgreSQL Database for Scalability

## 15.1 Database Choice

The mobile service booking backend uses PostgreSQL as its relational database.

PostgreSQL is suitable because it provides:

- ACID transactions for reliable booking and payment operations.
- Foreign keys, unique constraints, and indexes for data integrity.
- Efficient querying and filtering for service listings and bookings.
- Concurrent access control for requests from multiple users.
- Backup and recovery tools.
- Replication options for improving availability and read scalability.

The application is configured to use PostgreSQL through Django's database settings and environment variables.

## 15.2 Main Read and Write Operations

| Operation | Access pattern | Database approach |
|---|---|---|
| Browse services | Read-heavy | Query filtering, pagination, indexes, Redis caching |
| View saved services | Read-heavy | Customer filtering and suitable indexes |
| Create a booking | Write | Database transaction and validation |
| Change booking status | Write | Transaction and row-level locking where required |
| Initiate a payment | Write | Transactional updates and payment-state validation |
| Read notifications | Read-heavy | Filter by user and use pagination |
| Update user profile | Write | Validate and persist changes |

Service listings and other frequently requested data can benefit from caching. Booking and payment changes must be persisted reliably in PostgreSQL.

Redis caching must not be treated as the authoritative source for booking or payment records.

# 16. Database Indexing Strategy

Indexes help PostgreSQL locate records without scanning an entire table for every query. They improve read performance but consume storage and add overhead to inserts, updates, and deletes.

The application should maintain indexes based on actual query patterns.

Important examples include:

- Booking provider, booking date, and booking time for provider schedules.
- Saved-service customer and creation time for a customer's saved list.
- A unique constraint on saved-service customer and service.
- Idempotency-key lookup indexes for safely handling repeated requests.
- Foreign-key and frequently filtered fields where query analysis shows an indexing benefit.

Before adding new indexes, inspect existing model definitions and migrations to avoid duplicate indexes.

Use PostgreSQL's `EXPLAIN` and, where appropriate, `EXPLAIN ANALYZE` to evaluate query plans. Run performance analysis against representative data and avoid running expensive analysis against production workloads without considering its impact.

# 17. Transactions and Data Consistency

A database transaction groups related operations so that they succeed or fail together.

For example, booking creation and payment processing may require multiple database changes. If one required operation fails, the database changes within the transaction should be rolled back.

The project uses Django transaction management, including `transaction.atomic()` in relevant service-layer operations. Row-level locking with `select_for_update()` can protect critical records from conflicting concurrent updates.

The design follows these principles:

1. Validate input and permissions before changing records.
2. Use transactions for related database writes that must succeed together.
3. Lock rows when concurrent changes could violate a business rule.
4. Keep transactions short to reduce lock contention.
5. Use unique constraints and idempotency keys to prevent duplicate operations.
6. Do not hold a database transaction open while waiting for a slow external payment provider.
7. Treat payment-provider communication and webhook retries as separate reliability concerns.

Transactions and locking help maintain consistency, but they do not replace appropriate validation, database constraints, or payment idempotency.

# 18. Connection Pooling

Every database connection consumes resources. Under heavy traffic, opening too many connections can exhaust PostgreSQL's connection limit and reduce application performance.

Connection pooling reuses database connections rather than opening a new physical connection for every request.

Possible production approaches include:

- PgBouncer as an external PostgreSQL connection pooler.
- Django persistent connections using `CONN_MAX_AGE`, configured according to the deployment model.
- Connection health checks and sensible database connection limits.

The appropriate settings depend on the number of application workers, database capacity, transaction behavior, and whether an external pooler is used.

**Current implementation note:** Do not describe PgBouncer or persistent connection pooling as deployed unless it has actually been configured and verified. Connection pooling is a production scalability recommendation when it is not yet enabled.

# 19. Scaling to One Million Users

Supporting one million registered users does not mean that one million database connections are required. Capacity planning must account for concurrent requests, read/write ratios, query complexity, storage, and peak traffic.

A proposed scaling strategy is:

1. **Application layer:** Run multiple application workers or instances behind a load balancer.
2. **Database layer:** Use PostgreSQL with suitable indexes, short transactions, and query optimization.
3. **Caching layer:** Use Redis for frequently accessed service listings and other suitable cacheable data.
4. **Read optimization:** Apply pagination, avoid unnecessary related-object queries, and review slow queries.
5. **Connection management:** Limit application connections and introduce a pooler when appropriate.
6. **Read replicas:** Consider PostgreSQL replicas for eligible read-heavy workloads after measuring primary database pressure.
7. **Monitoring:** Track query latency, connection usage, cache hit rate, database CPU, storage, and error rates.
8. **Load testing:** Test realistic concurrent traffic and data volumes before selecting production capacity.

A million registered users is a planning target, not proof that the current deployment can sustain a particular request rate. Capacity must be demonstrated through testing.

--------------
# 20. PostgreSQL Backup and Recovery

PostgreSQL backups help recover database data after accidental deletion, data corruption, hardware failure, or other incidents.

## 20.1 Backup Strategy

The project database can be backed up using PostgreSQL's `pg_dump` utility. The custom archive format (`-F c`) supports inspection and selective restoration with PostgreSQL's `pg_restore` utility.

Example PowerShell commands:

```powershell
pg_dump -h localhost -p 5432 -U postgres -W -F c `
    -f "backend_architecture_review_backup.dump" `
    backend_architecture_review
```

Inspect the backup archive:

```powershell
pg_restore --list "backend_architecture_review_backup.dump"
```

The database backup should be stored securely, separately from the application source code, and protected with appropriate access controls.

## 20.2 Recovery Testing

A backup should not be considered reliable until its restoration has been tested.

The development environment was used to create a custom-format PostgreSQL backup and restore it into a separate test database. Verification found 25 public base tables and 14 booking records in the restored database.

This confirms that the tested archive could be restored sufficiently to verify those objects and records. It does not guarantee recovery from every possible production failure.

## 20.3 Production Recommendations

For a production deployment:

1. Schedule automated backups according to business recovery requirements.
2. Store backup copies in a separate, access-controlled location.
3. Encrypt backups where appropriate and protect database credentials.
4. Define a **Recovery Point Objective (RPO)**: the maximum acceptable amount of data loss measured in time.
5. Define a **Recovery Time Objective (RTO)**: the target time to restore service after an incident.
6. Periodically test restoration and document the recovery procedure.
7. Consider point-in-time recovery using base backups and archived write-ahead logs (WAL) when the required recovery objectives justify it.
8. Monitor backup jobs and alert on failures.

**Current status:** A local backup and a test restoration have been performed. Automated scheduling, off-site storage, and point-in-time recovery should be treated as future production work unless they have been separately configured and verified.

# 21. PostgreSQL Replication

PostgreSQL replication maintains copies of database data on additional database servers. It can improve availability and help distribute read traffic when configured appropriately.

A possible production architecture is:

- **Primary database:** Handles writes, such as booking creation, booking status changes, and payment records.
- **Read replica:** Handles eligible read-only queries, such as service browsing and reporting.
- **Monitoring and failover:** Detects database problems and supports recovery according to a tested operational procedure.

Replication considerations:

1. A replica may lag behind the primary database.
2. Queries that require immediately updated data should use the primary where necessary.
3. Replication does not replace independent backups.
4. Failover and recovery procedures must be tested.

**Current status:** Replication is a proposed production capability. It must not be considered implemented until a replica has been configured and verified.

# 22. Database Design Verification

The following checks have been performed in the development environment:

| Check | Evidence |
|---|---|
| Django system check | Previously reported no issues |
| Database engine | PostgreSQL |
| Migration consistency | Previously reported no changes detected |
| Backup creation | Custom-format PostgreSQL backup created |
| Backup inspection | `pg_restore --list` inspected the archive |
| Restore verification | A separate test database contained 25 public base tables and 14 booking records |

These checks verify the basic configuration and selected backup-recovery behavior. They do not prove production-scale performance or a complete disaster-recovery capability.

Further production validation should include realistic load tests, query-plan analysis, backup scheduling, monitoring, and tested recovery procedures.

# 23. Conclusion

PostgreSQL provides persistent relational storage for the mobile service booking backend. Database constraints, indexes, transactions, and appropriate locking help maintain data integrity under concurrent requests.

Redis can reduce database load for suitable frequently accessed data. To prepare for one million registered users, the architecture should also consider connection pooling, query optimization, pagination, monitoring, load testing, secure backups, and tested recovery procedures.

Read replicas and automated failover should be introduced when justified by measured performance and availability requirements. The target of one million users must be validated through realistic capacity testing rather than assumed from the database choice alone.