
import hashlib
import json
from datetime import timedelta

from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from .models import IdempotencyRecord


IDEMPOTENCY_EXPIRY_HOURS = 24


class IdempotencyConflict(APIException):
    status_code = 409
    default_detail = (
        "The same Idempotency-Key was already used "
        "with a different request."
    )
    default_code = "idempotency_conflict"


def build_request_hash(data):
    """
    Create a deterministic SHA-256 hash
    from the request payload.
    """

    normalized_data = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

    return hashlib.sha256(
        normalized_data.encode("utf-8")
    ).hexdigest()


def get_idempotency_key(request):
    """
    Read and validate the Idempotency-Key header.
    """

    key = request.headers.get("Idempotency-Key")

    if not key:
        return None

    key = key.strip()

    if not key:
        raise ValidationError(
            {
                "Idempotency-Key": (
                    "Idempotency-Key cannot be empty."
                )
            }
        )

    if len(key) > 100:
        raise ValidationError(
            {
                "Idempotency-Key": (
                    "Idempotency-Key must not exceed "
                    "100 characters."
                )
            }
        )

    return key


def get_existing_record(
    *,
    user,
    key,
    operation,
    request_hash,
):
    """
    Find an active idempotency record.

    Expired records are ignored.

    Raises IdempotencyConflict when the same key
    is reused with a different request payload.
    """

    record = (
        IdempotencyRecord.objects
        .filter(
            user=user,
            key=key,
            operation=operation,
            expires_at__gt=timezone.now(),
        )
        .first()
    )

    if record is None:
        return None

    if record.request_hash != request_hash:
        raise IdempotencyConflict(
            "The same Idempotency-Key cannot be reused "
            "for a different request."
        )

    return record


def create_idempotency_record(
    *,
    user,
    key,
    operation,
    request_hash,
):
    """
    Atomically create an idempotency record.

    Returns:
        (record, is_new)

    is_new=True:
        This database transaction created the record.

    is_new=False:
        Another request already created the record.
    """

    expires_at = (
        timezone.now()
        + timedelta(hours=IDEMPOTENCY_EXPIRY_HOURS)
    )

    try:
        with transaction.atomic():
            record = IdempotencyRecord.objects.create(
                user=user,
                key=key,
                operation=operation,
                request_hash=request_hash,
                status="PROCESSING",
                expires_at=expires_at,
            )

        return record, True

    except IntegrityError:
        record = (
            IdempotencyRecord.objects.get(
                user=user,
                key=key,
                operation=operation,
            )
        )

        if record.request_hash != request_hash:
            raise IdempotencyConflict(
                "The same Idempotency-Key cannot be reused "
                "for a different request."
            )

        return record, False


def start_idempotent_request(
    *,
    user,
    key,
    operation,
    request_data,
):
    """
    Start an idempotent request safely.

    Returns:
        (record, is_new)

    is_new=True:
        This request created the idempotency record
        and is allowed to execute the business operation.

    is_new=False:
        Another request already owns this idempotency key.
    """

    request_hash = build_request_hash(
        request_data,
    )

    existing_record = get_existing_record(
        user=user,
        key=key,
        operation=operation,
        request_hash=request_hash,
    )

    if existing_record is not None:
        return existing_record, False

    return create_idempotency_record(
        user=user,
        key=key,
        operation=operation,
        request_hash=request_hash,
    )


def complete_idempotent_request(
    *,
    record,
    response_status,
    response_body,
    resource_type=None,
    resource_id=None,
):
    """
    Store the successful response so mobile retries
    receive the same result.

    DjangoJSONEncoder converts values such as UUID,
    Decimal, date, and datetime into JSON-safe values.
    """

    json_safe_response = json.loads(
        json.dumps(
            response_body,
            cls=DjangoJSONEncoder,
        )
    )

    record.status = "COMPLETED"
    record.response_status = response_status
    record.response_body = json_safe_response
    record.resource_type = resource_type
    record.resource_id = resource_id

    record.save(
        update_fields=[
            "status",
            "response_status",
            "response_body",
            "resource_type",
            "resource_id",
        ]
    )

    return record


def fail_idempotent_request(record):
    """
    Mark an idempotent request as failed.

    The record remains available for auditing,
    but a future retry can be handled explicitly
    by the calling business logic.
    """

    record.status = "FAILED"

    record.save(
        update_fields=[
            "status",
        ]
    )

    return record
