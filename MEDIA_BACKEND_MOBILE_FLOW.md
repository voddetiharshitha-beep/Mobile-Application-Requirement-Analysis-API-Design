# Media Backend – Mobile Upload and Download Flow

## 1. Overview

The backend provides secure image/media handling for the mobile application.

The media implementation supports:

* Profile image uploads
* Service image uploads
* Secure media storage
* Safe generated filenames
* Image validation
* File size limits
* Image dimension limits
* Public and private media
* Owner-based access control
* Secure media downloads
* Automatic cleanup of deleted media files
* Automatic cleanup when a media file is replaced

All API endpoints are available under the `/api/v1/` API base path.

---

## 2. Supported Image Formats

The backend currently supports:

* JPEG (`.jpg`, `.jpeg`)
* PNG (`.png`)

The maximum allowed file size is:

```text
5 MB
```

The maximum allowed image dimensions are:

```text
4096 × 4096 pixels
```

The maximum total number of pixels is:

```text
16,777,216 pixels
```

Uploaded files are also verified using Pillow to ensure that the file contains valid image data.

---

## 3. Profile Image Upload

### Endpoint

```http
POST /api/v1/profile/image/
```

### Authentication

Authentication is required.

The mobile application must send a valid JWT access token:

```http
Authorization: Bearer <access_token>
```

### Content Type

The request should use:

```http
Content-Type: multipart/form-data
```

### Form field

The image should be sent using:

```text
image
```

### Example mobile request

```text
POST /api/v1/profile/image/

Authorization: Bearer <access_token>
Content-Type: multipart/form-data

image = profile.jpg
```

### Validation

The backend validates:

* File existence
* File extension
* MIME type
* File size
* Image validity
* Image dimensions

Invalid files are rejected.

---

## 4. Service Image Upload

### Endpoint

```http
POST /api/v1/services/<service_id>/images/
```

Replace `<service_id>` with the UUID of the service.

### Authentication

The endpoint follows the authentication and authorization rules implemented by the service image API.

### Content Type

```http
Content-Type: multipart/form-data
```

### Example

```text
POST /api/v1/services/7b2c.../images/

image = service.jpg
```

The uploaded image is associated with the specified service.

---

## 5. Service Image List

The mobile application can retrieve images associated with a service using:

```http
GET /api/v1/services/<service_id>/images/
```

Example:

```text
GET /api/v1/services/7b2c.../images/
```

The response contains the images associated with that service.

---

## 6. Service Image Delete

A service image can be deleted using:

```http
DELETE /api/v1/services/<service_id>/images/<image_id>/
```

Example:

```text
DELETE /api/v1/services/7b2c.../images/91af.../
```

Authorization rules are enforced by the existing service image API.

---

## 7. Generic Media Download

The new media download endpoint is:

```http
GET /api/v1/services/media/<media_id>/download/
```

Example:

```text
GET /api/v1/services/media/2c4a.../download/
```

The `<media_id>` value is the UUID of the `Media` record.

---

## 8. Public Media Access

Media can be marked as:

```text
PUBLIC
```

Public media can be downloaded without authentication.

Example:

```http
GET /api/v1/services/media/<media_id>/download/
```

No Authorization header is required for public media.

The backend returns the image file using a `FileResponse`.

---

## 9. Private Media Access

Media can also be marked as:

```text
PRIVATE
```

Private media is accessible only by the owner.

The mobile application should send:

```http
Authorization: Bearer <access_token>
```

The backend verifies that:

```text
request.user.id == media.owner_id
```

If the authenticated user is not the owner, the backend denies access.

The API returns:

```http
404 Not Found
```

for inaccessible private media.

This prevents unauthorized users from discovering whether a protected media object exists.

---

## 10. Anonymous Access Rules

The access rules are:

| Media visibility | Anonymous user |   Owner | Other authenticated user |
| ---------------- | -------------: | ------: | -----------------------: |
| PUBLIC           |        Allowed | Allowed |                  Allowed |
| PRIVATE          |         Denied | Allowed |                   Denied |

Private media therefore requires both:

1. Authentication
2. Ownership

---

## 11. Safe Filename Generation

The original uploaded filename is not used as the physical storage filename.

The backend generates a unique UUID-based filename.

Example:

```text
media/8e5c3b2e1a2d4f7c9a1234567890abcd.jpg
```

This provides:

* Unique filenames
* Reduced filename collision risk
* Protection against unsafe user-controlled storage names
* Separation between the user's original filename and the storage filename

The original filename is retained separately in the `Media.original_filename` field.

---

## 12. Media Metadata

Each `Media` record stores information including:

```text
id
owner
service
file
media_type
visibility
original_filename
mime_type
file_size
created_at
updated_at
```

The media UUID is used by the download endpoint.

---

## 13. Upload Validation Flow

The image validation process is:

```text
Mobile Application
        |
        v
multipart/form-data upload
        |
        v
Django API
        |
        v
Check file exists
        |
        v
Validate extension/MIME
        |
        v
Check file size <= 5 MB
        |
        v
Pillow image verification
        |
        v
Check image dimensions
        |
        v
Generate safe filename
        |
        v
Store media file
        |
        v
Create Media database record
```

Invalid uploads are rejected before they can be treated as valid media.

---

## 14. Download Flow

The mobile download flow is:

```text
Mobile Application
        |
        v
GET /api/v1/services/media/<media_id>/download/
        |
        v
Django API
        |
        v
Find Media record
        |
        v
Check visibility
        |
        +---- PUBLIC ----> Allow
        |
        +---- PRIVATE ---> Check authenticated owner
                              |
                              +---- Owner ----> Allow
                              |
                              +---- Other ---> 404
        |
        v
Open media file
        |
        v
Return FileResponse
        |
        v
Mobile Application
```

---

## 15. Download Response

The backend returns the actual media file using Django's `FileResponse`.

The response content type uses the stored MIME type.

The response also includes a download filename based on the original filename.

Example:

```http
Content-Type: image/jpeg
Content-Disposition: attachment; filename="profile.jpg"
```

---

## 16. Missing Media

If the requested media UUID does not exist, the API returns:

```http
404 Not Found
```

The API uses the error code:

```text
MEDIA_NOT_FOUND_OR_FORBIDDEN
```

The same response is used when a private media object exists but the requesting user is not authorized to access it.

This avoids exposing protected media existence information.

---

## 17. Missing Physical File

If the database record exists but the physical file is unavailable, the API returns:

```http
404 Not Found
```

with the error code:

```text
MEDIA_FILE_NOT_FOUND
```

---

## 18. Media Cleanup

The backend automatically removes physical media files when the corresponding `Media` database record is deleted.

The cleanup process is implemented using Django model signals.

### Delete flow

```text
Media record deleted
        |
        v
post_delete signal
        |
        v
Delete physical media file
```

---

## 19. Media Replacement Cleanup

When an existing `Media` record receives a new file, the previous physical file is removed.

Flow:

```text
Existing Media
      |
      v
New file assigned
      |
      v
pre_save signal
      |
      v
Delete old physical file
      |
      v
Save new file
```

This prevents abandoned media files from remaining in storage.

---

## 20. Security Rules

The media backend applies the following protections:

* Only supported image formats are accepted.
* Invalid image content is rejected.
* Files larger than 5 MB are rejected.
* Images larger than 4096 pixels in width are rejected.
* Images larger than 4096 pixels in height are rejected.
* Images exceeding the maximum pixel count are rejected.
* Storage filenames are generated by the backend.
* Public and private media are separated through visibility rules.
* Private media requires ownership.
* Unauthorized private media requests return `404`.
* Missing physical files are handled safely.
* Deleted media files are automatically cleaned from storage.

---

## 21. Mobile Application Responsibilities

The mobile application should:

1. Select a supported image.
2. Send the image using `multipart/form-data`.
3. Include the JWT access token when authentication is required.
4. Handle validation errors returned by the API.
5. Store the returned media identifier when applicable.
6. Use the media download endpoint when retrieving protected media.
7. Refresh the JWT access token when the access token expires.
8. Display an appropriate error when media is unavailable.

The mobile application should not assume that a media URL is permanently accessible.

Access must always be determined by the backend.

---

## 22. Current API Availability

The current backend exposes these media-related operations:

| Operation                | Endpoint                                           | Available |
| ------------------------ | -------------------------------------------------- | --------- |
| Upload profile image     | `/api/v1/profile/image/`                           | Yes       |
| Upload service image     | `/api/v1/services/<service_id>/images/`            | Yes       |
| List service images      | `/api/v1/services/<service_id>/images/`            | Yes       |
| Delete service image     | `/api/v1/services/<service_id>/images/<image_id>/` | Yes       |
| Download Media           | `/api/v1/services/media/<media_id>/download/`      | Yes       |
| Generic Media upload API | Not currently exposed                              | No        |

The `create_media()` service is available internally for creating `Media` records, but a dedicated generic `Media` upload API endpoint has not currently been exposed.

---

## 23. Testing

The media implementation includes automated tests covering:

### Access control

* Public media accessible anonymously
* Private media denied to anonymous users
* Private media accessible to the owner
* Private media denied to another authenticated user
* Missing media returns 404

### Validation

* Valid JPEG accepted
* Valid PNG accepted
* Invalid image content rejected
* Files larger than 5 MB rejected
* Images wider than 4096 pixels rejected
* Images taller than 4096 pixels rejected
* Images exceeding the maximum pixel count rejected

### Cleanup

* Physical file deleted when Media record is deleted
* Old physical file deleted when media is replaced

---

## 24. Verification

The following checks have been completed successfully:

```text
python manage.py check
```

Result:

```text
System check identified no issues (0 silenced).
```

Media access tests:

```text
python manage.py test services.tests.test_media
```

Result:

```text
Ran 6 tests
OK
```

Media validation tests:

```text
python manage.py test services.tests.test_media_validation
```

Result:

```text
Ran 7 tests
OK
```

Media cleanup tests:

```text
python manage.py test services.tests.test_media_cleanup
```

Result:

```text
Ran 2 tests
OK
```

---

## 25. Implementation Status

| Media Backend Requirement            | Status    |
| ------------------------------------ | --------- |
| Review existing upload code          | Completed |
| Define supported formats and limits  | Completed |
| Create Media model                   | Completed |
| Create media service                 | Completed |
| Validate uploaded images             | Completed |
| Generate safe filenames              | Completed |
| Separate private/public media        | Completed |
| Implement download/access rules      | Completed |
| Test invalid and large files         | Completed |
| Add cleanup handling                 | Completed |
| Document mobile upload/download flow | Completed |
---

## 26. End-to-End Upload State Model and API Contract

### 26.1 Upload lifecycle

The mobile application and backend follow this lifecycle:

```text
SELECT IMAGE
    |
    v
LOCAL STAGING
    |
    +---- Invalid file or local storage failure
    |          |
    |          v
    |       LOCAL FAILURE
    |
    v
UPLOAD REQUEST
    |
    +---- Network timeout / connection lost
    |          |
    |          v
    |       RETRY PENDING
    |          |
    |          v
    |       UPLOAD REQUEST
    |
    v
SERVER VALIDATION
    |
    +---- Invalid format, size, or image content
    |          |
    |          v
    |       REJECTED
    |
    +---- Server or storage failure
    |          |
    |          v
    |       RETRY / MANUAL RECOVERY
    |
    v
MEDIA STORED
    |
    v
DATABASE RECORD CREATED
    |
    v
SUCCESS RESPONSE
    |
    v
CLIENT RECORDS MEDIA ID
    |
    v
READY FOR DISPLAY OR DOWNLOAD
```

The diagram describes the intended client/server interaction. Local staging and retry state are client responsibilities unless a dedicated server-side upload-session API is introduced.

### 26.2 State definitions

| State | Meaning | Next action |
|---|---|---|
| `selected` | User selected an image | Validate before staging |
| `staged` | Image is available in temporary local storage | Start upload |
| `uploading` | Request is being sent | Wait for response |
| `retry_pending` | A transient network or server failure occurred | Retry with bounded attempts and backoff |
| `rejected` | Validation or authorization failed | Correct the input or credentials |
| `stored` | Server stored the file and created its media record | Process success response |
| `completed` | Client recorded the returned media identifier | Display or download media |
| `failed` | Retry limit reached or a non-recoverable failure occurred | Show error and allow a deliberate retry |

These client-side states are conceptual documentation states; they are not claimed to be persisted by the current backend.

### 26.3 API contract

**Profile image upload**

```http
POST /api/v1/profile/image/
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
```

Form field: `image`

**Service image upload**

```http
POST /api/v1/services/<service_id>/images/
Content-Type: multipart/form-data
```

Authentication and authorization follow the existing endpoint implementation.

The client should treat a successful HTTP response as completion only after it has parsed the response and recorded the returned media identifier, where provided.

### 26.4 Failure and retry rules

- **Invalid image or size:** the server rejects invalid content, unsupported image types, and files exceeding the configured 5 MB limit. Do not retry the unchanged invalid file.
- **Authentication or authorization failure:** refresh credentials or correct permissions. Do not retry indefinitely.
- **Network timeout or lost response:** the client may not know whether the server completed the upload. For service image uploads, retry using the same `Idempotency-Key` and the exact same file.
- **Transient server or storage failure:** clients should use bounded retries, with exponential backoff and jitter, for network errors, HTTP 429, and eligible HTTP 5xx responses. Allow at most three attempts in total. Respect `Retry-After` when provided.
- **Non-retryable responses:** do not automatically retry validation errors or authentication/authorization failures. A 409 response indicating that an upload is still processing should be handled separately from an idempotency-key conflict.
- **Repeated upload:** a successful retry using the same key and identical upload fingerprint returns the original response without creating another image record. Reusing the same key with different upload content returns a conflict.
- **Missing media during download:** report unavailable media and avoid an endless retry loop.

The retry policy is a client-side recommendation; the server does not automatically retry a failed transfer on the client's behalf.

### 26.5 Idempotency and resumability limitations

The service image upload endpoint supports the optional `Idempotency-Key` header. Use the same key for retries of the same image and service. A completed duplicate request returns HTTP 200 with the stored response; a request using the same key with a different upload fingerprint returns HTTP 409. A request already being processed also returns HTTP 409.

The upload is still a **whole-file multipart upload**. Chunked transfer, byte-range upload, and resuming from a partial offset are not implemented. A retry must transmit the complete file again. The configured image size limit is 5 MB.

Idempotency protects against duplicate image records for a completed request, but it does not provide resumable transfer or guarantee that every possible storage failure is automatically recovered. Clients should surface a final error after bounded retries are exhausted.

### 26.6 Booking lifecycle and legal transitions

The booking model in `services/models.py` defines the following legal
transitions. Requests that attempt an invalid transition must be rejected
without changing the booking status.

| Current state | Allowed next states |
|---|---|
| `pending` | `confirmed`, `cancelled`, `payment_failed` |
| `confirmed` | `in_progress`, `cancelled` |
| `in_progress` | `completed` |
| `completed` | None (terminal state) |
| `cancelled` | None (terminal state) |
| `payment_failed` | None (terminal state) |

The cancellation service checks `can_transition_to("cancelled")` before
saving the new status. Regression tests cover attempts to cancel bookings
in `in_progress` and `payment_failed`; both attempts must raise `ValueError`
and leave the original status unchanged.

Payment webhook regression coverage also checks that sending the same
successful webhook twice does not create duplicate payment-success or
booking-confirmation notifications.

### 26.7 Verification checklist

- [x] Valid service image upload succeeds and returns the stored media identifier.
- [x] Invalid image content is rejected.
- [ ] Oversized image rejection verified in the current test run.
- [x] Unauthorized service image upload is rejected.
- [x] Repeated upload with the same idempotency key and identical image does not create a duplicate record.
- [x] Reusing the same key with different image content returns a conflict.
- [x] Targeted service image upload retry tests passed: `python manage.py test services.tests.test_service_image_upload_retries` — 5 tests.
- [x] Existing idempotency tests passed: `python manage.py test services.tests.test_idempotency_reliability` — 6 tests.
- [x] Media tests passed: `python manage.py test services.tests.test_media` — 6 tests.
- [x] Django system check passed: `python manage.py check`.
- [ ] Interrupted network transfer and actual storage-failure recovery have not been verified through an end-to-end fault-injection test.
- [ ] Chunked upload and resume-from-offset are not implemented; clients must resend the complete file on retry.
