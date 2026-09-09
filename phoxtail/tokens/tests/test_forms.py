import pytest

from phoxtail.tokens.admin.forms import AccessTokenCreateForm

pytestmark = pytest.mark.django_db


class TestAccessTokenCreateForm:
    def test_minimal_valid_form(self):
        form = AccessTokenCreateForm({"name": "Laptop CLI"})
        assert form.is_valid(), form.errors

    def test_blank_name_invalid(self):
        form = AccessTokenCreateForm({"name": ""})
        assert not form.is_valid()
        assert "name" in form.errors

    def test_blank_scopes_stays_empty(self):
        """No implicit full access: emptiness is not a grant. The service
        layer decides whether an empty list is acceptable, and it is only
        acceptable alongside `unrestricted`."""
        form = AccessTokenCreateForm({"name": "t", "scopes": ""})
        assert form.is_valid()
        assert form.cleaned_data["scopes"] == []

    def test_only_whitespace_scopes_stays_empty(self):
        form = AccessTokenCreateForm({"name": "t", "scopes": "   ,  ,"})
        assert form.is_valid()
        assert form.cleaned_data["scopes"] == []

    def test_unrestricted_defaults_off(self):
        """The broad option must be chosen, never arrived at."""
        form = AccessTokenCreateForm({"name": "t", "scopes": "a"})
        assert form.is_valid()
        assert form.cleaned_data["unrestricted"] is False

    def test_comma_separated_scopes_split(self):
        form = AccessTokenCreateForm({"name": "t", "scopes": "read:streams, write:design , publish"})
        assert form.is_valid()
        assert form.cleaned_data["scopes"] == [
            "read:streams",
            "write:design",
            "publish",
        ]

    def test_drops_empty_entries_between_commas(self):
        form = AccessTokenCreateForm({"name": "t", "scopes": "a,,b,"})
        assert form.is_valid()
        assert form.cleaned_data["scopes"] == ["a", "b"]
