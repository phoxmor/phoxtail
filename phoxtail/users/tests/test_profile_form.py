"""The profile form's phone field: split widget in, model value out."""

from __future__ import annotations

import re

import pytest
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.utils import translation

from phoxtail.core.fields import render_field
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
        html = render_field("phone", UserProfileForm(instance=user)["phone_number"])
        assert 'name="phone_number_0"' in html
        assert 'name="phone_number_1"' in html
        assert 'name="phone_number"' not in html
        # The stored number decompresses back into the two controls.
        assert 'value="GR" selected' in html
        assert 'value="6912345678"' in html
        # The number box's widget is a tel input already; the type is written once.
        assert html.count('type="tel"') == 1
        # Each control gets its own outline, label and tap target.
        assert html.count("fw-md3-outlined") == 2
        assert 'for="id_phone_number_0"' in html
        assert 'for="id_phone_number_1"' in html

    def test_the_pair_points_at_the_error(self, user):
        """The two controls are one group, as Django groups them; the group names the error."""
        html = render_field("phone", UserProfileForm(_payload(phone_number_1="123"), instance=user)["phone_number"])
        assert '<fieldset class="fw-phone-row" aria-describedby="id_phone_number_error">' in html
        assert 'id="id_phone_number_error"' in html

    def test_country_choices_lead_with_the_code(self, user):
        """The narrow country box cuts its text off; the code must come first to stay in view."""
        choices = UserProfileForm(instance=user).fields["phone_number"].fields[0].choices
        assert choices[0] == ("", "—")
        assert ("GR", "+30 Greece") in choices
        names = [label.split(" ", 1)[1] for value, label in choices[1:]]
        assert names.index("Afghanistan") < names.index("Åland Islands") < names.index("Albania")

    def test_country_names_follow_the_page_language(self, user):
        """The form class loads once; its country names must still be the request's."""
        form = UserProfileForm(instance=user)
        with translation.override("el"):
            html = render_field("phone", form["phone_number"])
        assert "+30 Ελλάδα" in html
        names = re.findall(r'<option value="[A-Z]{2}"[^>]*>\+\d+ ([^<]+)</option>', html)
        assert names.index("Καζακστάν") < names.index("Κάτω Χώρες") < names.index("Κένυα")

    def test_the_phone_frame_refuses_another_widget(self, user):
        with pytest.raises(TypeError, match="PhoneNumberPrefixWidget"):
            render_field("phone", UserProfileForm(instance=user)["first_name"])


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
