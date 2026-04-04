from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django_htmx.http import HttpResponseClientRedirect

from phoxtail.booking.subscriptions.models import (
    Subscription,
    SubscriptionType,
)
from phoxtail.booking.subscriptions.services import SubscriptionService
from phoxtail.booking.subscriptions.utils import get_subscription_types_context

from ...constants import SubscriptionStatus


@login_required
def subscription_list_view(request):
    """Display user's subscriptions with their credit balances."""

    user_subscriptions = (
        Subscription.objects.filter(user=request.user)
        .exclude(status=SubscriptionStatus.ARCHIVED)
        .select_related("subscription_type")
        .prefetch_related(
            "credit_balances__service", "subscription_type__credit_allocations__service"
        )
        .order_by("-start_date")
    )

    context = {
        "user_subscriptions": user_subscriptions,
    }
    return render(
        request,
        "phoxtail_booking_subscriptions/public/subscriptions/index.html",
        context,
    )


@login_required
def subscription_type_list_view(request):
    """Display available subscription types for selection."""

    context = get_subscription_types_context()
    return render(
        request,
        "phoxtail_booking_subscriptions/public/subscription_types/list/index.html",
        context,
    )


@login_required
def subscription_create_form_view(request):
    """Display confirmation modal for subscription purchase."""

    subscription_type_id = request.GET.get("subscription_type_id")
    subscription_type = get_object_or_404(
        SubscriptionType.objects.prefetch_related("credit_allocations__service"),
        uuid=subscription_type_id,
    )

    return render(
        request,
        "phoxtail_booking_subscriptions/public/subscription_types/list/partials/forms/subscribe/form.html",
        {"subscription_type": subscription_type},
    )


@login_required
def subscription_create_view(request):
    """Create a new subscription for the user."""

    if request.method == "POST":
        subscription_type_id = request.POST.get("subscription_type_id")
        subscription_type = get_object_or_404(
            SubscriptionType, uuid=subscription_type_id
        )

        try:
            # Create subscription using the centralized service
            subscription = SubscriptionService().public.create(
                user=request.user,
                subscription_type=subscription_type,
            )

            messages.success(
                request,
                f"You have successfully subscribed to {subscription_type.name}!",
            )

            # Use HX-Redirect for HTMX compatibility
            return HttpResponseClientRedirect(
                reverse("dashboard:booking:subscriptions:subscription-list")
            )

        except ValidationError as e:
            for message in e.messages:
                messages.error(request, message)
        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {e}")

        # Get subscription types context for error rendering
        context = get_subscription_types_context()
        return render(
            request,
            "phoxtail_booking_subscriptions/public/subscription_types/list/partials/subscription_types.html",
            context,
        )

    return HttpResponse("Invalid request", status=400)


@login_required
@require_http_methods(["GET", "POST"])
def subscription_renew_form_view(request, subscription_id):
    """
    Display renewal confirmation form and process renewal.
    Handles both GET (display form) and POST (process renewal) requests.
    """
    subscription = get_object_or_404(
        Subscription.objects.select_related("subscription_type__location").filter(
            user=request.user
        ),
        uuid=subscription_id,
    )

    if request.method == "POST":
        try:
            # Execute renewal operation
            SubscriptionService(subscription).public.renew()

            messages.success(
                request,
                f"Your {subscription.subscription_type.name} subscription has been successfully renewed!",
            )

            # Render response with OOB swaps
            user_subscriptions = (
                Subscription.objects.filter(user=request.user)
                .exclude(status=SubscriptionStatus.ARCHIVED)
                .select_related("subscription_type")
                .prefetch_related(
                    "credit_balances__service",
                    "subscription_type__credit_allocations__service",
                )
                .order_by("-start_date")
            )

            context = {
                "subscription": subscription,
                "user_subscriptions": user_subscriptions,
                "renewal_success": True,
            }
            return render(
                request,
                "phoxtail_booking_subscriptions/public/subscriptions/partials/forms/renew/form_response.html",
                context,
            )

        except ValidationError as e:
            for message in e.messages:
                messages.error(request, message)

            context = {
                "subscription": subscription,
                "renewal_success": False,
            }
            return render(
                request,
                "phoxtail_booking_subscriptions/public/subscriptions/partials/forms/renew/form_response.html",
                context,
            )

    # GET request - display confirmation form
    context = {"subscription": subscription}
    return render(
        request,
        "phoxtail_booking_subscriptions/public/subscriptions/partials/forms/renew/form.html",
        context,
    )
