# Saved Services — Requirement Analysis

## 1. Problem

Customers can browse and book services in the mobile application, but there is currently no way for a customer to save a service for later.

Customers may find a service they are interested in but may not be ready to book it immediately. Without a saved-services feature, they must search for the service again later.

The system therefore needs a **Saved Services** feature that allows customers to save services, remove saved services, and view their saved services.

The system should also notify customers when a service they have saved changes availability.

---

## 2. Users

### Customer

The customer is the primary user of this feature.

A customer can:

* Save a service.
* Remove a saved service.
* View their saved services.
* Receive notifications when a saved service changes availability.

### Provider

The provider owns or manages services.

A provider may change the availability of a service. When the availability of a saved service changes, the affected customers should receive notifications.

### Administrator

The administrator can monitor and manage services and users through the existing administrative functionality.

---

## 3. Functional Requirements

### FR-01 — Save a Service

An authenticated customer must be able to save an existing service.

Example:

```text
Customer → Save Service → Service added to saved services
```

The system must associate the saved service with the authenticated customer.

---

### FR-02 — Remove a Saved Service

An authenticated customer must be able to remove a service from their saved services.

Example:

```text
Customer → Remove Saved Service → Service removed
```

---

### FR-03 — View Saved Services

An authenticated customer must be able to retrieve a list of their saved services.

The system must return only services saved by the currently authenticated customer.

---

### FR-04 — Prevent Duplicate Saved Services

A customer must not be able to save the same service multiple times.

The system should enforce uniqueness for the combination of:

```text
customer + service
```

---

### FR-05 — Authentication

Customers must be authenticated before they can:

* Save a service.
* Remove a saved service.
* View saved services.

Unauthenticated requests must be rejected.

---

### FR-06 — Service Availability Notification

When the availability of a service changes, the system must identify customers who have saved that service.

Those customers must receive a notification about the availability change.

---

### FR-07 — Notification Processing

Notification creation should use the existing notification architecture and asynchronous processing where appropriate.

Celery can be used to process notification creation without unnecessarily blocking the API request.

---

### FR-08 — Data Isolation

A customer must only be able to access their own saved services.

One customer must not be able to view, modify, or delete another customer's saved-service records.

---

### FR-09 — Invalid Service Handling

If a customer attempts to save a service that does not exist, the API must return an appropriate error response, such as:

```text
404 Not Found
```

---

### FR-10 — API Integration

The feature must integrate with the existing Django REST Framework API architecture, authentication, permissions, serializers, URLs, notifications, and testing structure.

---

## 4. Non-Functional Requirements

### NFR-01 — Security

The feature must require authentication for customer-specific operations.

Authorization must ensure that customers can access only their own saved services.

---

### NFR-02 — Performance

The saved-services APIs should perform efficiently and avoid unnecessary database queries.

The implementation should consider:

* `select_related()`
* `prefetch_related()`
* Database indexes
* Queryset filtering
* Pagination for large result sets
* Avoiding N+1 queries

---

### NFR-03 — Reliability

Saving or removing a service should produce a consistent database state.

Duplicate saved-service records must not be created even if multiple requests are made.

---

### NFR-04 — Scalability

The design should support a growing number of customers and saved services without requiring a major architectural change.

Database queries should be optimized for larger datasets.

---

### NFR-05 — Maintainability

The implementation should follow the existing Django project structure and coding conventions.

The feature should use reusable serializers, views, permissions, models, and existing notification infrastructure where appropriate.

---

### NFR-06 — Testability

The feature must be covered by automated tests.

Tests should cover:

* Saving a service.
* Removing a service.
* Viewing saved services.
* Duplicate saves.
* Authentication.
* Authorization.
* Invalid services.
* Availability notifications.

---

### NFR-07 — API Consistency

The new APIs should follow the existing API response format, authentication mechanism, HTTP methods, status codes, and URL structure used by the project.

---

### NFR-08 — Asynchronous Notification Processing

Availability-change notifications should be processed asynchronously where appropriate so that notification processing does not unnecessarily delay the main service-availability operation.

---

## 5. Business Rules

### BR-01 — Only Authenticated Customers Can Save Services

A user must be authenticated before saving a service.

---

### BR-02 — A Service Can Be Saved Only Once Per Customer

The same customer cannot have multiple saved records for the same service.

```text
Customer A + Service X = One saved record
```

---

### BR-03 — Different Customers Can Save the Same Service

Multiple customers may save the same service.

Example:

```text
Customer A → Service X
Customer B → Service X
Customer C → Service X
```

This is allowed.

---

### BR-04 — Customers Own Their Saved-Service Records

A customer can access only their own saved services.

---

### BR-05 — Only Existing Services Can Be Saved

A saved-service record must reference an existing service.

---

### BR-06 — Removing a Service Must Remove the Customer's Saved Relationship

Removing a saved service must not delete the actual service.

It only removes the relationship between the customer and the service.

```text
Remove Saved Service
        ↓
Saved relationship deleted
        ↓
Actual Service remains
```

---

### BR-07 — Availability Changes Trigger Notifications

When a service's availability changes, customers who have saved that service should receive a notification.

---

### BR-08 — Notifications Must Target Relevant Customers

A customer should receive a notification only when they have saved the affected service.

---

### BR-09 — Notification Creation Should Avoid Duplicates

The notification workflow should avoid unnecessarily creating duplicate notifications for the same availability change.

---

### BR-10 — Existing Service and User Data Must Remain Unchanged

Adding the Saved Services feature must not incorrectly modify existing customers, services, bookings, payments, or unrelated notifications.

---

## 6. Edge Cases

### EC-01 — Unauthenticated Save Request

A user attempts to save a service without authentication.

**Expected:**

```text
401 Unauthorized
```

---

### EC-02 — Unauthenticated Saved-Service List

A user attempts to view saved services without authentication.

**Expected:**

```text
401 Unauthorized
```

---

### EC-03 — Duplicate Save

A customer attempts to save the same service twice.

**Expected:**

The second save must be rejected or handled idempotently without creating a duplicate record.

---

### EC-04 — Remove Service That Was Not Saved

A customer attempts to remove a service that they have not saved.

**Expected:**

The API should return an appropriate response, such as `404 Not Found`, without affecting other saved services.

---

### EC-05 — Invalid Service ID

A customer sends an invalid or nonexistent service ID.

**Expected:**

The API should return an appropriate validation or `404 Not Found` response.

---

### EC-06 — Customer Attempts to Access Another Customer's Saved Service

A customer attempts to access another customer's saved-service data.

**Expected:**

The request must be denied or the data must not be exposed.

---

### EC-07 — Service Availability Changes With No Saved Customers

A service becomes unavailable or available, but no customer has saved it.

**Expected:**

No customer notifications need to be created.

---

### EC-08 — Service Availability Changes With Multiple Saved Customers

Multiple customers have saved the same service and its availability changes.

**Expected:**

Each relevant customer should receive the appropriate notification.

---

### EC-09 — Repeated Availability Updates

The same availability state is submitted repeatedly without an actual change.

**Expected:**

The system should avoid generating unnecessary duplicate availability-change notifications.

---

### EC-10 — Service Deleted After Being Saved

A service that was previously saved is deleted.

**Expected:**

The saved-service relationship should be handled according to the database relationship policy, such as cascading deletion or another explicitly defined cleanup strategy.

---

### EC-11 — Concurrent Save Requests

A customer sends multiple save requests at nearly the same time.

**Expected:**

The database uniqueness constraint must prevent duplicate saved-service records.

---

### EC-12 — Large Number of Saved Services

A customer has a large number of saved services.

**Expected:**

The saved-services endpoint should remain performant by using database-level filtering and pagination where appropriate.

---

## 7. Requirement Summary

The Saved Services feature will provide customers with a persistent way to save services for later use.

The feature must provide:

```text
Save Service
     ↓
View Saved Services
     ↓
Remove Saved Service
     ↓
Service Availability Changes
     ↓
Notify Customers
```

The implementation must maintain the existing application's security, performance, reliability, testing, and notification standards.

No implementation should begin until these requirements have been reviewed and understood.
