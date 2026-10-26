# Workflow Capstone: Upload-to-Result Reliability

**Validation date:** 2026-10-26

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

Result: **9 tests passed in 35.145 seconds (`OK`) on 2026-10-26.**

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

**Overall status: PARTIALLY VERIFIED — final capstone acceptance remains blocked by outstanding end-to-end evidence.**

The following table consolidates the five daily stories for the Reliable Media/Data Upload and Synchronization Workflow. A committed implementation is not, by itself, proof that every acceptance criterion has passed.

| Day | Story | Evidence available | Status and remaining work |
|---|---|---|---|
| Day 1 — 19 October 2026 | End-to-end flow and state model | Commit `e3e0aad` — `Document upload state model and enforce booking transitions`. The workflow diagram, API/recovery contract, booking transition rules, and upload limitations are documented. Three targeted regression tests passed on 23 October 2026 in 16.943 seconds: two invalid cancellation cases and duplicate successful webhook notification deduplication. | **Core criteria verified; full mobile-client-to-result end-to-end evidence and real network/storage failure injection remain outstanding.** |
| Day 2 — 20 October 2026 | Reliable transfer and retry | Original implementation commit `224f2a7`; latest retry/recovery changes are in commit `880a802` (`feat: harden media upload retry and recovery workflow`). The earlier report recorded 8 passing tests. On 2026-10-26, the updated upload retry suite passed 9 tests in 35.145 seconds, including the storage-failure retry regression test. Existing coverage includes validation, duplicate/conflicting requests, ownership enforcement, simulated completion-failure recovery, and upload-to-list integration. | **Partially verified.** Chunked/resumable upload is not implemented. Real network interruption and storage-outage failure injection remain unverified. |
| Day 3 — 21 October 2026 | Idempotent event/API processing | Commit `01ca721` — `Make payment webhooks idempotent`. Earlier validation also reported passing idempotency reliability tests. | **Implementation and test evidence available; acceptance review pending.** Confirm the current test commands/results and document the supported duplicate and out-of-order event behavior and its limitations. |
| Day 4 — 22 October 2026 | Observability and integration tests | Commit `9ffc898` — `test: add observability integration coverage`. The observability test module was run on 23 October 2026; 10 tests passed in 0.020 seconds (`OK`). | **Focused observability tests verified.** Explicitly map evidence for offline mode, timeout, rejection, duplicate submission, and server-error scenarios; do not assume the 10 tests cover every scenario without inspecting the tests. |
| Day 5 — 23 October 2026 | Workflow capstone | Commit `8ea27d9` — `test: document upload-to-result reliability`. The report originally recorded 8 upload retry/recovery tests; the latest upload retry suite passed 9 tests. The report also records three booking workflow tests, a passing Django system check, and an upload-to-list API integration test. | **Partially verified; final acceptance blocked.** A complete mobile-client-to-result run and real network/storage failure injection have not been verified. |

### Consolidated acceptance decision

- The implementation, test coverage, documentation, and commit history provide evidence of substantial progress across all five stories.
- The focused upload, booking, and observability test results are evidence of component behavior; they do not establish that the entire mobile-client-to-result workflow has passed as one integrated run.
- Chunked/resumable uploads are not implemented, and real network/storage failure injection remains outstanding.
- The exact coverage of each daily story must be checked against its individual acceptance criteria before marking that story fully complete.
- The final mini-project remains **partially verified** until the remaining critical integration evidence is collected or explicitly accepted as a documented limitation by the project evaluator.

## 9. Completion Checklist

- [x] Existing implementation and workflow documented.
- [x] Latest upload retry/recovery run recorded: 9 tests passed in 35.145 seconds on 2026-10-26.
- [x] Booking workflow test results recorded: 3 tests passed in the reported run.
- [x] Django configuration check passed in the reported run.
- [x] Focused upload-to-list API integration test verified.
- [x] Observability test module verified: 10 tests passed in the run on 23 October 2026.
- [x] Five daily stories listed with evidence and explicit remaining work.
- [x] Git history reviewed; before this report correction, the branch was five commits ahead of `origin/release/1.0.0`. Five untracked backup files are intentionally preserved.
- [ ] Full mobile-client-to-result end-to-end journey verified.
- [ ] Real network interruption and storage-outage failure-injection tests verified.
- [ ] Evidence mapped to every individual daily-story acceptance criterion.
- [ ] Final documentation diff reviewed and validated.
- [x] Latest upload-retry implementation and regression test committed as `880a802`. The previous report version is committed as `1de5286`; these corrections remain uncommitted pending review; pushing remains outstanding.

**Release note:** The report-focused commit at the start of this review was `b764953`; the latest upload-retry implementation commit is `880a802`. Before this report correction, the branch was five commits ahead of `origin/release/1.0.0`. The previous report version is committed as `1de5286`; these corrections remain uncommitted pending review. Five untracked backup files remain untouched. Review the documentation diff and run `git diff --check` before committing. Do not push unless explicitly approved, and do not mark full mobile end-to-end testing or real network/storage failure injection complete without evidence.
