# Authorization Layers

Phoxtail uses three distinct authorization layers. Each answers a different question, at a different point in the request lifecycle. They compose — they don't collapse into one check.

---

## The three questions

| Layer | Question | Where it runs |
|---|---|---|
| **1. Permission Policy** | Can this *user* reach this *endpoint*? | View decorator / template |
| **2. PAT Scopes** | Was this *token* issued with authority to do this? | API auth middleware |
| **3. Service `authorize()`** | Can this user act on *this specific instance*? | Service operation |

Each layer is independently useful. Removing any one creates a real gap:
- Without Layer 1, any authenticated user can reach any endpoint.
- Without Layer 2, a machine token issued for read-only sync could make write calls.
- Without Layer 3, a user with `manage_reservations` could move a reservation to an event at a location they're not assigned to.

---

## Layer 1: Permission Policy (endpoint-level)

This is the door. It runs first, cheapest, and gates everything else.

**Infrastructure:** `core/permissions/` provides `AppPermissionPolicy`, `permission_required_factory`, `PermissionMixin`, and `PermissionedViewSet`. Each app cluster wires these to its own permission model.

**How to define permissions:**

```python
# myapp/permissions/models.py
class MyAppAdminPermission(models.Model):
    class Meta:
        default_permissions = ()  # suppress add/change/delete/view
        permissions = [
            ("access_my_feature", "Can access my feature"),
            ("manage_my_records", "Can create and edit records"),
        ]
```

```python
# myapp/permissions/setup.py
from phoxtail.core.permissions import AppPermissionPolicy, permission_required_factory

my_permission_policy = AppPermissionPolicy(MyAppAdminPermission)
my_permission_required = permission_required_factory(my_permission_policy)
```

**How to enforce it:**

```python
# Function-based views
@my_permission_required("access_my_feature")
def my_view(request): ...

# Class-based views
class MyView(MyPermissionMixin, View):
    required_permissions = ["access_my_feature", "manage_my_records"]  # AND logic

# Templates — hides UI the user can't reach
{% if perms.myapp.access_my_feature %}
    <button>Open Feature</button>
{% endif %}
```

**Rules:**
- Superusers always pass (handled by `AppPermissionPolicy` automatically).
- Multiple codenames = AND logic (all required).
- For OR logic, call `policy.user_has_any_permission(user, [...])` directly.
- HTMX requests receive `204 + showToast` instead of a redirect-to-login 403.

**Make permissions appear in the Wagtail Groups editor** (so admins can assign them to groups without needing to open the Django admin):

```python
# myapp/wagtail_hooks.py
from wagtail import hooks
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from myapp.permissions.models import MyAppAdminPermission

@hooks.register("register_permissions")
def register_myapp_permissions():
    content_type = ContentType.objects.get_for_model(MyAppAdminPermission)
    return Permission.objects.filter(content_type=content_type)
```

---

## Layer 2: PAT Token Scopes (credential-level)

This layer only applies to **machine clients** — the CLI, MCP server, or any tool using a Personal Access Token. For a user clicking through a browser UI (session auth), no token is present and this layer is a transparent no-op.

The core invariant: **scopes narrow permissions, they never expand them.** A token authenticates *as* a user. No token can grant capabilities that the underlying user doesn't already have.

```
effective_permissions = user.permissions  ∩  (token.scopes if token else ALL)
```

**When this matters:** A developer has full admin permissions. They issue a token for their CI pipeline with scope `api:read`. That token can run read queries but cannot publish pages — even though the developer personally can.

**Current state:** Token auth and scope storage are implemented (`phoxtail/tokens/`). Scope *enforcement* is a roadmap item — today tokens authenticate identity only. The vocabulary will be: coarse HTTP-shaped scopes (`api:read`, `api:write`) or direct permission codenames.

**Future shape (when enforcement ships):**

```python
@dataclass
class AuthorizationContext:
    user: User
    token: AccessToken | None

    def has_perm(self, codename: str) -> bool:
        if not self.user.has_perm(codename):
            return False
        if self.token and not self.token.scope_covers(codename):
            return False
        return True
```

Layer 1 views and Layer 3 services will receive `ctx` and call `ctx.has_perm()` instead of `user.has_perm()`. Every `policy.user_has_permission(user, ...)` call becomes `ctx.has_perm(...)` — a search-and-replace, no architectural rework.

---

## Layer 3: Service `authorize()` (resource-level)

This layer runs inside the service operation — after the endpoint is open, after the request is authenticated. It answers the finest-grained question: not "can this user manage reservations" but "can this user manage *this* reservation for *this* event at *this* location."

**Why this layer exists:** View decorators can't know which instance you're acting on at URL-dispatch time. Service operations always have the instance in hand.

**How it looks:**

```python
# booking/reservations/services/admin/operations/move.py
class ReservationServiceAdminMove(ServiceOperation):
    def authorize(self) -> None:
        if not self.user.has_perm("booking_core.manage_reservations"):
            raise PermissionDenied
        # resource-level: is this staff assigned to the target event's location?
        if not self.instance.event.location.is_staff(self.user):
            raise PermissionDenied

    def validate(self) -> None: ...
    def perform(self) -> None: ...
```

**Rules:**
- View decorators are the *outer* check — cheap, fast, runs before any DB work.
- `authorize()` is the *inner* check — authoritative, runs even when called from a CLI command, management command, or API endpoint that bypasses views.
- Don't duplicate Layer 1 checks in `authorize()` unless the operation is reachable from outside the view layer.
- Most `authorize()` hooks start as empty stubs and get filled when resource-level rules emerge.

---

## How the layers relate

A request flows through all three in order:

```
HTTP Request
  │
  ├─ Layer 1: Permission Policy (view decorator / template)
  │     "Does this user have access_my_feature?"
  │         NO  → 403
  │         YES ↓
  │
  ├─ Layer 2: PAT Scope (API auth, if machine client)
  │     "Does this token's scope cover this operation?"
  │         NO  → 403
  │         YES ↓
  │
  └─ Layer 3: Service authorize() (operation lifecycle)
        "Can this user act on this specific instance?"
            NO  → PermissionDenied
            YES → validate() → perform()
```

For a normal browser session with no token, Layer 2 is bypassed entirely. For operations with no resource-level rules, Layer 3's `authorize()` is an empty pass-through. Neither absence is a bug — the layers compose independently.

---

## Adding a new app cluster

1. Create `myapp/permissions/models.py` with a `MyAppAdminPermission` anchor model.
2. Create `myapp/permissions/setup.py` with policy, decorator, mixin, and viewset.
3. Add a `register_permissions` Wagtail hook so permissions appear in the Groups editor.
4. Run `makemigrations` + `migrate`.
5. Use `@my_permission_required(...)` on views and `{% if perms.myapp.xxx %}` in templates.
6. Populate `authorize()` hooks in service operations as resource-level rules emerge.

---

## Real example: the AI chatbot

The design bar and chatbot API started as superuser-only (`request.user.is_superuser`). To open them to any user with the right permission, the pattern was applied exactly as above:

```python
# phoxtail/agent/permissions/models.py
class AgentAdminPermission(models.Model):
    class Meta:
        default_permissions = ()
        permissions = [("access_chatbot", "Can access the AI chatbot")]
```

```python
# phoxtail/agent/views.py
@agent_permission_required("access_chatbot")
def chat_history(request): ...
```

```html
{# design_bar.html — renders the whole design bar only for permitted users #}
{% if perms.phoxtail_agent.access_chatbot and page %}
```

```python
# phoxtail/agent/api/v1/chat.py
if not user or not agent_permission_policy.user_has_permission(user, "access_chatbot"):
    raise HttpError(403, "Access denied.")
```

Superusers still pass automatically. Any user assigned to a group that has `access_chatbot` now also gets in — without touching the superuser flag.
