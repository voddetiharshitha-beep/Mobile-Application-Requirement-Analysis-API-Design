# Workflow Capstone: Upload-to-Result Reliability

**Validation date:** 2026-10-23

## 1. Objective

Document the upload workflow, retries, recovery, privacy/security boundaries, test evidence, and troubleshooting steps using the project's existing implementation.

## 2. Workflow State Diagram

```text
Select image
    |
Stage file on client
    |
Upload multipart request with Idempotency-Key
    |
Authenticate and authorize
    |-- Failure --> Reject request
    |
Validate image type, size, and dimensions
    |-- Failure --> Return validation error
    |
Check idempotency key and content fingerprint
    |-- Same key + same content --> Replay/recover existing result
    |-- Same key + different content --> 409 Conflict
    |-- Request processing --> 409 Conflict; retry later
    |
Persist image and resource reference
    |
Complete idempotency record
    |-- Completion failure --> Retry with same key and exact same file
    |
Return API result
    |
Client records media ID and displays result
```

This diagram describes the documented workflow; it does not prove every branch was tested in a single end-to-end run.

## 3. API and Retry Contract

- `POST /api/v1/services/<service_id>/images/` — upload an image.
- `GET /api/v1/services/<service_id>/images/` — list service images.
- `DELETE /api/v1/services/<service_id>/images/<image_id>/` — delete an image.

Expected behavior:

- A valid first upload returns `201 Created`.
- The same key and identical content can replay the existing result with `200 OK`.
- The same key with different content returns `409 Conflict`.
- An already-processing request can return `409 Conflict`.
- Invalid or oversized images are rejected.
- Users who do not own the service cannot upload images.
- If resource creation succeeds but idempotency completion fails, retry using the same key and file to recover the existing resource.

Use bounded retries and backoff. Do not repeatedly retry invalid input or authorization failures.

## 4. Privacy and Security Boundaries

- Enforce authentication and service ownership on the server.
- Validate image content, format, size, and dimensions; do not trust client-provided filenames or MIME types alone.
- Use test accounts and synthetic images during demonstrations.
- Never expose passwords, tokens, API keys, webhook secrets, or customer personal data in logs or screenshots.
- A media ID is not proof of authorization. Check access on every protected read and delete.
- Keep public and private media access rules distinct.
- Do not expose filesystem paths or stack traces in client-facing errors.
- Review HTTPS, secrets, storage permissions, and database access separately before production deployment.

## 5. Verified Test Evidence

Validation date: 2026-10-23.

### Upload retry and recovery

Command:

`python manage.py test services.tests.test_service_image_upload_retries --keepdb --verbosity 2`

Result: **8 tests passed in 34.420 seconds (`OK`).**

Coverage includes successful upload, duplicate protection, conflicting content, invalid and oversized images, ownership enforcement, simulated idempotency-completion failure recovery, and upload-to-list API integration confirming the created image is retrievable without duplication.

### Booking workflow

Command:

`python manage.py test services.tests.test_automated_workflow --keepdb --verbosity 2`

Result: **3 tests passed in 13.111 seconds (`OK`).**

Coverage includes invalid booking transitions and duplicate idempotent booking requests.

### Django configuration

Command:

`python manage.py check`

Result: **No issues identified (0 silenced).**

These are separate component tests, not proof of one complete mobile-to-result integration run.

## 6. Troubleshooting

| Symptom | Action |
|---|---|
| `400 Bad Request` | Check image format, content, size, and dimensions. Correct invalid input before retrying. |
| `403 Forbidden` | Verify authentication, service ownership, and permissions. |
| `404 Not Found` | Check the resource ID and access permissions. |
| `409 Conflict` | Determine whether the key is processing or was reused with different content. Preserve the original key and file for retries. |
| Client timeout | The upload may already have succeeded. Retry with the same key and exact same file. |
| Completion failure | Retry with the same key and file; verify that only one resource exists. |
| Redis-dependent feature fails | Verify Redis availability and configuration. Distinguish Redis problems from image-storage failures. |
| Database record exists but file is missing | Investigate storage and logs; use the documented recovery procedure. |

Avoid manually deleting database records or stored files as a first recovery step.

## 7. Known Limitations

- Uploads use whole-file multipart requests; chunked and resumable uploads are not implemented.
- The completion-failure test is simulated; a real storage outage and interrupted network have not been verified end to end.
- Upload and booking suites passed separately; a combined mobile-client-to-result test remains to be verified.
- A passing Django system check does not prove production readiness.
- Production performance and reliability require deployment-specific measurements.

## 8. Daily Story Acceptance Status

- **Status: BLOCKED pending consolidated evidence.** This report does not yet list all five daily stories individually with their completion status and supporting evidence. Do not mark this acceptance criterion complete until each story is listed as completed with evidence or explicitly blocked with a reason.

## 9. Completion Checklist

- [x] Existing implementation reviewed.
- [x] Upload retry/recovery tests passed.
- [x] Booking workflow tests passed.
- [x] Django system check passed.
- [x] State diagram, API contract, security boundaries, and troubleshooting documented.
- [x] Focused upload-to-list API integration test verified.
- [ ] Full mobile-client-to-result end-to-end and real network/storage failure-injection tests verified.
- [ ] Final Git diff reviewed.
- [ ] Changes committed and pushed.
