# Event Service Layer Architecture

## Package Structure

```
booking/events/services/
├── __init__.py                          # Re-exports EventService, ProjectedEvent
├── base.py                              # EventService (queries, projections, recurrence)
├── projected.py                         # ProjectedEvent class
├── validation.py                        # ValidationResult + pure validator functions
└── admin/
    ├── __init__.py                      # Re-exports EventServiceAdminGateway
    ├── gateway.py                       # EventServiceAdminGateway
    └── operations/
        ├── __init__.py                  # Re-exports all operations
        ├── create.py                    # EventServiceAdminCreate
        ├── update.py                    # EventServiceAdminUpdate (all 3 scopes)
        └── update_template.py           # EventServiceAdminUpdateTemplate
```

## EventService Core (`base.py`)

The central service class. Accepts an optional `Event` instance:

```python
# For creation (no existing event):
event = EventService().admin.create(**data)

# For operations on existing events:
EventService(event).admin.update(**data)
EventService(event).admin.update_template(**data)
```

**Provides:**
- Reservation/capacity queries (`get_reservation_count`, `get_is_full`, etc.)
- Status helpers (`is_cancelled`, `is_unpublished`)
- Access control (`user_can_access_event`)
- Recurrence generation (`generate_recurring_events`, `_calculate_occurrences`)
- Calendar projections (`get_events_with_recurrence_projections`)
- Conflict checks (`validate_staff_availability`)

## Gateway Pattern

`EventServiceAdminGateway` provides namespaced access to admin operations:

```python
gateway = EventService(event).admin

# Validate-only (for form clean())
result = gateway.validate_create(**data)
result = gateway.validate_update(update_scope=..., **data)
result = gateway.validate_update_template(**data)

# Execute (for form save() or direct callers)
event = gateway.create(**data)               # force=True by default
event, count = gateway.update(**data)        # force=True by default
event = gateway.update_template(**data)      # force=True by default
```

Admin gateway defaults `force=True`: soft warnings are non-blocking. A future public gateway would default `force=False`.

## Operation Lifecycle

Each operation follows `authorize → validate → perform → execute`:

| Phase       | Purpose                                      |
|-------------|----------------------------------------------|
| `authorize` | Permission check (extensible, currently pass) |
| `validate`  | Returns `ValidationResult` with errors/warnings |
| `perform`   | Executes the operation in `transaction.atomic()` |
| `execute`   | Orchestrates: authorize → validate → raise_if_errors → (check warnings if not force) → perform |

## ValidationResult

```python
@dataclass
class ValidationResult:
    errors: list[ValidationMessage]    # Hard blocks
    warnings: list[ValidationMessage]  # Soft conflicts (admin can override)

    def add_error(message, field=None)
    def add_warning(message, field=None)
    def raise_if_errors()       # Raises Django ValidationError
    def raise_if_warnings()     # Raises Django ValidationError
    def merge(other)            # Combines two results
    has_errors, has_warnings, is_valid  # Properties
```

---

## Architectural Shift: Hard Stops → Soft Warnings

### What Changed

The previous monolithic `services.py` (1466 lines) treated **all** conflict scenarios as hard errors — every `raise ValidationError(...)` was a blocking wall. The refactored service layer introduces a two-tier classification: hard errors (physically impossible states) vs. soft warnings (schedule conflicts the admin may intentionally override).

### What Was Removed

| Removed mechanism | Old behavior | Rationale for removal |
|---|---|---|
| `UniqueConstraint("start_datetime", "space")` on `Event` | Database-level hard block on any two non-template events sharing the same start time and space | Overly restrictive — prevents legitimate schedule adjustments like swapping two events, back-to-back bookings where start times don't collide but the constraint blocked partial overlaps, and admin corrections during schedule migrations. The constraint only checked exact `start_datetime` matches, so it missed actual overlaps (e.g. 10:00–11:00 vs 10:30–11:30) while blocking valid non-overlapping events that happened to share a start time in different scenarios. |
| `event_conflicts_with_recurring_event()` | Hard block if a new/updated event's time slot overlapped any projected occurrence from any active recurring template | Removed because the conflict-aware recurrence generation (`generate_recurring_events`) already skips occupied slots at generation time, making this upfront check redundant. It also created a chicken-and-egg problem: admin couldn't create an event in a slot that a template *would* fill, even when the admin intended to override that occurrence. |
| `raise ValidationError` for space-time conflicts (create) | Hard block preventing any overlapping event in the same space | Downgraded to soft warning — admin may be doing a room swap, scheduling a transition period, or correcting a data issue. |
| `raise ValidationError` for staff double-booking | Hard block preventing any staff overlap | Downgraded to soft warning — admin may be reassigning staff across events or an instructor may legitimately float between overlapping sessions. |
| `raise ValidationError` for bulk series conflicts | Hard block on entire series update if any single instance would conflict | Downgraded to soft warning — admin may be restructuring the weekly schedule and knows some conflicts are temporary. |

### What Was Kept As Hard Errors

These remain `add_error` (unconditional blocks) because they represent logically impossible or data-corrupt states:

| Check | Why it stays hard |
|---|---|
| End time ≤ start time | Physically impossible — a negative-duration event is always a mistake |
| Duration > 24 hours | Almost certainly a date/time entry error |
| `recurrence_until` < `start_datetime` | Logically impossible — recurrence ends before it starts |
| Monthly recurrence mutual exclusivity | Invalid rrule configuration — would produce broken recurrence patterns |
| Monthly recurrence incomplete fields | Missing bysetpos/byweekday pair — rrule would silently produce wrong dates |

### Current Conflict Classification

| Check | Severity | Rationale |
|---|---|---|
| End time before start time | Hard error | Physically impossible |
| Duration > 24 hours | Hard error | Almost certainly a typo |
| Recurrence settings invalid | Hard error | Would generate broken recurrences |
| recurrence_until before start | Hard error | Logically impossible |
| Space-time conflict (real events) | Soft warning | Admin may be doing a swap |
| Staff double-booking | Soft warning | Admin may be reassigning staff |
| Bulk update series conflicts | Soft warning | Admin may be restructuring schedule |

Projected/virtual event conflicts are **not validated** — the conflict-aware recurrence generation handles those at generation time.

### How Soft Warnings Surface

Warnings don't silently disappear. The flow is:

1. **Form `clean()`** — calls `validate_create/update/update_template`, collects warnings into `form._warnings`
2. **View layer** — after successful save, iterates `form._warnings` and surfaces each as a `messages.warning()` toast
3. **API/programmatic callers** — can pass `force=False` to make warnings behave as hard errors, or inspect the `ValidationResult` directly

This means an admin creating an overlapping event will see a yellow warning banner like *"This time slot conflicts with an existing event: Pilates (2024-06-05 10:00 - 11:00) in Room A"* — they proceeded intentionally, but the system made the conflict visible.

### Safety Nets That Replace Hard Stops

| Layer | Mechanism |
|---|---|
| Recurrence generation | `generate_recurring_events()` checks both source-date dedup and space-time overlap before creating each instance — occupied slots are silently skipped |
| Source-date dedup | `recurrence_source_date` field (new in this refactor) tracks which occurrence date an event was generated for. A moved event (different `start_datetime`) still suppresses re-generation for that date. This prevents ghost duplicates after admin reschedules. |
| Projection dedup | `get_events_with_recurrence_projections()` uses the same source-date dedup — calendar views never show a projected dot alongside a real event for the same occurrence |

### Risks and Future Hardening

The permissive approach trades flexibility for the risk that admins create genuinely conflicting schedules without noticing. Areas to watch:

**Short-term (current gaps):**
- No audit trail for force-overridden warnings — if an admin creates a double-booking, there's no record that they were warned
- Warning messages are ephemeral (Django messages framework) — if the page is refreshed or the admin navigates away, the warning is lost
- No "undo" mechanism — once an overlapping event is created, cleaning it up is manual
- Bulk updates show at most one conflict warning (breaks early) — admin may not realize the full scope of conflicts in a large series

**Medium-term (recommended improvements):**
- Conflict dashboard: a scheduling view that highlights all current space-time overlaps and staff double-bookings across the active schedule
- Warning persistence: log overridden warnings to an audit model (`EventWarningLog`) so facility managers can review decisions
- Confirmation step for bulk operations: before applying a series-wide update that produces N conflicts, show a summary ("This will create 3 space conflicts and 1 staff conflict across 12 events") and require explicit confirmation
- Capacity validation: currently no check that `capacity ≤ space.capacity` — an admin can create a 50-person event in a 10-person room

**Long-term (architectural):**
- Public gateway (`EventServicePublicGateway`) with `force=False` default — end-user-facing booking flows should treat all conflicts as hard errors
- Role-based force permissions — only admin/manager roles can override warnings; staff-level users get hard errors
- Conflict resolution workflows — instead of just warning, offer the admin resolution actions ("Cancel the conflicting event", "Move this event to Room B", "Assign different staff")

---

## Conflict-Aware Recurrence Generation

`EventService.generate_recurring_events()` skips occurrences where:
1. A series instance with matching `recurrence_source_date` already exists (dedup — survives event moves)
2. A real event (from any source) already occupies the space-time slot (conflict avoidance)

This makes it safe to relax projected event conflict validation for admin operations — the generation itself is the safety net.

## Form Integration

Forms follow this pattern:

```python
def clean(self):
    cleaned_data = super().clean()
    if not self.errors:
        result = EventService(...).admin.validate_xxx(**cleaned_data)
        if result.has_errors:
            for err in result.errors:
                self.add_error(err.field, err.message)
        if result.has_warnings:
            self._warnings = result.warnings
    return cleaned_data

def save(self, commit=True):
    if not commit:
        return super().save(commit=False)
    return EventService(...).admin.xxx(**self.cleaned_data)
```

Views surface warnings after save:

```python
for warn in getattr(form, "_warnings", []):
    messages.warning(request, warn.message)
```

## Test Suite

```
booking/events/tests/
├── conftest.py                         # Shared fixtures (user, space, service, event, template)
├── factories.py                        # SpaceFactory, StaffFactory, EventFactory, RecurringTemplateFactory
└── services/
    ├── test_event_service.py           # Core: capacity, status, access, recurrence, projections, staff
    └── admin/
        ├── test_create.py              # Happy path, hard errors, soft warnings
        ├── test_update.py              # Single/future/all-in-series, hard errors, soft warnings
        └── test_update_template.py     # Template updates, hard errors
```

Factories reuse `UserFactory`, `LocationFactory`, `ServiceFactory` from `booking/subscriptions/tests/factories.py`.

## Adding New Operations

1. Create `booking/events/services/admin/operations/my_operation.py`
2. Implement `authorize()`, `validate()`, `perform()`, `execute()` methods
3. Re-export from `operations/__init__.py`
4. Add delegation method to `EventServiceAdminGateway`
5. Add tests in `booking/events/tests/services/admin/test_my_operation.py`
