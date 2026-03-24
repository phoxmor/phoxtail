# Reservation Service Layer Architecture

This document describes the design and responsibilities of the service layer in `booking/reservations/services/`.

---

## Overview

The service layer encapsulates all business logic related to reservations, keeping models thin and decoupling domain rules from views and forms. It is structured as three nested tiers:

```
services/
├── __init__.py               # Re-exports ReservationService, ReservationValidator
├── base.py                   # Core service class + shared validator
├── admin/
│   ├── gateway.py            # Admin domain gateway
│   └── operations/
│       ├── cancel.py         # Cancellation (delete or mark cancelled)
│       ├── complete.py       # Mark attendance (confirmed → completed)
│       ├── confirm.py        # Confirm waitlisted or cancelled reservations
│       ├── create.py         # Admin-initiated reservation creation
│       ├── move.py           # Move reservation to a different event
│       └── revert_waitlisted.py  # Revert confirmed/completed → waitlisted
└── public/
    ├── gateway.py            # Public domain gateway
    └── operations/
        ├── confirm_waitlisted.py  # User confirms a waitlisted reservation
        ├── create.py              # User creates a confirmed reservation
        └── create_waitlisted.py   # User joins waitlist for a full event
```

---

## Design Patterns

### Service Object
`ReservationService` is a plain Python class that wraps an optional `Reservation` instance. All business logic lives here rather than on the model itself. The model exposes a `service` property as the entry point:

```python
reservation.service  # → ReservationService(self)
```

### Gateway Pattern
`ReservationService` exposes two `@cached_property` attributes — `.admin` and `.public` — that return domain-specific gateway objects. Each gateway provides a clean, named interface for operations in that domain context.

```python
# Admin context (requires existing reservation)
ReservationService(reservation).admin.cancel(user)
ReservationService(reservation).admin.move(target_event_id)
ReservationService(reservation).admin.confirm(subscription_id)
ReservationService(reservation).admin.complete()
ReservationService(reservation).admin.revert_to_waitlisted()

# Admin context (no existing reservation)
ReservationService().admin.create(user_id, event_id, subscription_id, status)

# Public context
ReservationService().public.create(user, event_id, subscription_id)
ReservationService().public.create_waitlisted(user, event_id, subscription_id)
ReservationService().public.confirm_waitlisted(user, reservation_id, subscription_id)
```

Gateways are lazy-loaded (via `cached_property`) to avoid circular imports.

### Operation Pattern
Each operation is a dedicated class with a fixed lifecycle:

```
execute() → authorize() → validate() → perform()
```

| Method | Responsibility |
|---|---|
| `authorize()` | Permission hook. Currently a no-op; reserved for future RBAC checks. |
| `validate(...)` | Enforces business rules. Raises `django.core.exceptions.ValidationError` on failure. |
| `perform(...)` | Executes DB mutations inside `transaction.atomic()`. |
| `execute(...)` | Orchestrates the flow: resolves entities from IDs, then calls the three above in order. |

---

## Layer Responsibilities

### `ReservationService` (`base.py`)

Wraps an optional `Reservation` instance. Provides state queries and domain gateways.

**Domain gateways** (lazy `@cached_property`):
- `.admin` → `ReservationServiceAdminGateway`
- `.public` → `ReservationServicePublicGateway`

**State queries:**
- `is_cancelled()` — True if status is `CANCELLED`.
- `get_is_within_allowed_cancellation_period()` — True if cancellation would result in deletion + credit restoration (before the lockout window).

**User info delegation** (used by model properties for Wagtail search indexing):
- `get_user_username()`, `get_user_first_name()`, `get_user_last_name()`, `get_user_email()`, `get_user_full_name()`
- `get_event_service_name()`, `get_event_title()`

### `ReservationValidator` (`base.py`)

Shared validation helpers used across multiple operations:

- `validate_grace_period_access(subscription)` — Raises `ValidationError` if the subscription has exhausted its unpaid reservation limit.

---

### Admin Gateway (`admin/gateway.py`)

`ReservationServiceAdminGateway` wraps the parent `ReservationService` and exposes admin-context operations:

- `create(user_id, event_id, subscription_id, status)` → delegates to `ReservationServiceAdminCreate`
- `cancel(user)` → delegates to `ReservationServiceAdminCancel`
- `move(target_event_id, ...)` → delegates to `ReservationServiceAdminMove`
- `confirm(subscription_id)` → delegates to `ReservationServiceAdminConfirm`
- `complete()` → delegates to `ReservationServiceAdminComplete`
- `revert_to_waitlisted()` → delegates to `ReservationServiceAdminRevertWaitlisted`

### Public Gateway (`public/gateway.py`)

`ReservationServicePublicGateway` exposes user-facing operations with user-friendly error messages:

- `create(user, event_id, subscription_id)` → delegates to `ReservationServicePublicCreate`
- `create_waitlisted(user, event_id, subscription_id)` → delegates to `ReservationServicePublicCreateWaitlisted`
- `confirm_waitlisted(user, reservation_id, subscription_id)` → delegates to `ReservationServicePublicConfirmWaitlisted`

---

## Operations

### Admin: Create

Creates a reservation for a user on behalf of an admin.

**`validate()` rules:**
1. Event must not be in the past.
2. User must have access to the event (group check).
3. No duplicate reservation (any status blocks creation).
4. Event must not be cancelled.
5. Event must not be full (for CONFIRMED/COMPLETED status).
6. No overlapping reservations at the same time.
7. Event must fall within subscription period.
8. Subscription must provide access to the event's service.
9. Grace period limit not exceeded.

**`perform()` steps:**
1. Create the `Reservation` with specified status.
2. If status is not WAITLISTED, deduct one subscription credit.

### Admin: Cancel

Cancels a reservation. Behavior depends on timing relative to the cancellation lockout window.

**Within cancellation period** (before lockout):
1. Restore subscription credit (if not waitlisted and subscription exists).
2. Delete the reservation entirely.

**Outside cancellation period** (after lockout):
1. Mark reservation status as `CANCELLED`.
2. No credit restoration.

### Admin: Move

Moves a reservation from one event to another.

**`validate()` rules:**
1. Cannot move to the same event.
2. Target event must not be in the past.
3. Target event must not be cancelled.
4. User must have access to the target event.
5. No duplicate reservation at the target event.
6. Target event must not be full (for confirmed/completed reservations).
7. No overlapping reservations at the target time.
8. Subscription must provide access to the target event's service.

**`perform()` steps:**
1. Update `reservation.event` to the target event.
2. If the original and target events have different services, swap credits (restore original, use target).

### Admin: Confirm

Confirms a waitlisted or cancelled reservation.

**Waitlisted → Confirmed:**
1. Requires a subscription ID.
2. Validates event capacity, timing, overlaps, and subscription access.
3. Attaches the subscription and changes status to CONFIRMED.
4. Deducts one subscription credit.

**Cancelled → Confirmed:**
1. Uses the existing subscription (no new subscription needed).
2. Validates event capacity, timing, and overlaps.
3. Changes status to CONFIRMED without consuming additional credit (credit was already used and not restored during cancellation).

### Admin: Complete

Marks attendance on a confirmed reservation.

**`validate()` rules:**
1. Status must be CONFIRMED.
2. Event must not be cancelled.

**`perform()`:** Sets status to COMPLETED.

### Admin: Revert to Waitlisted

Reverts a confirmed or completed reservation back to waitlisted status.

**`validate()` rules:**
1. Status must be CONFIRMED or COMPLETED.

**`perform()` steps:**
1. Restore one subscription credit (if subscription exists).
2. Set status to WAITLISTED.

### Public: Create

User creates a confirmed reservation for an event.

**`validate()` rules:**
1. Event must not be in the past.
2. User must have access to the event.
3. No duplicate confirmed/completed reservation for the same event.
4. No overlapping reservations at the same time.
5. Event must not be cancelled or unpublished.
6. Event must not be full.
7. Event must fall within subscription period.
8. Subscription must provide access to the event's service.
9. Grace period limit not exceeded.

**`perform()` steps:**
1. Create the `Reservation` with CONFIRMED status.
2. Deduct one subscription credit.

### Public: Create Waitlisted

User joins the waitlist for a full event.

**`validate()` rules:**
1. Event must not be in the past.
2. User must have access to the event.
3. No existing reservation of any status (confirmed, waitlisted, cancelled, completed).
4. Event must not be cancelled or unpublished.
5. Event must be full (otherwise user should make a normal booking).
6. No overlapping confirmed/completed reservations.
7. Subscription must provide access to the event's service.
8. Grace period limit not exceeded.

**`perform()` steps:**
1. Create the `Reservation` with WAITLISTED status.
2. No credit deduction (credits are consumed when the waitlisted reservation is confirmed).

### Public: Confirm Waitlisted

User confirms a waitlisted reservation when a spot becomes available.

**`validate()` rules:**
1. Event must not be in the past.
2. User must have access to the event.
3. Event must not be cancelled or unpublished.
4. Event must not be full (a spot must have opened up).
5. No overlapping confirmed/completed reservations.
6. Subscription must provide access to the event's service.
7. Grace period limit not exceeded.

**`perform()` steps:**
1. Set status to CONFIRMED and attach the subscription.
2. Deduct one subscription credit.

---

## Cancellation Period

The cancellation period is determined by `Service.cancellation_lockout_hours`. A reservation can be cancelled "early" (with credit restoration and deletion) if:

```
now < event.start_datetime - timedelta(hours=cancellation_lockout_hours)
```

Otherwise, the reservation is marked as CANCELLED without credit restoration.

---

## Model Integration

`Reservation` delegates to the service layer via its `service` property. Several model properties are thin wrappers:

```python
reservation.is_cancelled                       # → service.is_cancelled()
reservation.is_within_allowed_cancellation_period  # → service.get_is_within_allowed_cancellation_period()
reservation.user_username                      # → service.get_user_username()
reservation.user_email                         # → service.get_user_email()
reservation.user_full_name                     # → service.get_user_full_name()
reservation.event_service_name                 # → service.get_event_service_name()
```

---

## Adding New Operations

To add a new operation (e.g., `reschedule`) to a domain:

1. Create `services/<domain>/operations/reschedule.py` with a class that follows the `authorize / validate / perform / execute` pattern.
2. Export it from `services/<domain>/operations/__init__.py`.
3. Add a `reschedule()` method to the corresponding gateway that instantiates the class and calls `.execute()`.

To add a new domain (e.g., `api`):

1. Create `services/api/gateway.py` and `services/api/operations/`.
2. Add a `@cached_property` on `ReservationService` that returns the new gateway.
