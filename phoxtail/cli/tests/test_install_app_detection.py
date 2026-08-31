"""Tests for how `phoxtail install` decides what belongs in INSTALLED_APPS."""

from pathlib import Path
from unittest.mock import patch

from phoxtail.cli.install import _confirm_installed_app, _detect_app_info

APP_CONFIG = "class TaggitConfig(AppConfig):\n    name = 'taggit'\n    label = 'taggit'\n"


def _site_packages() -> Path:
    path = Path(".venv/lib/python3.11/site-packages")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _install(module: str, *, files: dict[str, str] | None = None, distribution: str | None = None) -> None:
    """Fake a wheel unpacked into the project's .venv."""
    package = _site_packages() / module
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("")
    for name, content in (files or {}).items():
        (package / name).write_text(content)
    if distribution is not None:
        dist_info = _site_packages() / f"{distribution}-1.0.dist-info"
        dist_info.mkdir(parents=True, exist_ok=True)
        (dist_info / "top_level.txt").write_text(f"{module}\n")


class TestDetectAppInfo:
    def test_plain_library_is_not_registered(self):
        """Importable is not the same as being a Django app."""
        _install("httpx")
        assert _detect_app_info("httpx") == (None, None)

    def test_app_with_an_appconfig_is_registered(self):
        _install("taggit", files={"apps.py": APP_CONFIG})
        assert _detect_app_info("taggit") == ("taggit", "taggit")

    def test_module_name_is_read_from_the_distribution_metadata(self):
        """django-taggit installs `taggit`; guessing from the name finds nothing."""
        _install("taggit", files={"apps.py": APP_CONFIG}, distribution="django_taggit")
        assert _detect_app_info("django-taggit") == ("taggit", "taggit")

    def test_module_name_falls_back_to_the_record_manifest(self):
        """hatchling- and flit-built wheels ship no top_level.txt."""
        _install("corsheaders", files={"apps.py": "class C(AppConfig):\n    name = 'corsheaders'\n"})
        dist_info = _site_packages() / "django_cors_headers-1.0.dist-info"
        dist_info.mkdir(parents=True)
        (dist_info / "RECORD").write_text(
            "../../../bin/some-script,,\n"
            "django_cors_headers-1.0.dist-info/METADATA,sha256=abc,10\n"
            "corsheaders/__init__.py,sha256=abc,0\n"
            "corsheaders/apps.py,sha256=abc,10\n"
        )
        assert _detect_app_info("django-cors-headers") == ("corsheaders", "corsheaders")

    def test_legacy_app_without_apps_py_is_registered(self):
        _install("oldapp", files={"models.py": ""})
        assert _detect_app_info("oldapp") == ("oldapp", "oldapp")

    def test_label_falls_back_to_the_last_segment_of_name(self):
        _install("nested", files={"apps.py": "class C(AppConfig):\n    name = 'a.b.nested'\n"})
        assert _detect_app_info("nested") == ("nested", "nested")

    def test_package_that_is_not_installed(self):
        _site_packages()
        assert _detect_app_info("absent") == (None, None)


class TestConfirmInstalledApp:
    """Detection suggests; the person installing decides."""

    def test_flag_answers_without_prompting(self):
        assert _confirm_installed_app("django-taggit", None, app="taggit", no_app=False) == "taggit"

    def test_no_app_flag_wins_over_detection(self):
        assert _confirm_installed_app("wagtail", "wagtail", app=None, no_app=True) is None

    def test_non_interactive_run_falls_back_to_detection(self):
        with patch("phoxtail.cli.install.sys.stdin.isatty", return_value=False):
            assert _confirm_installed_app("wagtail", "wagtail", app=None, no_app=False) == "wagtail"

    def test_declining_a_detected_app_leaves_it_out(self):
        with patch("phoxtail.cli.install.sys.stdin.isatty", return_value=True):
            with patch("phoxtail.cli.install.Confirm.ask", return_value=False):
                assert _confirm_installed_app("wagtail", "wagtail", app=None, no_app=False) is None

    def test_an_undetected_app_can_still_be_registered_by_hand(self):
        """A package can be a Django app with none of the tell-tale files."""
        with patch("phoxtail.cli.install.sys.stdin.isatty", return_value=True):
            with patch("phoxtail.cli.install.Confirm.ask", return_value=True):
                with patch("phoxtail.cli.install.Prompt.ask", return_value="widget_tweaks"):
                    got = _confirm_installed_app("django-widget-tweaks", None, app=None, no_app=False)
        assert got == "widget_tweaks"
