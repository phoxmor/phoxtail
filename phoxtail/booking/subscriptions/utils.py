from django.db.models import Prefetch

from .models import SubscriptionType, SubscriptionTypeCreditAllocation


def get_subscription_types_context():
    """
    Helper function to get subscription types context for views.
    """
    # Prefetch credit allocations with their services
    prefetched_credit_allocations = Prefetch(
        "credit_allocations",
        queryset=SubscriptionTypeCreditAllocation.objects.select_related(
            "service"
        ).order_by("sort_order"),
        to_attr="prefetched_credit_allocations",
    )

    subscription_types = (
        SubscriptionType.objects.filter(is_active=True, is_public=True)
        .prefetch_related(prefetched_credit_allocations)
        .order_by("sort_order")
    )

    return {"subscription_types": subscription_types}
