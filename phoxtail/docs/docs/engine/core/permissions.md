# Permissions

This page documents the admin permission system — a two-tier architecture that separates **generic platform infrastructure** from **app-specific permission definitions**. The platform layer lives in `core/permissions/` and provides reusable base classes. Each app cluster (booking, and any future cluster like learning or e-commerce) creates a thin wiring layer that defines its own permission codenames and instantiates the base classes.

---

## How It Works

### Django Foundation

Django provides `auth.Permission` objects tied to `ContentType`. Every model automatically gets `add_`, `change_`, `delete_`, `view_` permissions. Users get permissions directly or through Groups. `user.has_perm("app_label.codename")` is the universal check.

### Wagtail's Permission Policy Layer

Wagtail wraps Django permissions in **permission policies** — objects that provide a consistent API for permission queries:

```
BasePermissionPolicy                    (abstract base)
  +-- BaseDjangoAuthPermissionPolicy    (Django auth helpers)
        +-- ModelPermissionPolicy       (checks model-level Django perms)
              +-- OwnershipPermissionPolicy  (adds ownership rules)
```

Key methods on any policy:

- `user_has_permission(user, action)` — e.g. action = `"add"`, `"change"`, `"delete"`
- `user_has_any_permission(user, actions)` — any of the listed actions
- `user_has_permission_for_instance(user, action, instance)` — instance-level

### The Gap in Base ViewSet

Wagtail's `ModelViewSet` (parent of `SnippetViewSet`) automatically creates a `ModelPermissionPolicy`, enforces permissions in views via `PermissionCheckedMixin`, controls menu visibility, and registers permissions in Wagtail's Groups editor.

The base `ViewSet` — which custom admin viewsets extend — provides **none of that**. No policy, no menu visibility control, no view-level enforcement. Any user with `wagtailadmin.access_admin` can see every menu item and access every view.

This permission system closes that gap.

---

## Architecture

### Two-Tier Split

```
core/permissions/                        # Platform infrastructure (generic)
+-- __init__.py                          # Public API exports
+-- policies.py                          # AppPermissionPolicy (base class)
+-- viewsets.py                          # PermissionedViewSet (base class)
+-- decorators.py                        # permission_required_factory (factory)
+-- mixins.py                            # PermissionMixin (generic CBV mixin)

booking/core/permissions/                # Booking-specific (uses core infrastructure)
+-- __init__.py                          # Public API exports
+-- models.py                            # BookingAdminPermission (codenames)
+-- setup.py                             # Policy singleton + decorator + mixin + viewset
```

### Platform Infrastructure: `core/permissions/`

#### AppPermissionPolicy

Base permission policy class that any app cluster can instantiate with its own permission model. Extends Wagtail's `BasePermissionPolicy`.

```python
from core.permissions import AppPermissionPolicy
from .models import BookingAdminPermission

booking_permission_policy = AppPermissionPolicy(BookingAdminPermission)
```

The policy resolves `user.has_perm("app_label.codename")` automatically using the permission model's `app_label`. Superusers bypass all checks. Inactive users are always denied.

#### PermissionedViewSet

Base ViewSet with permission-controlled menu item visibility. Subclasses set `permission_policy` and `required_permissions`:

```python
class BookingManagementViewSet(BookingViewSet):
    required_permissions = ["access_booking_management"]
```

The `menu_item_class` property dynamically creates a `MenuItem` subclass whose `is_shown()` checks the policy. Users without the required permissions never see the menu item.

#### permission_required_factory

Factory that creates app-specific FBV permission decorators:

```python
booking_permission_required = permission_required_factory(booking_permission_policy)

# Then in views:
@booking_permission_required("access_booking_management", "manage_reservations")
def my_view(request):
    ...
```

All listed permissions are required (AND logic). For HTMX requests, returns `HttpResponse(status=403)` instead of raising `PermissionDenied` — this prevents Wagtail's middleware from converting the denial into a redirect that would break the page layout.

#### PermissionMixin

Generic CBV mixin for permission-protected views. Same HTMX-aware 403 handling as the decorator. When `permission_policy` is `None` (the default), the mixin is a no-op — making it safe to add to base classes without breaking existing subclasses.

```python
class MySearchView(BookingPermissionMixin, SingleSelectSearchView):
    required_permissions = ["access_booking_management", "manage_reservations"]
```

### Base Search View Protection

`SingleSelectSearchView` and `MultiSelectChipsSearchView` in `core/views.py` inherit from `PermissionMixin` at the base class level. This means:

- Existing subclasses that don't set `permission_policy` / `required_permissions` continue to work unchanged
- Subclasses that set the attributes get automatic protection
- No subclass can accidentally forget the mixin — protection is inherited from the base class

---

## App-Specific Layer: Booking

### Permission Model

`BookingAdminPermission` in `booking/core/permissions/models.py` is a ContentType anchor — it's never instantiated. It exists so Django creates `auth_permission` rows during `migrate`. Uses `default_permissions = ()` to suppress the useless auto-generated `add_`/`change_`/`delete_`/`view_` permissions.

13 permission codenames across 5 domains:

| Domain | Codename | Description |
|--------|----------|-------------|
| Booking | `access_booking_management` | Can access booking management |
| Booking | `manage_reservations` | Can create, edit, move reservations |
| Booking | `manage_booking_event_details` | Can edit event details in booking view |
| Scheduling | `access_scheduling_management` | Can access scheduling management |
| Scheduling | `create_scheduled_events` | Can create events in scheduling |
| Scheduling | `edit_scheduled_events` | Can edit events in scheduling |
| Scheduling | `bulk_update_scheduled_events` | Can bulk-update event status |
| Billing | `access_billing_management` | Can access billing management |
| Billing | `manage_billing_subscriptions` | Can create and edit subscriptions |
| Users | `access_users_management` | Can access users management |
| Users | `create_booking_users` | Can create users |
| Users | `edit_booking_users` | Can edit users |
| Settings | `access_booking_settings` | Can access booking settings |

All codenames are prefixed with `booking_core.` when used with `user.has_perm()` (e.g. `booking_core.access_booking_management`), but this is handled automatically by the policy — views and decorators use bare codenames.

### Wiring (`setup.py`)

Creates all booking-specific instances from the generic infrastructure:

```python
from core.permissions import (
    AppPermissionPolicy, PermissionedViewSet, PermissionMixin,
    permission_required_factory,
)
from .models import BookingAdminPermission

booking_permission_policy = AppPermissionPolicy(BookingAdminPermission)
booking_permission_required = permission_required_factory(booking_permission_policy)

class BookingPermissionMixin(PermissionMixin):
    permission_policy = booking_permission_policy

class BookingViewSet(PermissionedViewSet):
    permission_policy = booking_permission_policy
```

### Wagtail Hooks

`register_booking_permissions` in `booking/core/wagtail_hooks.py` makes booking permissions appear in Wagtail's Groups editor:

```python
@hooks.register("register_permissions")
def register_booking_permissions():
    content_type = ContentType.objects.get_for_model(BookingAdminPermission)
    return Permission.objects.filter(content_type=content_type)
```

### Default Groups (Management Command)

```bash
make manage CMD="setup_booking_groups"
```

Creates 4 default groups (idempotent — safe to run multiple times):

| Group | Permissions |
|-------|-------------|
| Booking Admin | All 13 permissions |
| Booking Manager | All except `access_booking_settings` (12) |
| Booking Staff | `access_booking_management`, `manage_reservations`, `access_scheduling_management`, `edit_scheduled_events` (4) |
| Booking Viewer | All `access_*` permissions (5) |

---

## Permission Mapping

### ViewSets (Menu Visibility)

| ViewSet | `required_permissions` |
|---------|----------------------|
| `BookingManagementViewSet` | `["access_booking_management"]` |
| `SchedulingManagementViewSet` | `["access_scheduling_management"]` |
| `BillingManagementViewSet` | `["access_billing_management"]` |
| `UsersManagementViewSet` | `["access_users_management"]` |
| `BookingSettingsViewSet` | `["access_booking_settings"]` |

### FBV Protection (View-Level)

Every FBV uses `@booking_permission_required(...)`. The full mapping per module:

#### `booking/events/admin/booking/views.py`

| View | Permissions |
|------|------------|
| `admin_event_list_view` | `access_booking_management` |
| `admin_event_detail_form_view` | `access_booking_management` |
| `admin_booking_event_update_form_view` | `access_booking_management`, `manage_booking_event_details` |
| `admin_event_reservation_update_form_view` | `access_booking_management`, `manage_reservations` |
| `admin_event_reservation_move_form_view` | `access_booking_management`, `manage_reservations` |
| `admin_event_reservation_move_view` | `access_booking_management`, `manage_reservations` |
| `admin_event_reservation_create_form_view` | `access_booking_management`, `manage_reservations` |
| `admin_event_reservation_create_view` | `access_booking_management`, `manage_reservations` |
| `admin_booking_filters_form_view` | `access_booking_management` |
| `admin_booking_filters_view` | `access_booking_management` |

#### `booking/events/admin/scheduling/views.py`

| View | Permissions |
|------|------------|
| `admin_event_schedule_view` | `access_scheduling_management` |
| `admin_schedule_event_create_form_view` | `access_scheduling_management`, `create_scheduled_events` |
| `admin_schedule_event_update_form_view` | `access_scheduling_management`, `edit_scheduled_events` |
| `admin_schedule_template_event_update_form_view` | `access_scheduling_management`, `edit_scheduled_events` |
| `admin_schedule_event_capacity_form_field_view` | `access_scheduling_management` |
| `admin_schedule_event_frequency_form_field_view` | `access_scheduling_management` |
| `admin_schedule_event_weekdays_form_field_view` | `access_scheduling_management` |
| `admin_schedule_filters_form_view` | `access_scheduling_management` |
| `admin_schedule_filters_view` | `access_scheduling_management` |
| `admin_schedule_actions_form_view` | `access_scheduling_management` |
| `admin_schedule_actions_view` | `access_scheduling_management`, `bulk_update_scheduled_events` |
| `admin_schedule_bulk_update_status_form_view` | `access_scheduling_management`, `bulk_update_scheduled_events` |

#### `booking/subscriptions/views/admin/views.py`

| View | Permissions |
|------|------------|
| `admin_billing_index_view` | `access_billing_management` |
| `admin_subscription_create_form_view` | `access_billing_management`, `manage_billing_subscriptions` |
| `admin_subscription_create_view` | `access_billing_management`, `manage_billing_subscriptions` |
| `admin_subscription_detail_view` | `access_billing_management` |
| `admin_subscription_update_form_view` | `access_billing_management`, `manage_billing_subscriptions` |
| `admin_billing_filters_form_view` | `access_billing_management` |
| `admin_billing_filters_view` | `access_billing_management` |
| `admin_credit_balance_detail_view` | `access_billing_management` |

#### `booking/core/admin/users/views.py`

| View | Permissions |
|------|------------|
| `admin_users_index_view` | `access_users_management` |
| `admin_user_detail_view` | `access_users_management` |
| `admin_user_create_form_view` | `access_users_management`, `create_booking_users` |
| `admin_user_create_view` | `access_users_management`, `create_booking_users` |
| `admin_user_update_form_view` | `access_users_management`, `edit_booking_users` |
| `admin_user_update_view` | `access_users_management`, `edit_booking_users` |
| `admin_users_filters_form_view` | `access_users_management` |

#### `booking/core/admin/settings/views.py`

| View | Permissions |
|------|------------|
| `admin_settings_index_view` | `access_booking_settings` |

### CBV Protection

CBV subclasses set `permission_policy` and `required_permissions` as class attributes:

| CBV | Permissions |
|-----|------------|
| `ReservationMoveSearchTargetEventView` | `access_booking_management`, `manage_reservations` |
| `_ReservationCreateSingleSelectBase` (+ subclasses) | `access_booking_management`, `manage_reservations` |
| `_SubscriptionCreateSingleSelectBase` (+ subclasses) | `access_billing_management`, `manage_billing_subscriptions` |

---

## Permission Granularity

### Access vs Action Permissions

Every domain has two tiers:

1. **Access permissions** (`access_*`) — gate the entire section. Without this, the menu item is hidden and all views return 403. This is the coarse filter.

2. **Action permissions** (`manage_*`, `create_*`, `edit_*`, `bulk_*`) — gate specific operations within a section. A user with `access_booking_management` but without `manage_reservations` can view the booking list and event details but cannot create/edit/move reservations.

### Template-Level Checks

For hiding UI elements based on permissions, pass a context flag from the view:

```python
context["can_manage_reservations"] = booking_permission_policy.user_has_permission(
    request.user, "manage_reservations"
)
```

```html
{% if can_manage_reservations %}
    <button>Create Reservation</button>
{% endif %}
```

Both layers are necessary — the template check is UX (don't show what they can't do), the view decorator is security (enforce even if someone crafts a direct request).

---

## Adding New Permissions

1. Add codename + description to `BookingAdminPermission.Meta.permissions`
2. `makemigrations` + `migrate`
3. Use `@booking_permission_required("new_codename")` on the view
4. Update group assignments (management command or Wagtail Groups UI)

---

## Creating a New App Cluster

When building a new app cluster (e.g. learning platform), the entire permissions setup is:

```
learning/core/permissions/
+-- __init__.py
+-- models.py      # LearningAdminPermission with its own codenames
+-- setup.py       # ~10 lines: policy, decorator, mixin, viewset
```

```python
# learning/core/permissions/models.py
from django.db import models

class LearningAdminPermission(models.Model):
    class Meta:
        default_permissions = ()
        permissions = [
            ("access_course_management", "Can access course management"),
            ("create_courses", "Can create courses"),
            # ...
        ]
```

```python
# learning/core/permissions/setup.py
from core.permissions import (
    AppPermissionPolicy, PermissionedViewSet, PermissionMixin,
    permission_required_factory,
)
from .models import LearningAdminPermission

learning_permission_policy = AppPermissionPolicy(LearningAdminPermission)
learning_permission_required = permission_required_factory(learning_permission_policy)

class LearningPermissionMixin(PermissionMixin):
    permission_policy = learning_permission_policy

class LearningViewSet(PermissionedViewSet):
    permission_policy = learning_permission_policy
```

Zero duplication of core logic. Each cluster defines only what's unique to it.

---

## Service Layer Integration

The permission system protects **HTTP entry points** (view-level access control). The service layer has a separate, complementary authorization layer: the `authorize()` hook in the operation lifecycle.

```
HTTP Request
  |
  +-- View Layer (decorator / mixin) -- ENDPOINT-LEVEL
  |     "Does this user have access_booking_management + manage_reservations?"
  |         NO -> 403 PermissionDenied
  |         YES |
  |
  +-- Service Layer -- authorize() -- RESOURCE-LEVEL
  |     "Is this staff member authorized for this event's location?"
  |         NO -> PermissionDenied
  |         YES |
  |
  +-- Service Layer -- validate() -- BUSINESS RULES
        "Is this reservation valid? Event not full? No conflicts?"
            NO -> ValidationError
            YES -> perform() executes the operation
```

View permissions gate entire sections and endpoints. Service authorization (future) gates what you can do to which specific resources within those sections. Neither can replace the other.

---

## External Libraries

No additional libraries required. The architecture uses:

- **Django's built-in permission system** — `auth.Permission`, `auth.Group`, `user.has_perm()`
- **Wagtail's permission policy pattern** — `BasePermissionPolicy` and the `register_permissions` hook

Libraries like `django-rules` or `django-guardian` were evaluated but are unnecessary — the system's permission needs are well served by Django's standard model-level permissions combined with Wagtail's policy abstraction.
