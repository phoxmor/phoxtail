"""
Celery tasks for event management.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def generate_recurring_events_task(days_ahead=7, location_id=None):
    """
    Generate recurring event instances from active templates.

    This task finds all active recurrence templates and generates
    future event instances based on their recurrence patterns.

    Args:
        days_ahead: How many days ahead to generate events (default: 7)
        location_id: Optional location UUID to filter templates by location

    Returns:
        int: Total number of events created

    Usage:
        # Run asynchronously for all locations
        generate_recurring_events_task.delay(days_ahead=7)

        # Run asynchronously for specific location
        generate_recurring_events_task.delay(days_ahead=7, location_id=<location_id>)

        # Run synchronously (for testing)
        result = generate_recurring_events_task(days_ahead=7, location_id=<location_id>)
    """
    from phoxtail.booking.events.models import Event

    location_msg = f" for location_id={location_id}" if location_id else ""
    logger.info(
        f"Starting recurring event generation ({days_ahead} days ahead{location_msg})..."
    )

    # Get all active recurrence templates
    recurring_templates = Event.objects.active_recurrence_templates()

    # Filter by location if specified
    if location_id:
        recurring_templates = recurring_templates.filter(space__location_id=location_id)

    if not recurring_templates.exists():
        logger.info("No active recurrence templates found")
        return 0

    logger.info(f"Found {recurring_templates.count()} active template(s)")

    total_created = 0

    for template in recurring_templates:
        try:
            # Generate events for this template
            created_count = template.generate_recurring_events(days_ahead=days_ahead)
            total_created += created_count

            if created_count > 0:
                logger.info(
                    f"✓ Template '{template}': Created {created_count} event(s)"
                )
            else:
                logger.debug(f"✓ Template '{template}': No new events needed")

        except Exception as e:
            logger.error(
                f"✗ Error generating events for template '{template}': {e}",
                exc_info=True,
            )
            # Continue with other templates even if one fails
            continue

    logger.info(f"Recurring event generation complete. Total created: {total_created}")
    return total_created
