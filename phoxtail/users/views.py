from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django_htmx.http import trigger_client_event

from .forms import UserProfileForm


def redirect_to_allauth_login(request):
    """Redirect the Django admin login URL to the allauth login page."""
    return redirect("account_login")


@login_required
def profile_view(request):
    context = {"user": request.user}
    return render(request, "users/profile/index.html", context)


@login_required
def profile_update_form_view(request):
    user = request.user
    form = UserProfileForm(instance=user)
    context = {"form": form, "user": user}
    return render(request, "users/profile/partials/update_form.html", context)


@login_required
def profile_update_view(request):
    user = request.user
    form = UserProfileForm(request.POST, request.FILES, instance=user)

    saved = form.is_valid()
    if saved:
        if form.has_changed():
            form.save()
            messages.success(request, _("Your profile has been updated successfully."))
        else:
            messages.info(request, _("No changes were made to your profile."))
    else:
        messages.error(request, _("Please correct the errors below."))

    context = {"form": form, "user": user, "saved": saved}
    response = render(request, "users/profile/partials/update_profile_response.html", context)
    if saved:
        trigger_client_event(response, "closeModal")
    return response
