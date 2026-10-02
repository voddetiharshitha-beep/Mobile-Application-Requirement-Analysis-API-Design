# Final Django Mobile Backend Capstone & Individual Assessment

## Task 1 — Receive a New Requirement

### Requirement

Add a **Saved Services** feature where customers can:

1. Save services.
2. Remove saved services.
3. View their saved services.
4. Receive a notification when a saved service changes availability.

---

## 1. Requirement Understanding

The Saved Services feature will allow authenticated customers to maintain a personal list of services they are interested in.

The feature consists of two main areas:

### Customer functionality

```text
Customer
   ↓
View Services
   ↓
Save Service
   ↓
View Saved Services
   ↓
Remove Saved Service
```

### Notification functionality

```text
Service availability changes
            ↓
Find customers who saved the service
            ↓
Create notification
            ↓
Customer views notification
```

---

## 2. Existing Components Affected

The existing backend already contains:

* User authentication
* Service management
* Service model
* Notification system
* Celery background tasks
* Redis
* PostgreSQL
* Django REST Framework
* API permissions
* Pagination
* Automated tests
* Regression tests

The new feature should extend the existing architecture rather than introduce a separate system.

---

## 3. Proposed Data Model

A new `SavedService` model will establish a relationship between a customer and a service.

### Proposed fields

```text
SavedService
------------
id
customer
service
created_at
```

The customer and service combination should be unique so that the same customer cannot save the same service multiple times.

Example:

```text
Customer A → Service X    Allowed
Customer A → Service X    Duplicate - Not Allowed
Customer B → Service X    Allowed
```

---

## 4. Proposed API Endpoints

### Save a service

```http
POST /api/v1/services/<service_id>/save/
```

Requires authentication.

### Remove a saved service

```http
DELETE /api/v1/services/<service_id>/save/
```

Requires authentication.

### View saved services

```http
GET /api/v1/services/saved/
```

Requires authentication.

The saved-service list should return only services saved by the currently authenticated customer.

---

## 5. Notification Requirement

When a service's availability changes, customers who have saved that service should receive a notification.

Proposed workflow:

```text
Provider/Admin changes service availability
                ↓
       Availability changes
                ↓
       Find SavedService records
                ↓
       Identify affected customers
                ↓
       Create notifications
                ↓
          Celery task
                ↓
       Customer receives notification
```

The existing notification and Celery architecture should be reused where possible.

---

## 6. Security Requirements

| Scenario                                        | Expected Result                         |
| ----------------------------------------------- | --------------------------------------- |
| Unauthenticated user saves a service            | 401 Unauthorized                        |
| Authenticated customer saves a service          | Allowed                                 |
| Customer saves the same service twice           | Duplicate prevented                     |
| Customer removes a saved service                | Allowed                                 |
| Customer views saved services                   | Only their own saved services           |
| Customer accesses another customer's saved data | Not allowed                             |
| Service does not exist                          | 404 Not Found                           |
| Service availability changes                    | Relevant customers receive notification |

---

## 7. Performance Considerations

The feature should follow the performance practices already applied to the backend.

The implementation should:

* Use appropriate `select_related()` or `prefetch_related()` where required.
* Add a database uniqueness constraint for customer/service combinations.
* Add database indexes where justified.
* Paginate saved-service results when appropriate.
* Avoid N+1 queries.
* Use Celery for asynchronous notification work where appropriate.
* Avoid creating duplicate notifications.

---

## 8. Implementation Plan

The implementation will follow these stages:

1. Inspect the existing `Service` model.
2. Inspect the existing `Notification` model.
3. Inspect existing Celery notification tasks.
4. Inspect existing service URLs, views, and serializers.
5. Design the `SavedService` model.
6. Create the database migration.
7. Create the serializer.
8. Implement the save-service API.
9. Implement the remove-service API.
10. Implement the saved-services list API.
11. Implement availability-change notification logic.
12. Integrate the notification workflow with Celery where appropriate.
13. Add API URLs.
14. Add automated tests.
15. Test the APIs using Postman.
16. Run the full regression test suite.
17. Verify security and permission behavior.
18. Document the completed implementation.

---

## 9. Expected Acceptance Criteria

The feature will be considered complete when:

* Customers can save services.
* Customers can remove saved services.
* Customers can view their saved services.
* Duplicate saves are prevented.
* Users cannot access another customer's saved services.
* Appropriate authentication and authorization are enforced.
* Availability changes trigger notifications for relevant customers.
* Automated tests cover the new functionality.
* Regression tests continue to pass.
* API behavior is verified using Postman.
* No significant N+1 query problem is introduced.
* The implementation is documented.

---

## 10. Initial Design Decision

No coding will begin until the existing Service, Notification, Celery, URL, view, serializer, and permission implementations have been reviewed.

This ensures that the new Saved Services feature integrates with the existing Django mobile backend architecture and follows the project's established security, performance, testing, and notification patterns.
