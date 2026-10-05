# External Payment API Integration Research

## 1. Selected External Service

### Provider

Stripe

### Integration

Stripe Payment API using Stripe's test environment.

### Purpose

The existing Django application currently uses a mock payment workflow. The purpose of this integration is to connect the application's payment workflow to an external payment provider while keeping the integration secure, testable, and production-oriented.

The integration will initially use Stripe test mode so that no real customer payments are processed.

---

## 2. Why Stripe Was Selected

Stripe was selected because:

* It provides a well-established payment API.
* It supports test/sandbox payments.
* It provides API-based payment processing.
* It supports idempotency for safe retrying of requests.
* It provides webhook events for asynchronous payment status updates.
* It provides structured API errors.
* It can be integrated with Django REST Framework.
* The existing project already contains payment, booking, notification, and webhook functionality.

The existing Django payment service can therefore be extended instead of creating a completely separate payment architecture.

---

## 3. Authentication

Stripe API requests are authenticated using a secret API key.

The secret key must never be hard-coded in Python source code, committed to Git, or returned in an API response.

The application will store the Stripe secret key in an environment variable.

Example:

```text
STRIPE_SECRET_KEY=<stripe-test-secret-key>
```

The actual secret value must not be stored in this document.

The application will read the value from Django configuration at runtime.

---

## 4. Environment

The integration will initially use Stripe test mode.

Test mode allows the application to develop and test the integration without processing real payments.

The application must use test credentials during development and automated testing.

Production credentials must never be placed in source code or test files.

---

## 5. Payment API

The integration will use Stripe's PaymentIntent-based payment flow.

A PaymentIntent represents the application's intention to collect a payment and provides a Stripe identifier that can be associated with the local Payment record.

The high-level flow is:

```text
Customer
    |
    v
Django REST API
    |
    v
Payment Service
    |
    v
Stripe Payment API
    |
    v
Stripe PaymentIntent
    |
    v
Stripe payment status
```

The Django application will maintain its own Payment record and associate it with the external Stripe payment identifier.

---

## 6. Request Data

The external payment request will contain payment information required by Stripe.

The integration service will construct the provider request rather than allowing the client to directly control sensitive provider parameters.

Typical information includes:

* Amount
* Currency
* Payment method information where applicable
* Description or metadata
* Idempotency information when required

The amount must be calculated and validated by the backend using the application's booking/payment data.

The client must not be trusted to determine the final payable amount.

---

## 7. Response Data

Stripe returns a structured response containing information about the payment operation.

The integration should extract only the fields required by the application.

Important information may include:

* External payment identifier
* Payment status
* Amount
* Currency
* Error information when applicable

The complete provider response should not automatically be stored in the database or returned to the client.

Only required application data should be persisted.

---

## 8. Local Payment Mapping

The existing Django Payment model will remain the application's source of truth for the local payment record.

The external Stripe payment identifier should be associated with the local Payment record.

Conceptually:

```text
Local Payment
    |
    +-- Booking
    |
    +-- payment_status
    |
    +-- payment_method
    |
    +-- transaction_id
    |
    +-- Stripe PaymentIntent ID
```

The exact database field will be determined after reviewing the existing Payment model.

---

## 9. Idempotency

Payment creation must protect against duplicate requests.

A network timeout can occur after Stripe processes a request but before Django receives the response.

Without idempotency, retrying the same request could potentially create another payment operation.

Therefore, payment creation should use an idempotency key where appropriate.

The idempotency key must be deterministic for the operation being retried and must not expose sensitive information.

The application should not generate a new unrelated idempotency key for every retry of the same payment operation.

---

## 10. Request Timeout

External API requests must have an explicit timeout.

The application must never wait indefinitely for the payment provider.

The integration service should define a reasonable connection/read timeout appropriate for the payment operation.

If the provider does not respond within the configured timeout, the application should:

1. Treat the request as an external integration failure.
2. Avoid exposing internal exception details to the client.
3. Log the failure safely.
4. Preserve the local payment state so it can be reconciled or retried safely.
5. Use idempotency when retrying the same external operation.

---

## 11. Retry Strategy

Retries must be limited and safe.

The application should not blindly retry every payment error.

Retries are appropriate primarily for transient failures such as certain network failures or temporary provider/server failures.

The application should not retry permanent failures such as:

* Invalid authentication
* Invalid payment parameters
* Invalid request data
* Card/payment-method failures that require customer action

Retries must use the same idempotency key for the same payment operation where supported.

A retry policy should have a small maximum number of attempts and controlled delay.

---

## 12. Error Handling

The integration must distinguish between different failure categories.

### Validation errors

The request is invalid.

Example:

```text
Invalid amount
Invalid currency
Missing required data
```

These should not be retried.

### Authentication errors

The configured Stripe credentials are invalid.

These should not be retried repeatedly.

The configuration must be corrected.

### Network errors

The application cannot communicate with Stripe.

These may be handled as transient integration failures and may be retried safely when idempotency is available.

### Provider/server errors

Stripe may temporarily return an error indicating a server-side or temporary problem.

These may be eligible for a limited retry.

### Payment failure

The external payment operation itself may fail.

This should be represented as a failed payment rather than treating every payment failure as a Django application error.

---

## 13. Webhook Integration

Payment status can change asynchronously.

The application will therefore use a Stripe webhook endpoint to receive relevant payment events.

The high-level flow will be:

```text
Stripe
   |
   | Webhook
   v
Django webhook endpoint
   |
   v
Verify webhook signature
   |
   v
Find local Payment
   |
   v
Update Payment
   |
   v
Update Booking
   |
   v
Send notification
```

The existing project already has payment webhook functionality, so the Stripe webhook integration should extend the existing architecture rather than create an unrelated webhook system.

---

## 14. Webhook Security

Webhook requests must be verified before the application trusts their contents.

The Stripe webhook signing secret must be stored in an environment variable.

Example:

```text
STRIPE_WEBHOOK_SECRET=<stripe-webhook-secret>
```

The real secret must never be committed to Git.

The application must verify the provider's webhook signature before updating payment or booking records.

Invalid webhook signatures must be rejected.

---

## 15. Webhook Idempotency

Webhook events may be delivered more than once.

The application must therefore avoid applying the same payment event multiple times.

Webhook processing should be designed so that duplicate events do not:

* Confirm a booking incorrectly.
* Create duplicate notifications.
* Corrupt the payment status.
* Perform duplicate business operations.

The exact implementation will be determined after reviewing the existing Payment and Notification models.

---

## 16. Safe Logging

Integration failures should be logged for troubleshooting.

Logs must not contain:

* Stripe secret API keys
* Webhook signing secrets
* Passwords
* Authentication tokens
* Full payment credentials
* Sensitive payment-method information

Safe information may include:

* Local payment ID
* Booking ID
* External provider payment ID
* Error category
* HTTP status where appropriate
* Retry attempt number
* Timestamp

The integration should log enough information to diagnose failures without exposing secrets.

---

## 17. Success Handling

A successful external payment should result in:

```text
Stripe payment succeeds
        |
        v
Payment marked SUCCESS
        |
        v
Booking confirmed
        |
        v
Customer notification
        |
        v
WebSocket booking update
```

The existing `process_payment_webhook()` business logic already performs the local payment/booking update and notification workflow, so it can be adapted for Stripe events.

---

## 18. Failure Handling

A failed payment should not automatically confirm the booking.

The expected flow is:

```text
Stripe payment fails
        |
        v
Payment marked FAILED
        |
        v
Booking remains unconfirmed
        |
        v
Customer receives appropriate failure information
```

The exact mapping will be implemented after reviewing the current Booking and Payment models.

---

## 19. Testing Strategy

The integration must be tested without using real payments.

Automated tests should cover at least:

### Successful payment

```text
Django -> Stripe mock/test response -> SUCCESS
```

### Failed payment

```text
Django -> Stripe failure -> FAILED
```

### Timeout

```text
Django -> Stripe timeout -> safe integration failure
```

### Network failure

```text
Django -> network error -> safe integration failure
```

### Invalid provider response

```text
Django -> unexpected response -> safe failure
```

### Authentication failure

```text
Django -> invalid Stripe credentials -> safe failure
```

### Duplicate request

```text
Same payment request
        |
        v
Same idempotency key
        |
        v
No duplicate payment operation
```

### Webhook

Test:

* Valid webhook
* Invalid signature
* Duplicate webhook
* Successful payment event
* Failed payment event

---

## 20. Security Requirements

The integration must follow these rules:

* Never hard-code Stripe secrets.
* Store credentials only in environment variables.
* Never commit secrets to Git.
* Never return secrets through the API.
* Verify webhook signatures.
* Use explicit request timeouts.
* Use safe retry behavior.
* Use idempotency for retryable payment creation.
* Validate payment amounts on the server.
* Do not trust client-provided payment amounts.
* Do not log secrets.
* Do not expose raw provider exceptions to API clients.

---

## 21. Planned Django Architecture

The existing payment service will be extended rather than replaced.

Planned structure:

```text
services/
    payment_service.py
        |
        +-- local payment business logic
        |
        +-- external payment integration

config/
    settings.py
        |
        +-- Stripe configuration

.env
    |
    +-- STRIPE_SECRET_KEY
    +-- STRIPE_WEBHOOK_SECRET

tests/
    |
    +-- external payment integration tests
```

A separate provider client/integration layer may be introduced if needed to keep external API communication separate from business logic.

---

## 22. Planned Implementation Order

The implementation will follow this order:

1. Complete provider research.
2. Document authentication and API request/response behavior.
3. Review the existing Payment model and payment API.
4. Create the external payment integration service.
5. Configure Stripe credentials through environment variables.
6. Add request timeout and safe retry handling.
7. Add Stripe test-mode/sandbox integration.
8. Implement success and failure handling.
9. Add safe integration failure logging.
10. Add automated integration tests.
11. Document setup and troubleshooting.

---

## 23. Current Project Integration

The existing project already contains:

* `services/payment_service.py`
* Payment model
* Payment API endpoints
* Payment webhook endpoint
* Booking/payment relationship
* Notification handling
* WebSocket booking updates
* Payment journey tests
* Environment-based payment webhook configuration

Therefore, the Stripe integration will be implemented as an extension of the existing payment architecture rather than as a completely separate payment system.

---

## 24. Research Conclusion

Stripe test mode is suitable for integrating an external payment provider into this Django REST API.

The integration will use:

* Environment-based credentials
* Stripe test mode
* PaymentIntent-based payment processing
* Explicit request timeouts
* Limited safe retries
* Idempotency
* Webhook signature verification
* Safe error handling
* Secret-free logging
* Automated success/failure testing

No production payment credentials will be used during development or automated testing.
# Step 2 — Stripe Provider API Documentation

## 1. Provider API

The selected external payment provider is Stripe.

The application will use Stripe's PaymentIntent API for payment processing.

The PaymentIntent API allows the application to create and track a payment operation.

The Django application will communicate with Stripe over HTTPS.

The integration will use Stripe's test environment during development.

---

## 2. Authentication

Stripe API requests require authentication using a Stripe secret API key.

The secret key will be stored in an environment variable.

Example:

```text
STRIPE_SECRET_KEY=<test-secret-key>
```

The actual key must never be placed in:

* Python source code
* Git repository
* Documentation
* Automated test source
* API responses
* Application logs

The Django application will load the key from its environment configuration.

The secret key is used by the server-side integration service when communicating with Stripe.

The frontend/client application must never receive the Stripe secret API key.

---

## 3. PaymentIntent Request

The Django application will create a PaymentIntent through the Stripe API.

Conceptually, the request contains:

```json
{
  "amount": 50000,
  "currency": "inr"
}
```

The amount is represented in the smallest currency unit.

For example:

```text
₹500.00
```

would be represented as:

```text
50000
```

when using a currency whose smallest unit is one-hundredth of the major currency unit.

The backend must calculate and validate the amount using the application's booking/payment information.

The client must not be trusted to determine the final payment amount.

---

## 4. PaymentIntent Response

A successful PaymentIntent creation returns a structured object from Stripe.

A simplified example is:

```json
{
  "id": "pi_test_example",
  "object": "payment_intent",
  "amount": 50000,
  "currency": "inr",
  "status": "requires_payment_method"
}
```

The actual Stripe response contains additional fields.

The Django application should extract only the fields required by the application.

For example:

```text
Stripe PaymentIntent ID
Payment amount
Currency
Payment status
```

The complete provider response should not automatically be stored in the application's database.

---

## 5. Mapping Stripe Data to Django

The existing application has a local Payment model.

The integration will map the external Stripe payment identifier to the local payment record.

Conceptually:

```text
Django Payment
    |
    +-- Booking
    +-- payment_status
    +-- payment_method
    +-- transaction_id
    |
    +-- Stripe PaymentIntent ID
```

The exact database field will be determined after reviewing the current Payment model.

The local Payment record remains important because the application needs to maintain its own relationship between:

```text
Customer
    ↓
Booking
    ↓
Payment
    ↓
External Stripe Payment
```

---

## 6. Idempotency

Payment requests must be protected against accidental duplicate operations.

For example:

```text
Django
   |
   | Create PaymentIntent
   |
   X Network timeout
```

The application cannot immediately determine whether Stripe processed the request.

Retrying the operation without protection could result in an unintended duplicate payment operation.

Therefore, the integration should use Stripe's idempotency mechanism for operations where retries are possible.

The same idempotency key should be reused when retrying the same logical operation.

A new unrelated idempotency key should not be generated for every retry.

---

## 7. HTTP Communication

The Django server will communicate with Stripe using HTTPS.

The external API client must:

* Use the configured Stripe secret key.
* Use HTTPS.
* Set an explicit timeout.
* Handle network failures.
* Handle provider errors.
* Avoid exposing raw provider exceptions to API clients.

The integration service will be responsible for translating external provider failures into safe application-level errors.

---

## 8. Example Successful Flow

A successful payment integration flow will look like:

```text
Customer
   |
   | Create booking/payment
   v
Django API
   |
   | Validate booking and amount
   v
Payment Service
   |
   | Create PaymentIntent
   v
Stripe
   |
   | PaymentIntent response
   v
Payment Service
   |
   | Store external payment information
   v
Django Payment
```

After the payment is successfully completed, the application's webhook processing can update the local payment and booking status.

---

## 9. Example Failure Flow

If Stripe rejects the request:

```text
Django
   |
   | Payment request
   v
Stripe
   |
   | Error
   v
Payment Service
   |
   +-- Log safe error
   |
   +-- Do not expose secret/internal details
   |
   +-- Keep payment state consistent
   |
   v
Django API
```

The API should return a controlled error response rather than exposing the raw Stripe exception or secret configuration.

---

## 10. Webhook API

Payment processing may involve asynchronous status changes.

Stripe can send webhook events to the Django application.

The application's webhook flow will be:

```text
Stripe
   |
   | HTTPS webhook
   v
Django webhook endpoint
   |
   | Verify signature
   v
Payment Service
   |
   | Update Payment
   v
Booking
   |
   +-- Confirm booking when appropriate
   |
   +-- Send notification
```

The webhook signing secret will be stored in an environment variable.

Example:

```text
STRIPE_WEBHOOK_SECRET=<webhook-signing-secret>
```

The actual secret must never be committed to Git.

---

## 11. Authentication vs Webhook Verification

The Stripe API key and webhook signing secret have different purposes.

### Stripe secret API key

Used when:

```text
Django → Stripe
```

The Django application uses the secret key to authenticate API requests.

### Stripe webhook signing secret

Used when:

```text
Stripe → Django
```

The Django application uses the signing secret to verify that the webhook was sent by Stripe and has not been improperly modified.

They must therefore be stored as separate environment variables.

---

## 12. Provider Data That Must Not Be Trusted Blindly

The Django application must validate data received from Stripe before applying important business changes.

For example, before confirming a booking, the application should verify that the webhook/payment event corresponds to the expected local payment.

Important checks include:

* External payment identifier
* Local payment record
* Payment amount where applicable
* Payment currency where applicable
* Payment status
* Webhook signature

The application must not confirm an unrelated booking merely because a request claims that a payment succeeded.

---

## 13. API Error Handling

The integration must handle provider errors safely.

Possible categories include:

### Authentication failure

The configured Stripe credentials are invalid.

Action:

```text
Do not retry repeatedly.
Log a safe configuration error.
Return a controlled application error.
```

### Invalid request

The request contains invalid data.

Action:

```text
Do not retry.
Validate and correct the request.
```

### Network failure

The application cannot communicate with Stripe.

Action:

```text
Treat as a transient integration failure.
Use limited retry logic where safe.
Use the same idempotency key for the same operation.
```

### Timeout

Stripe does not respond within the configured timeout.

Action:

```text
Treat as an external integration failure.
Do not assume that the payment was unsuccessful.
Use idempotency/reconciliation when retrying.
```

### Provider/server failure

Stripe temporarily reports a server-side failure.

Action:

```text
A limited retry may be appropriate.
The retry must be safe and controlled.
```

### Payment failure

The payment itself fails.

Action:

```text
Mark the local payment appropriately.
Do not confirm the booking.
Return a safe payment failure response.
```

---

## 14. Security Requirements

The integration must follow these requirements:

1. Use HTTPS for provider communication.
2. Store the Stripe API key in an environment variable.
3. Store the webhook signing secret separately.
4. Never commit credentials to Git.
5. Never return credentials in API responses.
6. Never log credentials.
7. Verify webhook signatures.
8. Validate external payment information.
9. Use idempotency for retryable payment operations.
10. Use explicit request timeouts.
11. Do not expose raw Stripe exceptions to clients.
12. Do not allow the client to determine the trusted payment amount.

---

## 15. Documentation Status

Step 2 documents:

* Provider API: Stripe PaymentIntent API
* Authentication: server-side Stripe secret API key
* Request: payment amount and currency
* Response: PaymentIntent ID and payment status
* Idempotency: protection against duplicate operations
* Webhooks: asynchronous payment status updates
* Webhook authentication: signing-secret verification
* Error handling: controlled provider failure handling
* Security: environment-based credentials and safe logging

The next step is to implement the Django external integration service.
