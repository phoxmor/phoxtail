# User Service Layer Architecture

This document describes the design and responsibilities of the service layer in `users/services/`.

---

## Overview

The service layer orchestrates user management operations, keeping views thin and ensuring allauth integration is handled consistently. It follows the same `Service → Gateway → Operation` pattern as the subscription, event, and reservation service layers.

```
services/
├── __init__.py                          # Re-exports UserService
├── base.py                              # Core service class
└── admin/
    ├── __init__.py                      # Re-exports gateway + operations
    ├── gateway.py                       # Admin domain gateway
    └── operations/
        ├── create.py                    # Admin user creation
        └── update.py                    # Admin user update
```

**Important:** The service layer lives in `users/` and handles only core User + allauth concerns. It has **no dependency on the booking cluster**. Booking-specific concerns (e.g., `BookingGroup` membership) are handled in `booking/core/admin/users/views.py`, which calls the service for user operations and then manages group assignment separately.

---

## Design Philosophy: Delegation, Not Reimplementation

The subscription, event, and reservation service layers have heavy custom `validate()` methods because they encode domain-specific business rules no library handles. User management is fundamentally different — **Django and allauth are the domain experts**.

The User service layer therefore:

- **Does NOT** reimplement email uniqueness — `ModelForm.validate_unique()` handles this
- **Does NOT** reimplement password validation — `BaseUserCreationForm` provides password matching and strength checks via Django's `validate_password` and allauth's `adapter.clean_password()`
- **Does NOT** reimplement username generation — allauth's `adapter.populate_username()` handles this
- **Does** orchestrate: atomic user creation + allauth `EmailAddress` setup + adapter calls
- **Does** handle cross-cutting concerns forms can't: email change syncing with allauth records

This means `validate()` methods are intentionally empty — they exist as hooks for future business rules (e.g., "max users per organization") but currently all validation lives in the forms where Django and allauth handle it best.

---

## Design Patterns

### Service Object

`UserService` is a plain Python class that wraps an optional `User` instance. The model exposes a `service` property as the entry point:

```python
user.service          # → UserService(user)
UserService()         # → No user (for creation)
```

### Gateway Pattern

`UserService` exposes an `.admin` `@cached_property` that returns `UserServiceAdminGateway`. The gateway provides a clean, named interface for admin operations.

```python
# Create (no existing user)
UserService().admin.create(email, first_name, last_name, password, request)

# Update (existing user)
user.service.admin.update(request=request, **form.cleaned_data)
```

### Operation Pattern

Each operation follows the same fixed lifecycle as other service layers:

```
execute() → authorize() → validate() → perform()
```

| Method | Responsibility |
|---|---|
| `authorize()` | Permission hook. Currently a no-op; reserved for future RBAC checks. |
| `validate(...)` | Business rule hook. Currently empty — Django/allauth handle all validation in the form layer. |
| `perform(...)` | Executes DB mutations inside `transaction.atomic()`. |
| `execute(...)` | Orchestrates the flow: calls authorize, validate, and perform in order. |

---

## Layer Responsibilities

### `UserService` (`base.py`)

Wraps an optional `User` instance. Provides the admin gateway.

**Domain gateway** (lazy `@cached_property`):
- `.admin` → `UserServiceAdminGateway`

### Admin Gateway (`admin/gateway.py`)

`UserServiceAdminGateway` wraps the parent `UserService` and exposes admin-context operations:

- `create(email, first_name, last_name, password, request)` → delegates to `UserServiceAdminCreate.execute()`
- `update(request, **data)` → delegates to `UserServiceAdminUpdate.execute()`

---

### Operation: Create (`admin/operations/create.py`)

**`validate()`** — No-op. All field validation is handled by `UserCreateForm` (which inherits from `BaseUserCreationForm`): password matching, password strength, and email uniqueness via `validate_unique()`.

**`perform()` steps:**
1. Instantiate `User` with email, first_name, last_name.
2. Call `allauth.account.adapter.get_adapter().populate_username(request, user)` — generates username via allauth's configured strategy instead of hardcoded `email[:150]`.
3. Set the password and save the user.
4. Call `allauth.account.utils.setup_user_email(request, user, [])` — creates the allauth `EmailAddress` record so login and password-reset flows work correctly.

All DB writes run inside `transaction.atomic()`.

**Bug fixed:** Previously, admin-created users had no allauth `EmailAddress` record, breaking login and password-reset flows. The service now calls `setup_user_email()` to create this record.

---

### Operation: Update (`admin/operations/update.py`)

**`validate()`** — No-op. `UserUpdateForm` (ModelForm) handles email uniqueness via `validate_unique()`.

**`perform()` steps:**
1. Apply field changes to the user instance.
2. If email changed:
   - Re-populate username via allauth adapter.
   - Update the allauth `EmailAddress` record to match the new email.
3. Save the user.

All DB writes run inside `transaction.atomic()`.

---

## Admin UI Location

The admin management UI (forms, views, viewsets, templates) lives in `booking/core/admin/users/`, **not** in `users/`. This is because:

- The admin UI depends on `BookingGroup` (a `booking.core` model) for group assignment
- The `booking` cluster is feature-flagged (`FEATURE_ACTIVATE_BOOKING`) and may not exist in every deployment
- The `users` app must remain independent of the booking cluster

The views in `booking/core/admin/users/views.py` call the user service for create/update operations and handle `BookingGroup` membership separately.

---

## Form Integration

### `UserCreateForm` (`booking/core/admin/users/forms.py`)

Inherits from `django.contrib.auth.forms.BaseUserCreationForm` (which extends `ModelForm`). This provides for free:

- Password matching via `SetPasswordMixin.validate_passwords()`
- Password strength validation via `validate_password_for_user()`
- Email uniqueness via ModelForm's `validate_unique()`
- Proper password field widgets and help text

Includes a `booking_groups` checkbox field via `BookingGroupsMixin`.

### `UserUpdateForm` (`booking/core/admin/users/forms.py`)

Standard `ModelForm`. `validate_unique()` handles email conflicts. Includes `booking_groups` pre-populated with the user's current group membership.

---

## Model Integration

`User` delegates to the service layer via its `service` property:

```python
user.service.admin.create(...)   # Admin user creation
user.service.admin.update(...)   # Admin user update
```

---

## Adding New Operations

To add a new operation (e.g., `deactivate`) to the admin domain:

1. Create `services/admin/operations/deactivate.py` with a class that follows the `authorize / validate / perform / execute` pattern.
2. Export it from `services/admin/operations/__init__.py`.
3. Add a `deactivate()` method to `UserServiceAdminGateway` that instantiates the class and calls `.execute()`.

To add a new domain (e.g., `public`):

1. Create `services/public/gateway.py` and `services/public/operations/`.
2. Add a `@cached_property` on `UserService` that returns the new gateway.
