"""
Validation primitives and pure validator functions for event operations.
"""

from dataclasses import dataclass, field

from django.core.exceptions import ValidationError


@dataclass
class ValidationMessage:
    """A single validation message (error or warning)."""

    message: str
    field: str = None


@dataclass
class ValidationResult:
    """
    Collects hard errors and soft warnings from validation.

    Hard errors always prevent the operation.
    Soft warnings can be overridden by trusted callers (e.g. admin gateway with force=True).
    """

    errors: list[ValidationMessage] = field(default_factory=list)
    warnings: list[ValidationMessage] = field(default_factory=list)

    def add_error(self, message: str, field: str = None):
        self.errors.append(ValidationMessage(message=message, field=field))

    def add_warning(self, message: str, field: str = None):
        self.warnings.append(ValidationMessage(message=message, field=field))

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    @property
    def is_valid(self) -> bool:
        return not self.has_errors

    def raise_if_errors(self):
        """Build a Django ValidationError from all collected errors."""
        if not self.has_errors:
            return

        # Group errors by field
        error_dict = {}
        error_list = []
        for err in self.errors:
            if err.field:
                error_dict.setdefault(err.field, []).append(err.message)
            else:
                error_list.append(err.message)

        if error_dict and error_list:
            # Mix of field and non-field errors
            raise ValidationError({**error_dict, "__all__": error_list})
        elif error_dict:
            raise ValidationError(error_dict)
        else:
            raise ValidationError(error_list)

    def raise_if_warnings(self):
        """Build a Django ValidationError from all collected warnings."""
        if not self.has_warnings:
            return

        error_dict = {}
        error_list = []
        for warn in self.warnings:
            if warn.field:
                error_dict.setdefault(warn.field, []).append(warn.message)
            else:
                error_list.append(warn.message)

        if error_dict and error_list:
            raise ValidationError({**error_dict, "__all__": error_list})
        elif error_dict:
            raise ValidationError(error_dict)
        else:
            raise ValidationError(error_list)

    def merge(self, other: "ValidationResult"):
        """Combine two results in place."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


# ---------------------------------------------------------------------------
# Pure validator functions (extracted from old EventService static methods)
# ---------------------------------------------------------------------------


def validate_time_range(start_datetime, end_datetime) -> ValidationResult:
    """Validate that end > start and duration <= 24 hours."""
    result = ValidationResult()

    if not start_datetime or not end_datetime:
        return result

    if end_datetime <= start_datetime:
        result.add_error("End time must be after start time.", field="end_datetime")

    duration = end_datetime - start_datetime
    max_duration_hours = 24
    if duration.total_seconds() > (max_duration_hours * 3600):
        result.add_error(
            f"Event duration cannot exceed {max_duration_hours} hours. "
            f"Current duration: {duration.total_seconds() / 3600:.1f} hours. "
            f"Please check your end date and time.",
            field="end_datetime",
        )

    return result


def validate_recurrence_until(start_datetime, recurrence_until) -> ValidationResult:
    """Validate that recurrence_until is after start_datetime."""
    result = ValidationResult()

    if recurrence_until and start_datetime:
        if recurrence_until < start_datetime:
            result.add_error(
                "Recurrence end date must be after the event start time.",
                field="recurrence_until",
            )

    return result


def validate_monthly_recurrence(
    recurrence_freq,
    recurrence_bymonthday,
    recurrence_bysetpos,
    recurrence_byweekday_monthly,
) -> ValidationResult:
    """Validate monthly recurrence fields for mutual exclusivity."""
    from ..constants import RecurrenceFrequency

    result = ValidationResult()

    if recurrence_freq != RecurrenceFrequency.MONTHLY:
        return result

    has_bymonthday = recurrence_bymonthday is not None
    has_bysetpos = recurrence_bysetpos is not None
    has_byweekday_monthly = recurrence_byweekday_monthly is not None

    if has_bymonthday and (has_bysetpos or has_byweekday_monthly):
        result.add_error("Cannot specify both 'day of month' and 'position + weekday' options. Please choose one.")

    if has_bysetpos and not has_byweekday_monthly:
        result.add_error(
            "Weekday is required when using position (e.g., 'First Monday').",
            field="recurrence_byweekday_monthly",
        )

    if has_byweekday_monthly and not has_bysetpos:
        result.add_error(
            "Position is required when using weekday (e.g., 'First' Monday).",
            field="recurrence_bysetpos",
        )

    if not has_bymonthday and not (has_bysetpos and has_byweekday_monthly):
        result.add_error("For monthly recurrence, you must specify either 'day of month' or 'position + weekday'.")

    return result
