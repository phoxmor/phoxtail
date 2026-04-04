from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from phoxtail.booking.core.permissions import booking_permission_required
from phoxtail.users.services import UserService

from .forms import UserCreateForm, UserUpdateForm
from .utils import UsersContextBuilder, _sync_booking_groups

User = get_user_model()


@booking_permission_required("access_users_management")
def admin_users_list_view(request):
    context = UsersContextBuilder.get_full_context(request)

    is_htmx_request = bool(request.htmx)
    context["is_htmx_request"] = is_htmx_request

    if is_htmx_request:
        return render(
            request, "phoxtail_booking_core/admin/users/partials/users.html", context
        )

    return render(request, "phoxtail_booking_core/admin/users/index.html", context)


@booking_permission_required("access_users_management", "edit_booking_users")
def admin_user_update_form_view(request, user_id):
    """
    Displays and processes the user edit drawer form.
    Handles both GET (display) and POST (update) requests.
    """
    edited_user = get_object_or_404(User, uuid=user_id)

    if request.method == "POST":
        form = UserUpdateForm(request.POST, instance=edited_user)

        if form.is_valid():
            booking_groups = form.cleaned_data.pop("booking_groups")
            try:
                edited_user.service.admin.update(request=request, **form.cleaned_data)
                _sync_booking_groups(edited_user, booking_groups)
                messages.success(
                    request,
                    f"User {edited_user.get_full_name() or edited_user.email} successfully updated.",
                )
            except ValidationError as e:
                for message in e.messages:
                    messages.error(request, message)
        else:
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)

        users_context = UsersContextBuilder.get_full_context(request)
        context = {
            "form": form,
            "edited_user": edited_user,
            **users_context,
        }

        return render(
            request,
            "phoxtail_booking_core/admin/users/partials/forms/update/form_response.html",
            context,
        )

    form = UserUpdateForm(instance=edited_user)
    context = {"form": form, "edited_user": edited_user}

    return render(
        request,
        "phoxtail_booking_core/admin/users/partials/forms/update/form.html",
        context,
    )


@booking_permission_required("access_users_management", "create_booking_users")
def admin_user_create_form_view(request):
    """Displays the create user drawer form."""
    form = UserCreateForm()
    context = {"form": form}

    return render(
        request,
        "phoxtail_booking_core/admin/users/partials/forms/create/form.html",
        context,
    )


@booking_permission_required("access_users_management", "create_booking_users")
def admin_user_create_view(request):
    """Processes the user creation action."""
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    form = UserCreateForm(request.POST)
    users_context = UsersContextBuilder.get_full_context(request)
    context = {**users_context, "form": form}
    created = False

    if form.is_valid():
        booking_groups = form.cleaned_data.get("booking_groups")
        user = UserService().admin.create(
            email=form.cleaned_data["email"],
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"],
            password=form.cleaned_data["password1"],
            request=request,
        )
        _sync_booking_groups(user, booking_groups)
        created = True
        messages.success(
            request,
            f"User {user.get_full_name() or user.email} successfully created.",
        )
        users_context = UsersContextBuilder.get_full_context(request)
        context.update(users_context)

    context["created"] = created

    return render(
        request,
        "phoxtail_booking_core/admin/users/partials/forms/create/form_response.html",
        context,
    )


@booking_permission_required("access_users_management")
def admin_users_filters_form_view(request):
    """Displays the filters modal (filter state only, no list building)."""
    context = UsersContextBuilder.get_filters_context(request)

    return render(
        request,
        "phoxtail_booking_core/admin/users/partials/forms/filters/form.html",
        context,
    )


@booking_permission_required("access_users_management")
def admin_users_filters_view(request):
    """Processes filter changes and returns OOB swaps."""
    context = UsersContextBuilder.get_full_context(request)

    return render(
        request,
        "phoxtail_booking_core/admin/users/partials/forms/filters/form_response.html",
        context,
    )


@booking_permission_required("access_users_management")
def admin_users_search_view(request):
    """Processes search changes and returns OOB swaps."""
    context = UsersContextBuilder.get_full_context(request)

    return render(
        request,
        "phoxtail_booking_core/admin/users/partials/forms/search/form_response.html",
        context,
    )
