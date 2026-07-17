"""``/api/users/v1/users`` — User endpoints (superuser-only surface).

Endpoints:
- ``GET    /``          — list, optional ``?search=``/``?is_active=`` filters
- ``POST   /``          — create (password-less), returns 201 with ETag header
- ``POST   /bulk/``     — bulk create, per-row results, capped per request
- ``POST   /verify-emails/``       — bulk email verification, per-row results
- ``GET    /{uuid}/``   — detail, sets ETag header
- ``PATCH  /{uuid}/``   — partial update, requires ``If-Match``
- ``POST   /{uuid}/verify-email/`` — mark the allauth email record verified
- ``DELETE /{uuid}/``   — permanent delete (see below)

DELETE is irreversible and destructive: installed apps may reference users
with ``on_delete=CASCADE``, so deleting a user removes their related
records across the project. Deactivation (``PATCH {"is_active": false}``)
is the preferred removal for accounts in active use. Superusers are
deletable — except the acting account itself (Wagtail admin rule);
GDPR-style erasure is a future dedicated operation.

Business logic lives in ``UserService.admin`` (service layer); rule
violations raise ``django.core.exceptions.ValidationError`` which the
shared API instance translates into a 422 response. Passwords are never
accepted: users are created with an unusable password and no login access.
"""

from __future__ import annotations

from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpRequest, HttpResponse
from ninja import Query, Router
from ninja.errors import HttpError
from wagtail.search.backends import get_search_backend

from phoxtail.users.api.v1._helpers import (
    require_if_match,
    resolve_gender,
    resolve_user,
    user_detail,
    user_etag,
    user_summary,
)
from phoxtail.users.api.v1.schemas import (
    EmailVerification,
    EmailVerificationBulk,
    EmailVerificationBulkResult,
    Error,
    UserBulkCreate,
    UserBulkResult,
    UserCreate,
    UserList,
    UserUpdate,
)
from phoxtail.users.api.v1.schemas import (
    User as UserSchema,
)
from phoxtail.users.services import UserService

router = Router()

# Rows accepted by a single bulk request. Larger imports must be chunked
# by the client — keeps per-request work and response sizes bounded.
BULK_MAX_ROWS = 100


def _create_kwargs(payload: UserCreate) -> dict:
    """Translate a create payload into ``UserService.admin.create`` kwargs."""
    kwargs: dict = {
        "email": payload.email,
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "is_active": payload.is_active,
    }
    if payload.username is not None:
        kwargs["username"] = payload.username
    if payload.born_at is not None:
        kwargs["born_at"] = payload.born_at
    if payload.gender_uuid is not None:
        kwargs["gender"] = resolve_gender(payload.gender_uuid)
    if payload.country is not None:
        kwargs["country"] = payload.country
    if payload.phone_number is not None:
        kwargs["phone_number"] = payload.phone_number
    return kwargs


@router.get(
    "/",
    response={200: UserList, 403: Error},
    summary="List Users",
)
def list_users(
    request: HttpRequest,
    search: str | None = Query(None, description="Prefix search on email, username, first or last name."),
    is_active: bool | None = Query(None, description="Filter by active state."),
):
    qs = get_user_model().objects.all()
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    if search:
        qs = get_search_backend().autocomplete(search, qs)

    users = [user_summary(u) for u in qs]
    return {"users": users, "total": len(users)}


@router.post(
    "/",
    response={201: UserSchema, 403: Error, 404: Error, 422: Error},
    summary="Create a User (password-less, no email sent)",
)
def create_user(
    request: HttpRequest,
    response: HttpResponse,
    payload: UserCreate,
):
    user = UserService().admin.create(request=request, **_create_kwargs(payload))
    response["ETag"] = user_etag(user)
    return 201, user_detail(user)


@router.post(
    "/bulk/",
    response={200: UserBulkResult, 403: Error, 422: Error},
    summary="Bulk create Users (per-row results, no email sent)",
)
def bulk_create_users(request: HttpRequest, payload: UserBulkCreate):
    """Create up to ``BULK_MAX_ROWS`` users in one request.

    Rows are processed independently — each row is atomic on its own, and
    a failing row (e.g. duplicate email) never aborts the batch.
    """
    if len(payload.users) > BULK_MAX_ROWS:
        raise HttpError(
            422,
            f"Too many rows: {len(payload.users)} (max {BULK_MAX_ROWS} per request). "
            "Split the import into smaller batches.",
        )

    service = UserService()
    results = []
    created = failed = 0
    for index, row in enumerate(payload.users):
        try:
            user = service.admin.create(request=request, **_create_kwargs(row))
        except (DjangoValidationError, HttpError) as exc:
            failed += 1
            detail = "; ".join(exc.messages) if isinstance(exc, DjangoValidationError) else str(exc)
            results.append({"index": index, "status": "error", "uuid": None, "email": row.email, "detail": detail})
        else:
            created += 1
            results.append(
                {"index": index, "status": "created", "uuid": user.uuid, "email": user.email, "detail": None}
            )
    return {"results": results, "created": created, "failed": failed}


@router.post(
    "/verify-emails/",
    response={200: EmailVerificationBulkResult, 403: Error, 422: Error},
    summary="Bulk verify email addresses (no email sent)",
)
def bulk_verify_emails(request: HttpRequest, payload: EmailVerificationBulk):
    """Mark up to ``BULK_MAX_ROWS`` users' emails verified, independently per row."""
    if len(payload.user_uuids) > BULK_MAX_ROWS:
        raise HttpError(
            422,
            f"Too many rows: {len(payload.user_uuids)} (max {BULK_MAX_ROWS} per request). "
            "Split the request into smaller batches.",
        )

    results = []
    verified = already_verified = failed = 0
    for index, user_uuid in enumerate(payload.user_uuids):
        try:
            user = resolve_user(user_uuid)
            status = user.service.admin.verify_email()
        except HttpError as exc:
            failed += 1
            results.append({"index": index, "uuid": user_uuid, "status": "error", "email": None, "detail": str(exc)})
        else:
            if status == "verified":
                verified += 1
            else:
                already_verified += 1
            results.append({"index": index, "uuid": user.uuid, "status": status, "email": user.email, "detail": None})
    return {
        "results": results,
        "verified": verified,
        "already_verified": already_verified,
        "failed": failed,
    }


@router.get(
    "/{user_uuid}/",
    response={200: UserSchema, 403: Error, 404: Error},
    summary="Show a User by UUID",
)
def get_user(
    request: HttpRequest,
    response: HttpResponse,
    user_uuid: UUID,
):
    user = resolve_user(user_uuid)
    response["ETag"] = user_etag(user)
    return user_detail(user)


@router.patch(
    "/{user_uuid}/",
    response={200: UserSchema, 403: Error, 404: Error, 412: Error, 422: Error, 428: Error},
    summary="Update a User by UUID (optimistic concurrency)",
)
def update_user(
    request: HttpRequest,
    response: HttpResponse,
    user_uuid: UUID,
    payload: UserUpdate,
):
    """Apply the fields present in the payload, guarded by ``If-Match``."""
    user = resolve_user(user_uuid)
    require_if_match(request, user_etag(user))

    data: dict = {}
    for field in ("first_name", "last_name", "email", "username", "is_active"):
        if field in payload.model_fields_set and getattr(payload, field) is not None:
            data[field] = getattr(payload, field)
    # Genuinely nullable fields: explicit null clears the value.
    for field in ("born_at", "country", "phone_number"):
        if field in payload.model_fields_set:
            data[field] = getattr(payload, field)
    if "gender_uuid" in payload.model_fields_set:
        data["gender"] = resolve_gender(payload.gender_uuid) if payload.gender_uuid else None

    updated = user.service.admin.update(request=request, **data)
    response["ETag"] = user_etag(updated)
    return user_detail(updated)


@router.post(
    "/{user_uuid}/verify-email/",
    response={200: EmailVerification, 403: Error, 404: Error},
    summary="Verify a User's email address (no email sent)",
)
def verify_email(request: HttpRequest, user_uuid: UUID):
    """Mark the allauth email record for ``user.email`` as verified + primary."""
    user = resolve_user(user_uuid)
    status = user.service.admin.verify_email()
    return {"uuid": user.uuid, "email": user.email, "status": status}


@router.delete(
    "/{user_uuid}/",
    response={204: None, 403: Error, 404: Error, 409: Error, 422: Error},
    summary="Delete a User by UUID (irreversible; cascades to related records)",
)
def delete_user(request: HttpRequest, user_uuid: UUID):
    """Permanently delete a user; refuses the acting account itself."""
    from django.db.models import ProtectedError

    user = resolve_user(user_uuid)
    try:
        user.service.admin.delete(acting_user=request.auth)
    except ProtectedError as exc:
        raise HttpError(
            409,
            f"Cannot delete: {len(exc.protected_objects)} related object(s) reference this user. "
            "Deactivate the account instead.",
        )
    return 204, None
