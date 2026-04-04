from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel

from .constants import RecurrenceFrequency, RecurrenceWeekday


class RecurrenceMixin(models.Model):
    """
    Mixin to add recurrence functionality to models.
    All fields are nullable to support one-time (non-recurring) instances.
    """

    recurrence_freq = models.IntegerField(
        null=True,
        blank=True,
        choices=RecurrenceFrequency.choices,
        verbose_name=_("Frequency"),
        help_text=_("Frequency of recurrence"),
    )
    recurrence_interval = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name=_("Interval"),
        help_text=_("Interval between iterations (e.g., 2 for bi-weekly)"),
    )
    recurrence_byweekday = models.JSONField(
        blank=True,
        default=list,
        verbose_name=_("Weekdays"),
        help_text=_(
            "Which days of the week to repeat on (0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday)"
        ),
    )
    recurrence_bymonthday = models.IntegerField(
        null=True,
        blank=True,
        choices=[(i, _(f"Day {i}")) for i in range(1, 32)] + [(-1, _("Last Day"))],
        verbose_name=_("Day of month"),
        help_text=_("Specific day of the month (1-31 or -1 for last day of month)"),
    )
    recurrence_bysetpos = models.IntegerField(
        null=True,
        blank=True,
        choices=[
            (1, _("First")),
            (2, _("Second")),
            (3, _("Third")),
            (4, _("Fourth")),
            (-1, _("Last")),
        ],
        verbose_name=_("Position"),
        help_text=_("Position of the weekday in the month (e.g., 'First Monday')"),
    )
    recurrence_byweekday_monthly = models.IntegerField(
        null=True,
        blank=True,
        choices=RecurrenceWeekday.choices,
        verbose_name=_("Weekday for monthly recurrence"),
        help_text=_(
            "Which weekday to use with position (e.g., 'Monday' in 'First Monday')"
        ),
    )
    recurrence_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Recurrence end"),
        help_text=_("Stop generating recurring events after this date/time"),
    )
    recurrence_excluded_dates = models.JSONField(
        blank=True,
        default=list,
        verbose_name=_("Excluded dates"),
        help_text=_(
            "Dates to skip during recurrence generation and projection. "
            "Populated automatically when a single occurrence is deleted."
        ),
    )
    recurrence_source_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Original occurrence date"),
        help_text=_(
            "The date from the recurrence pattern this instance covers. "
            "Set once at creation; not updated when the event is moved."
        ),
    )
    recurrence_template = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="series_instances",
        verbose_name=_("Template"),
        help_text=_("Template instance that defines this recurring series"),
    )
    is_recurrence_template = models.BooleanField(
        default=False,
        verbose_name=_("Is Template"),
        help_text=_("True if this is a template instance (not a real occurrence)"),
    )

    recurrence_panels = [
        FieldPanel("recurrence_freq"),
        FieldPanel("recurrence_interval"),
        FieldPanel("recurrence_byweekday"),
        FieldPanel("recurrence_bymonthday"),
        FieldPanel("recurrence_bysetpos"),
        FieldPanel("recurrence_byweekday_monthly"),
        FieldPanel("recurrence_until"),
        FieldPanel("recurrence_excluded_dates"),
    ]

    class Meta:
        abstract = True
