# Saved Services API Design

## 1. Overview

The Saved Services API allows authenticated customers to save services for later use, view their saved services, and remove a saved service.

### Endpoints

| Method | Endpoint                       | Purpose                                          |
| ------ | ------------------------------ | ------------------------------------------------ |
| POST   | `/api/v1/saved-services/`      | Save a service                                   |
| GET    | `/api/v1/saved-services/`      | View the authenticated customer's saved services |
| DELETE | `/api/v1/saved-services/{id}/` | Remove a saved service                           |

---

# 2. POST — Save a Service

### Endpoint

```text
POST /api/v1/saved-services/
```

### Purpose

Creates a saved-service record for the authenticated customer.

A customer can save an existing service. The same customer cannot save the same service more than once.

---

## Request

### Headers

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Request Body

```json
{
    "service": "17b4xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

### Request Fields

| Field     | Type | Required | Description                 |
| --------- | ---- | -------- | --------------------------- |
| `service` | UUID | Yes      | UUID of the service to save |

The customer is obtained from the authenticated JWT token and is **not supplied by the client**.

---

## Successful Response

### Status Code

```text
201 Created
```

### Example

```json
{
    "id": "8c7dxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "service": "17b4xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "service_name": "Home Cleaning",
    "created_at": "2026-10-03T10:30:00Z"
}
```

---

## Authentication

JWT authentication is required.

```http
Authorization: Bearer <access_token>
```

Unauthenticated users cannot save services.

---

## Permissions

* User must be authenticated.
* Only customers can create saved-service records.
* The service must exist.
* The authenticated user's identity is taken from the access token.
* A customer cannot create a duplicate saved-service record for the same service.

---

## Errors

### Authentication missing

```text
401 Unauthorized
```

Example:

```json
{
    "detail": "Authentication credentials were not provided."
}
```

### Service does not exist

```text
400 Bad Request
```

Example:

```json
{
    "service": [
        "Invalid pk \"...\" - object does not exist."
    ]
}
```

### Duplicate saved service

```text
400 Bad Request
```

Example:

```json
{
    "service": [
        "This service has already been saved."
    ]
}
```

---

# 3. GET — View Saved Services

### Endpoint

```text
GET /api/v1/saved-services/
```

### Purpose

Returns the saved services belonging to the authenticated customer.

A customer must only see their own saved services.

---

## Request

### Headers

```http
Authorization: Bearer <access_token>
```

No request body is required.

---

## Successful Response

### Status Code

```text
200 OK
```

### Example

```json
[
    {
        "id": "8c7dxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "service": "17b4xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "service_name": "Home Cleaning",
        "created_at": "2026-10-03T10:30:00Z"
    },
    {
        "id": "91abxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "service": "25cdxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "service_name": "Plumbing Service",
        "created_at": "2026-10-03T11:00:00Z"
    }
]
```

If the customer has no saved services:

```json
[]
```

---

## Authentication

JWT authentication is required.

---

## Permissions

* User must be authenticated.
* The API returns only records belonging to the authenticated customer.
* A customer cannot view another customer's saved services.

---

## Errors

### Authentication missing

```text
401 Unauthorized
```

### Invalid authentication token

```text
401 Unauthorized
```

---

# 4. DELETE — Remove a Saved Service

### Endpoint

```text
DELETE /api/v1/saved-services/{id}/
```

### Purpose

Removes a saved-service relationship.

The actual `Service` record is **not deleted**.

---

## Request

### Headers

```http
Authorization: Bearer <access_token>
```

### URL Parameter

```text
{id}
```

The `id` is the UUID of the `SavedService` record.

Example:

```text
DELETE /api/v1/saved-services/8c7dxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/
```

No request body is required.

---

## Successful Response

### Status Code

```text
204 No Content
```

The response contains no response body.

---

## Authentication

JWT authentication is required.

---

## Permissions

* User must be authenticated.
* A customer can delete only their own saved-service records.
* Deleting a saved service must not delete the actual `Service`.
* A customer cannot remove another customer's saved-service record.

---

## Errors

### Authentication missing

```text
401 Unauthorized
```

### Saved service does not exist

```text
404 Not Found
```

Example:

```json
{
    "detail": "Not found."
}
```

### Saved service belongs to another customer

```text
404 Not Found
```

The API should avoid revealing whether another customer's saved-service record exists.

---

# 5. Status Code Summary

| Operation                   |        Status Code | Meaning                                    |
| --------------------------- | -----------------: | ------------------------------------------ |
| Save service                |      `201 Created` | Saved successfully                         |
| View saved services         |           `200 OK` | Saved services returned                    |
| Remove saved service        |   `204 No Content` | Removed successfully                       |
| Missing authentication      | `401 Unauthorized` | Authentication required                    |
| Invalid request / duplicate |  `400 Bad Request` | Request validation failed                  |
| Saved service not found     |    `404 Not Found` | Record does not exist or is not accessible |

---

# 6. Security and Data Isolation

The API must enforce customer-level data isolation.

For every request:

```text
JWT token
    ↓
Authenticated User
    ↓
Customer's SavedService records only
```

The client must never provide a `customer` ID when creating a saved service.

The backend obtains the customer from:

```python
request.user
```

For listing saved services, the query must be restricted to:

```python
SavedService.objects.filter(customer=request.user)
```

For deletion, the saved-service record must also be restricted to the authenticated customer.

This prevents one customer from accessing or deleting another customer's saved services.

---

# 7. API Flow

### Save

```text
Customer
   ↓
POST /api/v1/saved-services/
   ↓
JWT Authentication
   ↓
Validate Service
   ↓
Check Duplicate
   ↓
Create SavedService
   ↓
201 Created
```

### View

```text
Customer
   ↓
GET /api/v1/saved-services/
   ↓
JWT Authentication
   ↓
Filter by request.user
   ↓
Return Saved Services
   ↓
200 OK
```

### Remove

```text
Customer
   ↓
DELETE /api/v1/saved-services/{id}/
   ↓
JWT Authentication
   ↓
Verify Ownership
   ↓
Delete SavedService relationship
   ↓
204 No Content
```

---

# 8. Business Rules

1. Only authenticated customers can use the Saved Services API.
2. A service must exist before it can be saved.
3. A customer can save a service only once.
4. Multiple customers can save the same service.
5. Customers can view only their own saved services.
6. Customers can delete only their own saved-service records.
7. Removing a saved service does not delete the actual service.
8. Deleting a service automatically removes related saved-service records because of the database relationship.
9. The customer identity is determined from JWT authentication rather than request data.
10. The API should return appropriate HTTP status codes for successful and failed operations.

---

# 9. Endpoint Summary

```text
POST
/api/v1/saved-services/
    → Save a service
    → 201 Created

GET
/api/v1/saved-services/
    → View customer's saved services
    → 200 OK

DELETE
/api/v1/saved-services/{id}/
    → Remove saved service
    → 204 No Content
```
