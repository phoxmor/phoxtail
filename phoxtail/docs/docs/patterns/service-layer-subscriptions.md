# Subscription Service Layer Architecture

This document describes the design and responsibilities of the service layer in `booking/subscriptions/services/`.

---

## Overview

The service layer encapsulates all business logic related to subscriptions, keeping models thin and decoupling domain rules from views and forms. It is structured as three nested tiers:

```
services/
├── __init__.py               # Re-exports SubscriptionService, SubscriptionTypeService
├── base.py                   # Core service classes
├── admin/
│   ├── gateway.py            # Admin domain gateway
│   └── operations/
│       ├── create.py         # Admin subscription creation
│       └── renew.py          # Admin subscription renewal
└── public/
    ├── gateway.py            # Public domain gateway
    └── operations/
        ├── create.py         # Public subscription creation
        └── renew.py          # Public subscription renewal
```

---

## Design Patterns

### Service Object
`SubscriptionService` and `SubscriptionTypeService` are plain Python classes that wrap a model instance. All business logic lives here rather than on the model itself. Models expose a `service` property as the entry point:

```python
subscription.service        # → SubscriptionService(self)
subscription_type.service   # → SubscriptionTypeService(self)
```

### Gateway Pattern
`SubscriptionService` exposes two `@cached_property` attributes — `.admin` and `.public` — that return domain-specific gateway objects. Each gateway provides a clean, named interface for operations in that domain context.

```python
# Admin context
SubscriptionService().admin.create(user, subscription_type)
SubscriptionService(subscription).admin.renew()

# Public context
SubscriptionService().public.create(user, subscription_type)
SubscriptionService(subscription).public.renew()
```

Gateways are lazy-loaded (via `cached_property`) to avoid circular imports.

### Operation Pattern
Each operation (create, renew) is a dedicated class with a fixed lifecycle:

```
execute() → authorize() → validate() → perform()
```

| Method | Responsibility |
|---|---|
| `authorize(user)` | Permission hook. Currently a no-op; reserved for future RBAC checks. |
| `validate(...)` | Enforces business rules. Raises `django.core.exceptions.ValidationError` on failure. |
| `perform(...)` | Executes DB mutations inside `transaction.atomic()`. |
| `execute(...)` | Orchestrates the flow: resolves defaults, then calls the three above in order. |

This separation makes it easy to test validation and persistence independently, and to call `perform()` directly when bypassing authorization/validation is intentional (e.g., from the renew operation delegating to create).

---

## Layer Responsibilities

### `SubscriptionTypeService` (`base.py`)

Wraps a `SubscriptionType` instance. Provides state queries on the type itself:

- `is_active()` — Whether the subscription type is currently open for purchase.
- `is_public()` — Whether the subscription type is publicly visible.

### `SubscriptionService` (`base.py`)

Wraps an optional `Subscription` instance. This is the core of the service layer and owns all generic business logic.

**Domain gateways** (lazy `@cached_property`):
- `.admin` → `SubscriptionServiceAdminGateway`
- `.public` → `SubscriptionServicePublicGateway`

**Credit management:**
- `get_credits_for_service(service)` — Returns remaining credits for a service (`float('inf')` for unlimited, `0` for no access).
- `use_credit(service)` — Atomically deducts one credit. Returns `True` on success.
- `restore_credit(service)` — Atomically restores one credit on reservation cancellation. Returns `True` on success.
- `create_initial_credit_balances(subscription)` — Seeds `credits` and `SubscriptionCreditBalance` rows from the subscription type on creation.

**Access control:**
- `can_access_service(service, skip_credit_validation, skip_active_check)` — Full access check: status, expiry, and credit availability.
- `can_renew()` — True when subscription is ACTIVE, paid, the type is still active, and the subscription is either expired or credits depleted.

**State queries:**
- `is_expired()` — True if `end_date` has passed. Non-expiring subscriptions always return False.
- `has_remaining_credits()` — True if either shared or any per-service credits remain.
- `has_remaining_shared_credits()` — True if shared pool is unlimited or `> 0`.
- `has_remaining_per_service_credits(service=None)` — True if the given service (or any service) has credits remaining.
- `get_renewal_end_date()` — Calculates the `end_date` for a fresh renewal based on the type's duration and location timezone.
- `is_event_within_subscription_period(event_start_datetime)` — True if the event date falls between `start_date` and `end_date`.

**Grace period:**
- `can_access_grace_period_reservations()` — True if subscription is paid or the unpaid reservation count is below the limit.
- `get_remaining_grace_period_reservations()` — Number of free reservations remaining before payment is required.
- `get_unpaid_reservation_count()` — Counts confirmed/completed/cancelled reservations on an unpaid subscription.

**User info delegation** (used by model `@cached_property` fields for Wagtail search indexing):
- `get_user_first_name()`, `get_user_last_name()`, `get_user_username()`, `get_user_email()`
- `get_subscription_type_name()`

---

### Admin Gateway (`admin/gateway.py`)

`SubscriptionServiceAdminGateway` wraps the parent `SubscriptionService` and exposes admin-context operations:

- `create(user, subscription_type, start_date=None)` → delegates to `SubscriptionServiceAdminCreate.execute()`
- `renew(start_date=None)` → delegates to `SubscriptionServiceAdminRenew.execute()`

### Public Gateway (`public/gateway.py`)

`SubscriptionServicePublicGateway` mirrors the admin gateway with public-context operations and user-facing error messages:

- `create(user, subscription_type, start_date=None)` → delegates to `SubscriptionServicePublicCreate.execute()`
- `renew(start_date=None)` → delegates to `SubscriptionServicePublicRenew.execute()`

---

### Operation: Create (Admin & Public)

Both follow the same structure. The public version adds one extra validation step.

**`validate()` rules:**

| # | Admin | Public |
|---|---|---|
| 1 | Subscription type must be active | Subscription type must be active |
| 2 | — | Subscription type must be public |
| 3 | User must have no unpaid subscriptions | User must have no unpaid subscriptions |
| 4 | User must have no active duplicate of the same type | User must have no active duplicate of the same type |

**`perform()` steps:**
1. Instantiate `Subscription` with `user`, `subscription_type`, and `start_date`.
2. If the type has a `duration`, compute `end_date = start_date + timedelta(days=duration)`.
3. Save the subscription.
4. Call `self.service.create_initial_credit_balances(subscription)` to seed the credit pool.

All DB writes run inside `transaction.atomic()`.

---

### Operation: Renew (Admin & Public)

Both follow the same structure. The public version adds a public-visibility validation step.

**`validate()` rules:**

| # | Admin | Public |
|---|---|---|
| 1 | Subscription must not be None | Subscription must not be None |
| 2 | Subscription type must be active | Subscription type must be active |
| 3 | — | Subscription type must be public |
| 4 | Status must be ACTIVE | Status must be ACTIVE |
| 5 | Must be expired OR credits depleted (not both active + credits) | Must be expired OR credits depleted |
| 6 | Subscription must be paid | Subscription must be paid |

**`perform()` steps:**
1. Archive the current subscription (`status = ARCHIVED`).
2. Delegate to `Create.perform()` (bypassing authorize/validate) to create a fresh subscription with reset credits and a new date window.

All DB writes (archive + create) run inside a single `transaction.atomic()`.

---

## Credit System

The credit system supports two operating modes determined by whether `SubscriptionCreditBalance` records exist for a subscription.

### Free Mode (no per-service balances)

When no `SubscriptionCreditBalance` rows exist, the subscription has a single shared credits pool (`Subscription.credits`) that grants access to any service:

- `credits = None` → unlimited access to all services
- `credits > 0` → limited access; each usage decrements the pool
- `credits = 0` → no access

### Whitelist Mode (per-service balances present)

When `SubscriptionCreditBalance` rows exist, they act as a service whitelist. Only listed services can be accessed. Each balance has its own `credits` field, with the shared pool acting as a fallback.

**Credit consumption (`use_credit`):**
1. Try service-specific balance first.
2. If specific balance is exhausted, fall back to shared credits (only if limited; unlimited shared credits are never used as a fallback in whitelist mode).
3. If neither has credits, return `False`.

**Credit restoration (`restore_credit`):**
1. Try to restore shared credits first (if below the allocated max from the subscription type).
2. If shared credits are full or unlimited, restore service-specific balance instead.

### Initialization (`create_initial_credit_balances`)

Called once during subscription creation:

1. Copies `SubscriptionType.credits` → `Subscription.credits` (the shared pool).
2. Copies `unpaid_reservation_limit` from the type if not already set.
3. Creates one `SubscriptionCreditBalance` row per `SubscriptionTypeCreditAllocation`, seeding each balance with the allocation's credit value.

A `credits = None` on either the shared pool or a per-service balance always means **unlimited**.

---

## Model Integration

`Subscription` and `SubscriptionType` delegate to the service layer via their `service` property. Several model methods are thin wrappers:

```python
# On Subscription
subscription.is_expired                     # → service.is_expired()
subscription.can_renew                      # → service.can_renew()
subscription.renewal_end_date               # → service.get_renewal_end_date()
subscription.remaining_grace_period_reservations  # → service.get_remaining_grace_period_reservations()
subscription.use_credit(service)            # → service.use_credit(service)
subscription.can_access_service(service)    # → service.can_access_service(service)

# On SubscriptionType
subscription_type.service.is_active()
subscription_type.service.is_public()
```

Wagtail search index fields (`user_first_name`, `user_email`, `subscription_type_name`, etc.) are also computed through the service to keep the model clean.

---

## Adding New Operations

To add a new operation (e.g., `cancel`) to a domain:

1. Create `services/<domain>/operations/cancel.py` with a class that follows the `authorize / validate / perform / execute` pattern.
2. Export it from `services/<domain>/operations/__init__.py`.
3. Add a `cancel()` method to the corresponding gateway that instantiates the class and calls `.execute()`.

To add a new domain (e.g., `api`):

1. Create `services/api/gateway.py` and `services/api/operations/`.
2. Add a `@cached_property` on `SubscriptionService` that returns the new gateway.
