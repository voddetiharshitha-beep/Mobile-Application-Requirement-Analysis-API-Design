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
