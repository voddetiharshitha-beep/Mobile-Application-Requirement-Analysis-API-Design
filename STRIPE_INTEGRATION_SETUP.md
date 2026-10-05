# Stripe External Payment Integration Setup

## 1. Overview

This document explains how the Django REST API integrates with Stripe
for external payment processing.

The integration uses Stripe PaymentIntent API in Stripe test mode.

The integration provides:

- Secure environment-based Stripe credentials
- Stripe PaymentIntent creation
- HTTP timeout configuration
- Automatic retry configuration
- Idempotency protection
- Safe error handling
- Safe integration failure logging
- Mocked automated tests
- Payment journey validation
- Failure response validation

---

## 2. Prerequisites

The following are required:

- Python 3.13+
- Django
- Django REST Framework
- PostgreSQL
- Redis
- A Stripe account
- Stripe test-mode API credentials

The Stripe Python SDK is installed in the project.

Verify the installed version with:

```powershell
python -c "import stripe; print(stripe.VERSION)"