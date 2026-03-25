from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied
from django.http import QueryDict
from django.test import RequestFactory
from django_htmx.middleware import HtmxDetails

from phoxtail.streams.views import (
    _get_studio_form,
    studio_apply_context_view,
    studio_context_modal_view,
    studio_index_view,
)

from .factories import BlockSystemPromptFactory, BlockVariantFactory

pytestmark = pytest.mark.django_db


def _make_request(user=None, query_params=None):
    """Build a GET request with htmx attribute attached."""
    rf = RequestFactory()
    url = "/"
    if query_params:
        url += "?" + query_params.urlencode()
    request = rf.get(url)
    request.htmx = HtmxDetails(request)
    if user:
        request.user = user
    return request


class TestGetStudioForm:
    def test_returns_unbound_when_no_params(self):
        request = _make_request()
        form = _get_studio_form(request)
        assert not form.is_bound

    def test_returns_bound_when_form_field_present(self, system_prompt):
        request = _make_request()
        request.GET = QueryDict(f"system_prompt={system_prompt.pk}")
        form = _get_studio_form(request)
        assert form.is_bound

    def test_returns_unbound_when_only_empty_params(self):
        request = _make_request()
        request.GET = QueryDict("system_prompt=&variant=")
        form = _get_studio_form(request)
        assert not form.is_bound


class TestStudioIndexView:
    @patch("phoxtail.streams.views.render")
    def test_returns_response_for_superuser(self, mock_render, superuser):
        mock_render.return_value = "ok"
        request = _make_request(user=superuser)
        result = studio_index_view(request)
        assert result == "ok"
        _, args, kwargs = mock_render.mock_calls[0]
        assert args[1] == "phoxtail_streams/studio/index.html"
        assert "form" in args[2]
        assert "rendered_prompt" in args[2]

    def test_denies_unpermitted_user(self, user):
        request = _make_request(user=user)
        with pytest.raises(PermissionDenied):
            studio_index_view(request)

    @patch("phoxtail.streams.views.render")
    def test_rendered_prompt_none_for_unbound(self, mock_render, superuser):
        mock_render.return_value = "ok"
        request = _make_request(user=superuser)
        studio_index_view(request)
        context = mock_render.call_args[0][2]
        assert context["rendered_prompt"] is None

    @patch("phoxtail.streams.views.render")
    def test_rendered_prompt_populated_when_valid(self, mock_render, superuser):
        mock_render.return_value = "ok"
        sp = BlockSystemPromptFactory(template="Hello {{ block.name }}")
        v = BlockVariantFactory()
        request = _make_request(user=superuser)
        request.GET = QueryDict(
            f"system_prompt={sp.pk}&variant={v.pk}&collection={v.collection.pk}"
        )
        studio_index_view(request)
        context = mock_render.call_args[0][2]
        assert context["rendered_prompt"] is not None
        assert v.block.name in context["rendered_prompt"]


class TestStudioContextModalView:
    @patch("phoxtail.streams.views.render")
    def test_renders_modal_template(self, mock_render, superuser):
        mock_render.return_value = "ok"
        request = _make_request(user=superuser)
        studio_context_modal_view(request)
        template = mock_render.call_args[0][1]
        assert "modal.html" in template

    def test_denies_unpermitted_user(self, user):
        request = _make_request(user=user)
        with pytest.raises(PermissionDenied):
            studio_context_modal_view(request)


class TestStudioApplyContextView:
    @patch("phoxtail.streams.views.render")
    def test_renders_response_template(self, mock_render, superuser):
        mock_render.return_value = "ok"
        request = _make_request(user=superuser)
        studio_apply_context_view(request)
        template = mock_render.call_args[0][1]
        assert "response.html" in template

    def test_denies_unpermitted_user(self, user):
        request = _make_request(user=user)
        with pytest.raises(PermissionDenied):
            studio_apply_context_view(request)
