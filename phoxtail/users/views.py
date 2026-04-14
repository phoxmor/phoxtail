from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import UserProfileForm


def login_redirect_view(request):
    """Redirect authenticated users to the wagtail admin or home; send others to login."""
    if not request.user.is_authenticated:
        return redirect("account_login")

    if request.user.has_perm("wagtailadmin.access_admin"):
        return redirect("wagtailadmin_home")

    return redirect("/")


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

    if form.is_valid():
        if form.has_changed():
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
        else:
            messages.info(request, "No changes were made to your profile.")
    else:
        messages.error(request, "Please correct the errors below.")

    context = {"form": form, "user": user}
    return render(
        request, "users/profile/partials/update_profile_response.html", context
    )
