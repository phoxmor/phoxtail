"""The shared favicon falls back to phoxtail's symbol until a site sets its own."""

from types import SimpleNamespace

from django.template.loader import render_to_string


def _settings(favicon=None, favicon_dark=None):
    site_setting = SimpleNamespace(favicon=favicon, favicon_dark=favicon_dark)
    return SimpleNamespace(phoxtail_cms=SimpleNamespace(SiteSetting=site_setting))


def test_without_site_favicons_the_symbol_is_offered_for_each_theme():
    html = render_to_string("phoxtail_core/favicon.html", {"settings": _settings()})

    assert "symbol-on-light.svg" in html
    assert "symbol-on-dark.svg" in html
    assert 'media="(prefers-color-scheme: dark)"' in html


def test_one_site_favicon_alone_is_not_enough_to_replace_the_symbol():
    """Both versions are needed, or a theme would be left without an icon."""
    html = render_to_string("phoxtail_core/favicon.html", {"settings": _settings(favicon=object())})

    assert "symbol-on-light.svg" in html
