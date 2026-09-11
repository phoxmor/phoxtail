"""The profile form's phone field: split widget in, model value out."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string

from phoxtail.users.forms import UserProfileForm

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="member",
        email="member@example.com",
        first_name="Given",
        last_name="Family",
        phone_number="+306912345678",
    )


def _payload(**overrides):
    return {
        "first_name": "Given",
        "last_name": "Family",
        "phone_number_0": "GR",
        "phone_number_1": "6912345678",
        **overrides,
    }


class TestPhoneNumberRoundTrip:
    def test_split_subwidgets_save(self, user):
        form = UserProfileForm(_payload(phone_number_1="6900000000"), instance=user)
        assert form.is_valid(), form.errors
        form.save()
        user.refresh_from_db()
        assert str(user.phone_number) == "+306900000000"

    def test_number_can_be_cleared(self, user):
        """The model allows a blank number, so the edit form must too."""
        form = UserProfileForm(_payload(phone_number_0="", phone_number_1=""), instance=user)
        assert form.is_valid(), form.errors
        form.save()
        user.refresh_from_db()
        assert not user.phone_number

    def test_widget_posts_the_names_the_field_reads(self, user):
        """The rendered field must carry the suffixed names, or nothing binds."""
        html = render_to_string(
            "phoxtail_core/forms/widgets/phone.html",
            {"field": UserProfileForm(instance=user)["phone_number"]},
        )
        assert 'name="phone_number_0"' in html
        assert 'name="phone_number_1"' in html
        assert 'name="phone_number"' not in html
        # The stored number decompresses back into the two controls.
        assert 'value="GR" selected' in html
        assert 'value="6912345678"' in html
        # Each control gets its own outline, label and tap target.
        assert html.count("fw-md3-outlined") == 2
        assert 'for="id_phone_number_0"' in html
        assert 'for="id_phone_number_1"' in html


@pytest.mark.urls("phoxtail.users.tests.urls")
class TestFailedSaveResponse:
    def test_errors_reswap_the_form_not_the_drawer(self, user):
        """A failed save must leave the open drawer in the DOM."""
        form = UserProfileForm(_payload(phone_number_1="123"), instance=user)
        assert not form.is_valid()
        html = render_to_string(
            "users/profile/partials/update_profile_response.html",
            {"form": form, "user": user},
        )
        assert 'hx-swap-oob="innerHTML:#profile-update-form-body"' in html
        assert "phoxtail-modal-overlay" not in html
