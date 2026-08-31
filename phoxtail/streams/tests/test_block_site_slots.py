"""Site-wide slot blocks: the site provides the block by default; a page
that places the block itself takes over."""

from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError
from django.template import Context, Template
from django.test import RequestFactory
from wagtail.models import Locale, Site

from phoxtail.streams.cache import (
    get_blocks_for_site_slot,
    get_dynamic_block_instance,
    get_shared_block,
)
from phoxtail.streams.constants import BlockSiteSlot
from phoxtail.streams.models import SharedBlock

from .factories import BlockFactory, BlockVariantFactory

pytestmark = pytest.mark.django_db

TITLE_SCHEMA = [{"type": "char_field", "value": {"name": "title"}}]


def make_site_wide_block(identifier="navbar", slot="before_content", html="<nav>{{ value.title }}</nav>", **kwargs):
    block = BlockFactory(
        identifier=identifier,
        is_shared=True,
        site_slot=slot,
        schema=TITLE_SCHEMA,
        **kwargs,
    )
    BlockVariantFactory(block=block, collection=None, is_default=True, html=html)
    return block


def fill_shared_content(block, title="Hello", variant=None, locale=None):
    return SharedBlock.objects.create(
        block=block,
        site=Site.objects.get(is_default_site=True),
        locale=locale or Locale.get_default(),
        variant=variant,
        content=[{"type": block.identifier, "value": {"title": title}, "id": "t"}],
    )


def render_slot(slot, page=None, request=None, **extra):
    request = request or RequestFactory().get("/")
    template = Template('{% load phoxtail_cms_tags %}{% block_site_slot "' + slot + '" %}')
    return template.render(Context({"request": request, "page": page, **extra}))


class TestModelValidation:
    def test_site_slot_requires_is_shared(self):
        block = BlockFactory(is_shared=False, site_slot="head_start")
        with pytest.raises(ValidationError) as exc_info:
            block.clean()
        assert "site_slot" in exc_info.value.message_dict

    def test_shared_block_variant_must_belong_to_block(self):
        block = make_site_wide_block()
        stranger = BlockVariantFactory()
        row = fill_shared_content(block)
        row.variant = stranger
        with pytest.raises(ValidationError) as exc_info:
            row.clean()
        assert "variant" in exc_info.value.message_dict


class TestSlotLookup:
    def test_slot_order_wins_over_chooser_order(self):
        second = make_site_wide_block(identifier="cookiebot", slot="head_start", sort_order=0)
        first = make_site_wide_block(identifier="gtm", slot="head_start", sort_order=99)
        second.slot_order = 2
        second.save()
        first.slot_order = 1
        first.save()
        assert [b.identifier for b in get_blocks_for_site_slot("head_start")] == ["gtm", "cookiebot"]

    def test_locale_fallback_to_default(self):
        block = make_site_wide_block()
        row = fill_shared_content(block)
        el = Locale.objects.create(language_code="el")
        site = Site.objects.get(is_default_site=True)
        assert get_shared_block(block.identifier, site, el) == row

    def test_locale_row_beats_fallback(self):
        block = make_site_wide_block()
        fill_shared_content(block, title="english")
        el = Locale.objects.create(language_code="el")
        el_row = fill_shared_content(block, title="greek", locale=el)
        site = Site.objects.get(is_default_site=True)
        assert get_shared_block(block.identifier, site, el) == el_row


class TestSiteSlotTag:
    def test_renders_shared_content_in_addressable_wrapper(self):
        block = make_site_wide_block()
        row = fill_shared_content(block, title="Hello")
        html = render_slot("before_content")
        assert "<nav>Hello</nav>" in html
        assert f'data-phoxtail-bar-shared-block-id="{row.pk}"' in html

    def test_head_slot_renders_bare(self):
        block = make_site_wide_block(identifier="gtm", slot="head_start", html="<script>gtm()</script>")
        fill_shared_content(block)
        html = render_slot("head_start")
        assert "<script>gtm()</script>" in html
        assert "data-phoxtail-bar" not in html

    def test_no_shared_row_renders_nothing(self):
        make_site_wide_block()
        assert render_slot("before_content") == ""

    def test_page_placing_the_block_takes_over(self):
        block = make_site_wide_block()
        fill_shared_content(block)
        page = SimpleNamespace(
            locale=Locale.get_default(),
            body=[SimpleNamespace(block_type=block.identifier)],
        )
        assert render_slot("before_content", page=page) == ""

    def test_site_variant_beats_default_variant(self):
        block = make_site_wide_block(html="<nav>default</nav>")
        site_variant = BlockVariantFactory(block=block, collection=None, html="<nav>site</nav>")
        fill_shared_content(block, variant=site_variant)
        assert "<nav>site</nav>" in render_slot("before_content")

    def test_render_in_preview_guard(self):
        block = make_site_wide_block(identifier="gtm", slot="head_start", render_in_preview=False)
        fill_shared_content(block)
        assert render_slot("head_start", phoxtail_screenshot_mode=True) == ""
        assert render_slot("head_start") != ""

    def test_hidden_toggle_suppresses_in_place_render(self):
        block = make_site_wide_block()
        fill_shared_content(block)
        request = RequestFactory().get("/")
        ref = get_dynamic_block_instance(block.identifier)
        assert ref.render({"hidden": True}, {"request": request}) == ""
        assert "<nav>" in ref.render({}, {"request": request})

    def test_preview_panel_guard(self):
        block = make_site_wide_block(identifier="gtm", slot="head_start", render_in_preview=False)
        fill_shared_content(block)
        request = RequestFactory().get("/")
        request.in_preview_panel = True
        assert render_slot("head_start", request=request) == ""

    def test_blocks_render_in_slot_order(self):
        gtm = make_site_wide_block(identifier="gtm", slot="head_start", html="<script>gtm()</script>")
        cookiebot = make_site_wide_block(identifier="cookiebot", slot="head_start", html="<script>cookiebot()</script>")
        gtm.slot_order = 1
        gtm.save()
        cookiebot.slot_order = 2
        cookiebot.save()
        fill_shared_content(gtm)
        fill_shared_content(cookiebot)
        html = render_slot("head_start")
        assert html.index("gtm()") < html.index("cookiebot()")

    def test_page_type_restriction_scopes_injection(self):
        from django.contrib.contenttypes.models import ContentType

        allowed_ct, other_ct = ContentType.objects.order_by("pk")[:2]
        block = make_site_wide_block()
        block.page_types.set([allowed_ct])
        fill_shared_content(block, title="Scoped")

        def page_of(ct):
            return SimpleNamespace(locale=Locale.get_default(), body=[], content_type_id=ct.pk)

        assert "<nav>Scoped</nav>" in render_slot("before_content", page=page_of(allowed_ct))
        assert render_slot("before_content", page=page_of(other_ct)) == ""
        assert render_slot("before_content") == ""  # no page at all

    def test_page_variant_beats_site_variant(self):
        block = make_site_wide_block(html="<nav>default</nav>")
        site_variant = BlockVariantFactory(block=block, collection=None, html="<nav>site</nav>")
        page_variant = BlockVariantFactory(block=block, collection=None, html="<nav>page</nav>")
        fill_shared_content(block, variant=site_variant)
        request = RequestFactory().get("/")
        ref = get_dynamic_block_instance(block.identifier)
        assert "<nav>page</nav>" in ref.render({"variant": page_variant}, {"request": request})
        assert "<nav>site</nav>" in ref.render({}, {"request": request})


class TestPlainSharedBlocksUnchanged:
    """Shared blocks without a site_slot keep today's per-page behavior."""

    def test_no_hidden_toggle_without_slot(self):
        slotless = make_site_wide_block(identifier="promo", slot="")
        slotted = make_site_wide_block(identifier="navbar")
        assert "hidden" not in get_dynamic_block_instance(slotless.identifier).child_blocks
        assert "hidden" in get_dynamic_block_instance(slotted.identifier).child_blocks

    def test_per_page_render_still_resolves_shared_content(self):
        block = make_site_wide_block(identifier="promo", slot="")
        fill_shared_content(block, title="World")
        request = RequestFactory().get("/")
        ref = get_dynamic_block_instance(block.identifier)
        assert "<nav>World</nav>" in ref.render({}, {"request": request})

    def test_slotless_block_never_injected(self):
        block = make_site_wide_block(identifier="promo", slot="")
        fill_shared_content(block)
        for slot, _label in BlockSiteSlot.choices:
            assert render_slot(slot) == ""


class TestSharedBlockFragmentEndpoint:
    def test_renders_addressable_fragment(self, superuser):
        from phoxtail.agent.views import render_shared_block_fragment

        block = make_site_wide_block()
        row = fill_shared_content(block, title="Hello")
        request = RequestFactory().get("/")
        request.user = superuser
        response = render_shared_block_fragment(request, shared_block_id=row.pk)
        assert response.status_code == 200
        html = response.content.decode()
        assert "<nav>Hello</nav>" in html
        assert f'data-phoxtail-bar-shared-block-id="{row.pk}"' in html

    def test_missing_row_raises_404(self, superuser):
        from django.http import Http404

        from phoxtail.agent.views import render_shared_block_fragment

        request = RequestFactory().get("/")
        request.user = superuser
        with pytest.raises(Http404):
            render_shared_block_fragment(request, shared_block_id=987654)
