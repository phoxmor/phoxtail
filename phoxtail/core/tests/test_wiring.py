"""Tests for phoxtail.core.wiring."""

import pytest

from phoxtail.core.wiring import (
    _resolve_dependencies,
    find_phoxtail_config,
    wire_apps,
)

APP_A = "phoxtail.core.tests.wiring_testapps.app_a"
APP_B = "phoxtail.core.tests.wiring_testapps.app_b"
APP_PLAIN = "phoxtail.core.tests.wiring_testapps.app_plain"
APP_CYCLE_A = "phoxtail.core.tests.wiring_testapps.app_cycle_a"
APP_CYCLE_B = "phoxtail.core.tests.wiring_testapps.app_cycle_b"
APP_MISSING = "phoxtail.core.tests.wiring_testapps.app_nope"


def _base_settings():
    return {
        "INSTALLED_APPS": [],
        "TEMPLATES": [
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "OPTIONS": {
                    "context_processors": [
                        "django.template.context_processors.request",
                    ],
                },
            },
        ],
        "MIDDLEWARE": [
            "django.middleware.common.CommonMiddleware",
        ],
    }


class TestFindPhoxtailConfig:
    def test_returns_phoxtail_subclass(self):
        cfg = find_phoxtail_config(APP_A)
        assert cfg is not None
        assert cfg.__name__ == "AppAConfig"

    def test_returns_none_for_plain_appconfig(self):
        assert find_phoxtail_config(APP_PLAIN) is None

    def test_returns_none_for_missing_module(self):
        assert find_phoxtail_config(APP_MISSING) is None


class TestResolveDependencies:
    def test_linear_dependency_is_inserted_before_dependent(self):
        resolved = _resolve_dependencies([APP_B])
        assert resolved == [APP_A, APP_B]

    def test_existing_order_preserved_when_dependency_already_listed(self):
        resolved = _resolve_dependencies([APP_A, APP_B])
        assert resolved == [APP_A, APP_B]

    def test_no_change_for_plain_apps(self):
        resolved = _resolve_dependencies([APP_PLAIN, APP_A])
        assert resolved == [APP_PLAIN, APP_A]

    def test_cycle_raises(self):
        with pytest.raises(ValueError, match="Circular dependency"):
            _resolve_dependencies([APP_CYCLE_A])


class TestWireApps:
    def test_merges_context_processors_without_duplicating(self):
        settings = _base_settings()
        settings["INSTALLED_APPS"] = [APP_A, APP_A]
        wire_apps(settings)
        cps = settings["TEMPLATES"][0]["OPTIONS"]["context_processors"]
        assert cps.count(f"{APP_A}.ctx.proc_a") == 1
        assert cps[0] == "django.template.context_processors.request"

    def test_appends_middleware_without_duplicating(self):
        settings = _base_settings()
        settings["INSTALLED_APPS"] = [APP_A]
        wire_apps(settings)
        mw = settings["MIDDLEWARE"]
        assert mw.count(f"{APP_A}.middleware.MiddlewareA") == 1
        assert mw[0] == "django.middleware.common.CommonMiddleware"

    def test_default_settings_setdefault_user_wins(self):
        settings = _base_settings()
        settings["INSTALLED_APPS"] = [APP_A]
        settings["APP_A_SETTING"] = "user-override"
        wire_apps(settings)
        assert settings["APP_A_SETTING"] == "user-override"

    def test_default_settings_applied_when_absent(self):
        settings = _base_settings()
        settings["INSTALLED_APPS"] = [APP_A]
        wire_apps(settings)
        assert settings["APP_A_SETTING"] == "a-default"

    def test_default_settings_first_wins_across_apps(self):
        settings = _base_settings()
        settings["INSTALLED_APPS"] = [APP_A, APP_B]
        wire_apps(settings)
        assert settings["SHARED_SETTING"] == "from-a"

    def test_plain_appconfigs_skipped_silently(self):
        settings = _base_settings()
        settings["INSTALLED_APPS"] = [APP_PLAIN]
        wire_apps(settings)
        assert settings["INSTALLED_APPS"] == [APP_PLAIN]
        assert settings["TEMPLATES"][0]["OPTIONS"]["context_processors"] == [
            "django.template.context_processors.request"
        ]

    def test_dependencies_expanded_in_installed_apps(self):
        settings = _base_settings()
        settings["INSTALLED_APPS"] = [APP_B]
        wire_apps(settings)
        assert settings["INSTALLED_APPS"] == [APP_A, APP_B]


class TestCollectUrlPatterns:
    """Synthetic app configs — the mechanism, not whichever apps ship with it."""

    @staticmethod
    def _config(url_mount):
        from phoxtail.core.app_config import PhoxtailAppConfig

        config = object.__new__(PhoxtailAppConfig)
        config.url_mount = url_mount
        return config

    @pytest.fixture
    def collect(self, monkeypatch):
        from django.apps import apps

        from phoxtail.core.app_config import UrlMount
        from phoxtail.core.wiring import collect_url_patterns

        def _collect(*mounts):
            configs = [self._config(mount) for mount in mounts]
            monkeypatch.setattr(apps, "get_app_configs", lambda: configs)
            return collect_url_patterns()

        _collect.mount = UrlMount
        return _collect

    @staticmethod
    def _localized(patterns):
        return [p for p in patterns if hasattr(p.pattern, "language_prefix")]

    @staticmethod
    def _plain(patterns):
        return [str(p.pattern) for p in patterns if not hasattr(p.pattern, "language_prefix")]

    def test_i18n_mount_is_language_prefixed(self, collect):
        mount = collect.mount(prefix="shop/", module="phoxtail.core.urls", i18n=True)
        assert self._localized(collect(mount))

    def test_plain_mount_is_not_language_prefixed(self, collect):
        mount = collect.mount(prefix="shop/", module="phoxtail.core.urls")
        patterns = collect(mount)
        assert not self._localized(patterns)
        assert "shop/" in self._plain(patterns)

    def test_set_language_published_alongside_a_localized_mount(self, collect):
        mount = collect.mount(prefix="shop/", module="phoxtail.core.urls", i18n=True)
        assert "i18n/" in self._plain(collect(mount))

    def test_a_plain_mount_stays_out_of_the_localized_group(self, collect):
        plain = collect.mount(prefix="shop/", module="phoxtail.core.urls")
        localized = collect.mount(prefix="dash/", module="phoxtail.core.urls", i18n=True)
        patterns = collect(plain, localized)
        assert "shop/" in self._plain(patterns)
        assert len(self._localized(patterns)) == 1

    def test_no_localized_mount_publishes_no_set_language(self, collect):
        """A project with nothing to translate gets no i18n/ URLs at all."""
        mount = collect.mount(prefix="shop/", module="phoxtail.core.urls")
        assert self._plain(collect(mount)) == ["shop/"]

    def test_no_mounts_at_all(self, collect):
        assert collect() == []
