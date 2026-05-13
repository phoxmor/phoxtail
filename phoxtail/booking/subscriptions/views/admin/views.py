from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from phoxtail.booking.core.permissions import (
    booking_permission_policy,
    booking_permission_required,
)
from phoxtail.booking.subscriptions.models import Subscription
from phoxtail.booking.subscriptions.services import SubscriptionService
from phoxtail.core.views import SingleSelectSearchView

from .forms import SubscriptionCreateForm
from .utils import BillingContextBuilder


@booking_permission_required("access_billing_management")
def admin_subscription_list_view(request):
    context = BillingContextBuilder.get_full_context(request)

    is_htmx_request = bool(request.htmx)
    context["is_htmx_request"] = is_htmx_request

    if is_htmx_request:
        return render(
            request,
            "phoxtail_booking_subscriptions/admin/billing/partials/billing.html",
            context,
        )

    return render(request, "phoxtail_booking_subscriptions/admin/billing/index.html", context)


@booking_permission_required("access_billing_management", "manage_billing_subscriptions")
def admin_subscription_update_form_view(request, subscription_id):
    """
    Displays the update subscription form in the billing section for admin to edit existing subscriptions.
    Handles both GET (display form) and POST (process form) requests.
    Includes inline formset for credit balances.
    """
    from phoxtail.booking.subscriptions.forms import (
        SubscriptionCreditBalanceFormSet,
        SubscriptionUpdateForm,
    )

    subscription = get_object_or_404(Subscription, uuid=subscription_id)

    if request.method == "POST":
        # Initialize both form and formset with POST data
        form = SubscriptionUpdateForm(request.POST, instance=subscription)
        formset = SubscriptionCreditBalanceFormSet(request.POST, instance=subscription)

        # Validate both form and formset
        if form.is_valid() and formset.is_valid():
            try:
                # Save the parent form first
                subscription = form.save()
                # Then save the formset (credit balances)
                formset.save()

                messages.success(
                    request,
                    f"Subscription for"
                    f" {subscription.user.get_full_name() or subscription.user.username}"
                    " successfully updated.",
                )
            except ValidationError as e:
                for message in e.messages:
                    messages.error(request, message)
        else:
            # Form or formset has errors
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)

            # Also add formset errors
            for form_errors in formset.errors:
                for field, errors in form_errors.items():
                    for error in errors:
                        messages.error(request, error)

        billing_context = BillingContextBuilder.get_full_context(request)
        context = {
            "form": form,
            "formset": formset,
            "subscription": subscription,
            **billing_context,
        }

        return render(
            request,
            "phoxtail_booking_subscriptions/admin/billing/partials/forms/update/subscription/form_response.html",
            context,
        )
    else:
        # GET request - initialize form and formset with existing data
        form = SubscriptionUpdateForm(instance=subscription)
        formset = SubscriptionCreditBalanceFormSet(instance=subscription)

    context = {
        "form": form,
        "formset": formset,
        "subscription": subscription,
    }

    return render(
        request,
        "phoxtail_booking_subscriptions/admin/billing/partials/forms/update/subscription/form.html",
        context,
    )


@booking_permission_required("access_billing_management", "manage_billing_subscriptions")
def admin_subscription_create_form_view(request):
    """
    Displays the create subscription drawer form for admin.
    """
    form = SubscriptionCreateForm()

    context = {
        "form": form,
        "search_user_url": reverse(
            "billing_management:admin_subscription_create_search_user",
        ),
        "search_subscription_type_url": reverse(
            "billing_management:admin_subscription_create_search_subscription_type",
        ),
    }

    return render(
        request,
        "phoxtail_booking_subscriptions/admin/billing/partials/forms/create/admin_subscription_create_form.html",
        context,
    )


@booking_permission_required("access_billing_management", "manage_billing_subscriptions")
def admin_subscription_create_view(request):
    """
    Processes the subscription creation action for admin.
    """
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    form = SubscriptionCreateForm(request.POST)

    billing_context = BillingContextBuilder.get_full_context(request)

    context = {
        **billing_context,
        "form": form,
        "search_user_url": reverse(
            "billing_management:admin_subscription_create_search_user",
        ),
        "search_subscription_type_url": reverse(
            "billing_management:admin_subscription_create_search_subscription_type",
        ),
    }

    created = False

    if form.is_valid():
        try:
            subscription = SubscriptionService().admin.create(
                user=form.cleaned_data["user"],
                subscription_type=form.cleaned_data["subscription_type"],
            )
            created = True
            messages.success(
                request,
                f"Subscription successfully created for "
                f"{subscription.user.get_full_name() or subscription.user.username} "
                f"with {subscription.subscription_type.name}.",
            )
            billing_context = BillingContextBuilder.get_full_context(request)
            context.update(billing_context)
        except ValidationError as e:
            for message in e.messages:
                messages.error(request, message)

    context["created"] = created

    return render(
        request,
        "phoxtail_booking_subscriptions/admin/billing/partials/forms/create/admin_subscription_create_response.html",
        context,
    )


def _subscription_create_form_state_context(form):
    """Shared helper: form state values for OOB placeholder sync."""
    return {
        "user_value": form["user"].value(),
        "subscription_type_value": form["subscription_type"].value(),
    }


class _SubscriptionCreateSingleSelectBase(SingleSelectSearchView):
    """Shared base for subscription create search views."""

    permission_policy = booking_permission_policy
    required_permissions = ["access_billing_management", "manage_billing_subscriptions"]
    form_class = SubscriptionCreateForm
    hx_include = "#create-subscription-parent-fields, #create-subscription-form-placeholder"

    def get_form(self, data):
        return self.form_class(data)

    def get_extra_context(self, form):
        return _subscription_create_form_state_context(form)


class SubscriptionCreateSearchUserView(_SubscriptionCreateSingleSelectBase):
    field_name = "user"
    search_url_name = "billing_management:admin_subscription_create_search_user"
    oob_response_template = (
        "phoxtail_booking_subscriptions/admin/billing/partials/forms/create/widgets/user_search_response.html"
    )


class SubscriptionCreateSearchSubscriptionTypeView(_SubscriptionCreateSingleSelectBase):
    field_name = "subscription_type"
    search_url_name = "billing_management:admin_subscription_create_search_subscription_type"
    item_template = (
        "phoxtail_booking_subscriptions/admin/billing/partials/forms/create/widgets/subscription_type_item_display.html"
    )
    oob_response_template = (
        "phoxtail_booking_subscriptions/admin/billing/partials/forms/create/widgets/"
        "subscription_type_search_response.html"
    )


@booking_permission_required("access_billing_management")
def admin_billing_filters_form_view(request):
    """
    Displays the filters modal for the billing view (filters only, no actions).
    Uses lightweight filter context only - no expensive list building.
    """
    context = BillingContextBuilder.get_filters_context(request)

    return render(
        request,
        "phoxtail_booking_subscriptions/admin/billing/partials/forms/filters/form.html",
        context,
    )


@booking_permission_required("access_billing_management")
def admin_billing_filters_view(request):
    """
    Processes filter changes and returns OOB swaps to update both the list and the filters form.
    This allows filter state to be managed server-side without JavaScript.
    """
    context = BillingContextBuilder.get_full_context(request)

    return render(
        request,
        "phoxtail_booking_subscriptions/admin/billing/partials/forms/filters/form_response.html",
        context,
    )


@booking_permission_required("access_billing_management")
def admin_billing_search_view(request):
    """
    Processes search changes and returns OOB swaps to update both the list and the search form.
    This allows search state to be managed server-side without JavaScript.
    """
    context = BillingContextBuilder.get_full_context(request)

    return render(
        request,
        "phoxtail_booking_subscriptions/admin/billing/partials/forms/search/form_response.html",
        context,
    )


@booking_permission_required("access_billing_management", "manage_billing_subscriptions")
def admin_subscription_renew_form_view(request, subscription_id):
    """
    Display renewal confirmation form and process renewal for admin.
    Handles both GET (display form) and POST (process renewal) requests.
    """
    subscription = get_object_or_404(
        Subscription.objects.select_related("subscription_type__location").prefetch_related(
            "subscription_type__credit_allocations__service"
        ),
        uuid=subscription_id,
    )

    if request.method == "POST":
        try:
            # Execute renewal operation using admin service
            new_subscription = SubscriptionService(subscription).admin.renew()

            messages.success(
                request,
                f"Subscription for {subscription.user.get_full_name() or subscription.user.username} "
                f"has been successfully renewed!",
            )

            # Get updated billing context
            billing_context = BillingContextBuilder.get_full_context(request)

            # Initialize form and formset for the new subscription (needed for update form template)
            from phoxtail.booking.subscriptions.forms import (
                SubscriptionCreditBalanceFormSet,
                SubscriptionUpdateForm,
            )

            form = SubscriptionUpdateForm(instance=new_subscription)
            formset = SubscriptionCreditBalanceFormSet(instance=new_subscription)

            context = {
                "subscription": new_subscription,
                "form": form,
                "formset": formset,
                "renewal_success": True,
                **billing_context,
            }
            return render(
                request,
                "phoxtail_booking_subscriptions/admin/billing/partials/forms/renew/form_response.html",
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
                "phoxtail_booking_subscriptions/admin/billing/partials/forms/renew/form_response.html",
                context,
            )

    # GET request - display confirmation form
    context = {"subscription": subscription}
    return render(
        request,
        "phoxtail_booking_subscriptions/admin/billing/partials/forms/renew/form.html",
        context,
    )
