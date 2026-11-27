from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import pgettext
from django_htmx.http import trigger_client_event

from .forms import UserProfileForm


def redirect_to_allauth_login(request):
    """Redirect the Django admin login URL to the allauth login page.

    For a logged-out visitor the ``next`` parameter travels with it, and
    allauth's login view decides whether it is safe to follow. The admin
    also sends a logged-in user here when it refuses them, and allauth sends
    a logged-in user straight on to ``next``; carrying it for them would
    bounce them between the admin and the login page, so it is dropped.
    """
    url = reverse("account_login")
    next_url = request.GET.get(REDIRECT_FIELD_NAME)
    if next_url and not request.user.is_authenticated:
        url += "?" + urlencode({REDIRECT_FIELD_NAME: next_url})
    return redirect(url)


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
        messages.error(request, pgettext("form", "Please correct the errors below."))

    context = {"form": form, "user": user, "saved": saved}
    response = render(request, "users/profile/partials/update_profile_response.html", context)
    if saved:
        trigger_client_event(response, "closeModal")
    return response
