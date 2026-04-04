"""
Admin gateway — namespaced access to admin-specific event operations.
"""

from typing import TYPE_CHECKING

from .operations import (
    EventServiceAdminCreate,
    EventServiceAdminDelete,
    EventServiceAdminUpdate,
    EventServiceAdminUpdateTemplate,
)

if TYPE_CHECKING:
    from ...models import Event
    from ..base import EventService
    from ..validation import ValidationResult


class EventServiceAdminGateway:
    """
    Gateway to all admin domain operations for events.

    Provides both validate-only and execute entry points.
    Execute methods default to force=True so that soft warnings
    are non-blocking for admin callers.
    """

    def __init__(self, service: "EventService") -> None:
        self.service = service

    # ------------------------------------------------------------------
    # Validation-only entry points (for form clean())
    # ------------------------------------------------------------------

    def validate_create(self, **data) -> "ValidationResult":
        operation = EventServiceAdminCreate(self.service)
        return operation.validate(**data)

    def validate_update(self, update_scope=None, **data) -> "ValidationResult":
        operation = EventServiceAdminUpdate(self.service)
        return operation.validate(update_scope=update_scope, **data)

    def validate_update_template(self, **data) -> "ValidationResult":
        operation = EventServiceAdminUpdateTemplate(self.service)
        return operation.validate(**data)

    def validate_delete(self, delete_scope=None) -> "ValidationResult":
        operation = EventServiceAdminDelete(self.service)
        return operation.validate(delete_scope=delete_scope)

    # ------------------------------------------------------------------
    # Execute entry points (for form save() and non-form callers)
    # ------------------------------------------------------------------

    def create(self, force: bool = True, **data) -> "Event":
        """Create a new event. force=True skips soft-warning check."""
        operation = EventServiceAdminCreate(self.service)
        return operation.execute(force=force, **data)

    def update(
        self,
        update_scope: str | None = None,
        force: bool = True,
        **data,
    ) -> tuple["Event", int]:
        """Update an event (single, this-and-future, or all-in-series)."""
        operation = EventServiceAdminUpdate(self.service)
        return operation.execute(update_scope=update_scope, force=force, **data)

    def update_template(self, force: bool = True, **data) -> "Event":
        """Update a template event."""
        operation = EventServiceAdminUpdateTemplate(self.service)
        return operation.execute(force=force, **data)

    def delete(
        self,
        delete_scope: str | None = None,
        force: bool = True,
    ) -> int:
        """Delete an event (single, this-and-future, or all-in-series)."""
        operation = EventServiceAdminDelete(self.service)
        return operation.execute(delete_scope=delete_scope, force=force)
