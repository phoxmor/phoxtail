# Service Layer

The Service Layer is the standard pattern for organizing business logic in Phoxtail apps. It sits between your views/forms and your models, ensuring that domain rules are centralized, testable, and reusable regardless of how the operation is triggered (admin UI, public view, management command, or API).

---

## Why a Service Layer

Django encourages "fat models, thin views", but as business logic grows, models become tangled with cross-cutting concerns: validation rules that span multiple models, side effects that must happen atomically, and domain logic that doesn't belong in any single model.

The Service Layer solves this by providing a dedicated home for business logic:

- **Models stay thin** -- they define schema, relationships, and database-level constraints. No business logic.
- **Forms stay focused** -- they handle field-level validation and user input cleaning. They call the service for business rules.
- **Views stay thin** -- they handle HTTP concerns (request/response, messages, redirects). They call forms, which call the service.
- **Services own the domain** -- all business rules, cross-model orchestration, and side effects live here.

---

## Architecture: Service, Gateway, Operation

Every service layer follows a three-tier structure:

```
<app>/services/
├── __init__.py               # Re-exports the main service class
├── base.py                   # Core service class (queries, state, helpers)
├── admin/
│   ├── __init__.py
│   ├── gateway.py            # Admin domain gateway
│   └── operations/
│       ├── __init__.py
│       ├── create.py         # One file per operation
│       └── update.py
└── public/
    ├── __init__.py
    ├── gateway.py            # Public domain gateway
    └── operations/
        ├── __init__.py
        └── create.py
```

### Service (`base.py`)

The central class. Wraps an optional model instance and provides:

- **Domain gateways** via `@cached_property` (`.admin`, `.public`)
- **State queries** (e.g., `is_expired()`, `is_cancelled()`)
- **Business helpers** (e.g., credit management, access control)
- **Read-only operations** that don't mutate data

```python
class BookingService:
    def __init__(self, booking=None):
        self.booking = booking

    @cached_property
    def admin(self):
        from .admin.gateway import BookingServiceAdminGateway
        return BookingServiceAdminGateway(self)

    @cached_property
    def public(self):
        from .public.gateway import BookingServicePublicGateway
        return BookingServicePublicGateway(self)

    def is_expired(self):
        return self.booking.end_date < date.today()
```

Gateways are lazy-loaded via `@cached_property` and use deferred imports to avoid circular dependencies.

### Gateway (`gateway.py`)

A gateway groups operations for a specific domain context (admin, public, API). It provides a clean, named interface and delegates to operation classes.

```python
class BookingServiceAdminGateway:
    def __init__(self, service):
        self.service = service

    def create(self, **kwargs):
        from .operations.create import BookingServiceAdminCreate
        return BookingServiceAdminCreate(self.service).execute(**kwargs)

    def cancel(self, **kwargs):
        from .operations.cancel import BookingServiceAdminCancel
        return BookingServiceAdminCancel(self.service).execute(**kwargs)
```

The same operation can have different validation rules depending on the gateway. For example, a public `create` might require the item to be publicly visible, while the admin `create` skips that check.

### Operation (`operations/*.py`)

Each operation is a dedicated class with a fixed four-phase lifecycle:

```
execute() → authorize() → validate() → perform()
```

| Phase | Responsibility |
|---|---|
| `authorize()` | Permission check. Currently a hook for future RBAC. |
| `validate()` | Business rule enforcement. Raises `ValidationError` on failure. |
| `perform()` | DB mutations inside `transaction.atomic()`. Returns the result. |
| `execute()` | Orchestrates the full flow: resolves inputs, then calls authorize, validate, perform in order. |

```python
class BookingServiceAdminCreate:
    def __init__(self, service):
        self.service = service

    def authorize(self):
        pass  # Future RBAC hook

    def validate(self, user, event):
        if event.is_cancelled:
            raise ValidationError("Cannot book a cancelled event.")
        if event.is_full:
            raise ValidationError("Event is full.")

    def perform(self, user, event):
        with transaction.atomic():
            booking = Booking.objects.create(user=user, event=event)
            return booking

    def execute(self, user_id, event_id):
        user = User.objects.get(pk=user_id)
        event = Event.objects.get(pk=event_id)
        self.authorize()
        self.validate(user, event)
        return self.perform(user, event)
```

This separation makes it easy to:

- **Test validation independently** from persistence
- **Call `perform()` directly** when bypassing auth/validation is intentional (e.g., one operation delegating to another)
- **Add authorization** without touching business logic
- **Reason about** what each phase does

---

## Model Integration

Models expose the service via a `service` property:

```python
class Booking(models.Model):
    # ... fields ...

    @property
    def service(self):
        return BookingService(self)
```

This enables ergonomic access throughout the codebase:

```python
# State queries
booking.service.is_expired()

# Operations on existing records
booking.service.admin.cancel(user=request.user)

# Operations that create new records (no instance)
BookingService().admin.create(user_id=user.id, event_id=event.id)
```

Models can also expose thin wrapper properties for frequently used queries:

```python
class Booking(models.Model):
    @property
    def is_expired(self):
        return self.service.is_expired()
```

---

## Form Integration

Forms call the service layer for business validation in `clean()` and for persistence in `save()`:

```python
class BookingCreateForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        if not self.errors:
            # Let the service validate business rules
            try:
                # Trigger validation only (not persistence)
                service = BookingService()
                service.admin._validate_create(**cleaned_data)
            except ValidationError as e:
                # Surface service errors as form errors
                raise
        return cleaned_data

    def save(self, commit=True):
        if not commit:
            return super().save(commit=False)
        # Delegate persistence to the service
        return BookingService().admin.create(**self.cleaned_data)
```

!!! note "Field validation stays in forms"
    The service layer handles **business rules** (cross-model checks, domain logic). **Field-level validation** (required fields, format checks, uniqueness) stays in Django forms and model validators where it belongs. Don't reimplement what Django already does well.

---

## View Integration

Views stay thin -- they handle HTTP and delegate to forms:

```python
def create_view(request):
    form = BookingCreateForm(request.POST or None)
    if form.is_valid():
        try:
            booking = form.save()
            messages.success(request, "Booking created.")
            return redirect(booking)
        except ValidationError as e:
            for msg in e.messages:
                messages.error(request, msg)
    return render(request, "booking/create.html", {"form": form})
```

---

## Validation Patterns

The service layer supports two validation strategies depending on the complexity of your domain.

### Simple: Raise on Failure

For most apps, operations raise `ValidationError` directly when a rule is violated:

```python
def validate(self, user, event):
    if event.is_cancelled:
        raise ValidationError("Cannot book a cancelled event.")
```

This is the default approach. Use it when all validation failures are hard stops.

### Advanced: ValidationResult with Errors and Warnings

For domains where some conflicts are advisory (admin can override), operations return a `ValidationResult` instead:

```python
@dataclass
class ValidationResult:
    errors: list[ValidationMessage]    # Hard blocks -- always prevent the operation
    warnings: list[ValidationMessage]  # Soft conflicts -- admin can override

    def add_error(self, message, field=None): ...
    def add_warning(self, message, field=None): ...
    def raise_if_errors(self): ...     # Raises ValidationError from errors
    def raise_if_warnings(self): ...   # Raises ValidationError from warnings
    def merge(self, other): ...        # Combines two results
```

The gateway controls whether warnings block the operation:

```python
class EventServiceAdminGateway:
    def create(self, force=True, **data):
        """Admin create -- force=True means warnings are non-blocking."""
        op = EventServiceAdminCreate(self.service)
        return op.execute(force=force, **data)
```

And the operation's `execute()` checks accordingly:

```python
def execute(self, force=True, **data):
    self.authorize()
    result = self.validate(**data)
    result.raise_if_errors()          # Always block on hard errors
    if not force:
        result.raise_if_warnings()    # Block on warnings too (for form validation)
    return self.perform(**data)
```

Forms collect warnings for display:

```python
def clean(self):
    cleaned_data = super().clean()
    if not self.errors:
        result = EventService().admin.validate_create(**cleaned_data)
        if result.has_errors:
            for err in result.errors:
                self.add_error(err.field, err.message)
        if result.has_warnings:
            self._warnings = result.warnings  # Store for the view
    return cleaned_data
```

Views surface warnings after a successful save:

```python
if form.is_valid():
    event = form.save()
    messages.success(request, "Event created.")
    for warn in getattr(form, "_warnings", []):
        messages.warning(request, warn.message)
```

!!! tip "When to use ValidationResult"
    Use the simple raise-on-failure pattern unless you have a genuine need for soft warnings. The advanced pattern adds complexity and should only be introduced when admins need the ability to override specific conflict types.

### Delegation: When the Framework Knows Best

Some domains are already well-handled by Django or third-party libraries. In these cases, the service layer's `validate()` can be intentionally empty:

```python
def validate(self):
    pass  # Django's BaseUserCreationForm handles password and email validation
```

The [Users service](service-layer-users.md) takes this approach -- allauth and Django's auth forms are the domain experts for user management, so the service focuses purely on orchestration (atomic creation + allauth `EmailAddress` setup).

The rule: **don't reimplement what a trusted library already does**. Let the service orchestrate, not duplicate.

---

## ID Resolution

Operations receive IDs in `execute()` and resolve them to model instances before calling `validate()` and `perform()`:

```python
def execute(self, user_id, event_id):
    user = User.objects.get(pk=user_id)
    event = Event.objects.get(pk=event_id)
    self.authorize()
    self.validate(user, event)
    return self.perform(user, event)
```

This convention:

- Keeps gateways clean (they pass through primitive values)
- Centralizes entity fetching in one place
- Makes `perform()` reusable when called directly by other operations (they can pass already-resolved instances)

---

## Atomic Transactions

All DB mutations in `perform()` are wrapped in `transaction.atomic()`:

```python
def perform(self, user, event):
    with transaction.atomic():
        booking = Booking.objects.create(user=user, event=event)
        subscription.service.use_credit(event.service)
        return booking
```

This ensures that multi-step operations either fully succeed or fully roll back. No partial updates.

---

## Naming Conventions

### Classes

Operations follow the pattern `{App}Service{Gateway}{Action}`:

```
SubscriptionServiceAdminCreate
ReservationServicePublicConfirmWaitlisted
EventServiceAdminUpdate
UserServiceAdminCreate
```

### Gateway Methods

Method names match the domain action:

```python
gateway.create(...)
gateway.cancel(...)
gateway.confirm(...)
gateway.move(...)
gateway.renew(...)
```

For operations that support separate validation (advanced pattern):

```python
gateway.validate_create(...)   # Returns ValidationResult
gateway.create(...)            # Validates + persists
```

---

## Adding a Service Layer to Your App

### Step 1: Create the structure

```
myapp/services/
├── __init__.py
├── base.py
└── admin/
    ├── __init__.py
    ├── gateway.py
    └── operations/
        ├── __init__.py
        └── create.py
```

### Step 2: Define the base service

```python
# myapp/services/base.py
from functools import cached_property


class MyAppService:
    def __init__(self, instance=None):
        self.instance = instance

    @cached_property
    def admin(self):
        from .admin.gateway import MyAppServiceAdminGateway
        return MyAppServiceAdminGateway(self)

    # Add state queries and helpers here
```

### Step 3: Define the gateway

```python
# myapp/services/admin/gateway.py
class MyAppServiceAdminGateway:
    def __init__(self, service):
        self.service = service

    def create(self, **kwargs):
        from .operations.create import MyAppServiceAdminCreate
        return MyAppServiceAdminCreate(self.service).execute(**kwargs)
```

### Step 4: Define operations

```python
# myapp/services/admin/operations/create.py
from django.core.exceptions import ValidationError
from django.db import transaction


class MyAppServiceAdminCreate:
    def __init__(self, service):
        self.service = service

    def authorize(self):
        pass

    def validate(self, **data):
        # Your business rules here
        pass

    def perform(self, **data):
        with transaction.atomic():
            instance = MyModel.objects.create(**data)
            return instance

    def execute(self, **kwargs):
        self.authorize()
        self.validate(**kwargs)
        return self.perform(**kwargs)
```

### Step 5: Wire up the model

```python
# myapp/models.py
class MyModel(models.Model):
    @property
    def service(self):
        from .services import MyAppService
        return MyAppService(self)
```

### Step 6: Re-export from `__init__.py`

```python
# myapp/services/__init__.py
from .base import MyAppService

__all__ = ["MyAppService"]
```

---

## Reference Implementations

The following apps implement the full service layer pattern and serve as reference:

| App | Complexity | Key Features | Docs |
|---|---|---|---|
| [Users](service-layer-users.md) | Minimal | Empty validation (delegates to Django/allauth), orchestration-only service | Simplest starting point |
| [Subscriptions](service-layer-subscriptions.md) | Moderate | Credit system, dual gateways (admin/public), grace period logic | Good example of domain helpers on the base service |
| [Reservations](service-layer-reservations.md) | High | 9 operations across 2 gateways, status lifecycle, cross-service credit management | Most operations in a single service |
| [Events](service-layer-events.md) | Advanced | ValidationResult pattern, hard errors vs. soft warnings, recurrence generation | Most complex validation strategy |

Start with the **Users** service to understand the minimal structure, then look at **Subscriptions** for a service with real business logic. **Events** demonstrates the advanced ValidationResult pattern.

---

## Design Principles

1. **One home for business logic.** If a rule governs what can or can't happen in your domain, it lives in the service layer -- not in a model method, not in a view, not scattered across forms.

2. **Orchestrate, don't reimplement.** If Django, allauth, or another library already validates something well, let it. The service layer orchestrates the overall flow; it doesn't duplicate framework expertise.

3. **Atomic all the way.** Every `perform()` wraps its mutations in `transaction.atomic()`. If step 3 of 4 fails, steps 1 and 2 roll back.

4. **Separation of read and write.** State queries live on the base service. Mutations live in operations. This makes it clear what's safe to call freely and what has side effects.

5. **Gateways enforce context.** The same underlying logic can have different validation rules for different callers. An admin can override warnings; a public user cannot. Gateways make this explicit.

6. **Operations are self-contained.** Each operation class encapsulates a single action with a predictable lifecycle. Adding a new operation means adding a new file -- no existing code changes.

7. **Lazy loading prevents import cycles.** Gateways use `@cached_property` with deferred imports. Operations import what they need at call time, not at module load time.
