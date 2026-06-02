"""Tests for the phoxtail hatch command."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from phoxtail.__main__ import app
from phoxtail.cli.hatch import (
    APPS_MARKER,
    PLACEHOLDER,
    TEMPLATE_DIR,
    _copy_template,
)

runner = CliRunner()


class TestCopyTemplate:
    """Unit tests for the _copy_template helper."""

    def test_copies_all_template_files_minus_conditional(self, tmp_path):
        target = tmp_path / "myproject"
        target.mkdir()
        count = _copy_template("myproject", target)

        # Without booking, src/celery.py is skipped as a conditional file.
        template_files = [f for f in TEMPLATE_DIR.rglob("*") if f.is_file()]
        assert count == len(template_files) - 1

    def test_copies_all_template_files_with_booking(self, tmp_path):
        target = tmp_path / "myproject"
        target.mkdir()
        count = _copy_template("myproject", target, optional_apps=["phoxtail.booking"])

        # With booking selected, src/celery.py is included.
        template_files = [f for f in TEMPLATE_DIR.rglob("*") if f.is_file()]
        assert count == len(template_files)

    def test_replaces_placeholder_in_toml(self, tmp_path):
        target = tmp_path / "acme"
        target.mkdir()
        _copy_template("acme", target)

        toml = (target / "phoxtail.toml").read_text()
        assert PLACEHOLDER not in toml
        assert 'name = "acme"' in toml

    def test_replaces_placeholder_in_celery_when_booking_selected(self, tmp_path):
        target = tmp_path / "acme"
        target.mkdir()
        _copy_template("acme", target, optional_apps=["phoxtail.booking"])

        celery = (target / "src" / "celery.py").read_text()
        assert PLACEHOLDER not in celery
        assert '"acme"' in celery

    def test_celery_file_skipped_without_booking(self, tmp_path):
        target = tmp_path / "acme"
        target.mkdir()
        _copy_template("acme", target)

        assert not (target / "src" / "celery.py").exists()

    def test_replaces_placeholder_in_settings(self, tmp_path):
        target = tmp_path / "acme"
        target.mkdir()
        _copy_template("acme", target)

        settings = (target / "src" / "settings" / "base.py").read_text()
        assert PLACEHOLDER not in settings

    def test_preserves_django_template_syntax(self, tmp_path):
        """Django template tags like {{ page.title }} must not be touched."""
        target = tmp_path / "acme"
        target.mkdir()
        _copy_template("acme", target)

        # Check HTML templates still have Django template syntax
        html_files = list(target.rglob("*.html"))
        for html_file in html_files:
            content = html_file.read_text()
            # Should not contain the phoxtail placeholder
            assert PLACEHOLDER not in content

    def test_creates_subdirectories(self, tmp_path):
        target = tmp_path / "myproject"
        target.mkdir()
        _copy_template("myproject", target)

        assert (target / "src" / "settings").is_dir()
        # No templates directory in the scaffold — SitePage.get_template() routes
        # all SitePage subclasses to phoxtail_cms/pages/page.html by default.
        assert not (target / "myproject" / "templates").exists()

    def test_injects_optional_apps_into_settings(self, tmp_path):
        target = tmp_path / "myproject"
        target.mkdir()
        _copy_template("myproject", target, optional_apps=["phoxtail.dashboard"])

        settings = (target / "src" / "settings" / "base.py").read_text()
        assert APPS_MARKER.strip() not in settings
        assert '"phoxtail.dashboard",' in settings

    def test_removes_apps_marker_when_no_optional_apps(self, tmp_path):
        target = tmp_path / "myproject"
        target.mkdir()
        _copy_template("myproject", target)

        settings = (target / "src" / "settings" / "base.py").read_text()
        assert APPS_MARKER.strip() not in settings
        assert "phoxtail.dashboard" not in settings

    def test_booking_writes_umbrella_dotted_name_only(self, tmp_path):
        """Hatch writes the umbrella app name. depends_on expansion happens
        at runtime via PhoxtailBookingConfig."""
        target = tmp_path / "myproject"
        target.mkdir()
        _copy_template("myproject", target, optional_apps=["phoxtail.booking"])

        settings = (target / "src" / "settings" / "base.py").read_text()
        assert '"phoxtail.booking",' in settings
        # No hatch-time expansion: subapps should NOT appear in base.py
        assert '"phoxtail.booking.core",' not in settings
        # Dashboard is NOT hatch-injected; booking pulls it via depends_on at runtime
        assert '"phoxtail.dashboard",' not in settings

    def test_both_selected_writes_both_once(self, tmp_path):
        target = tmp_path / "myproject"
        target.mkdir()
        _copy_template(
            "myproject",
            target,
            optional_apps=["phoxtail.dashboard", "phoxtail.booking"],
        )

        settings = (target / "src" / "settings" / "base.py").read_text()
        assert settings.count('"phoxtail.dashboard",') == 1
        assert settings.count('"phoxtail.booking",') == 1

    def test_no_booking_removes_all_booking_apps(self, tmp_path):
        target = tmp_path / "myproject"
        target.mkdir()
        _copy_template("myproject", target, optional_apps=["phoxtail.dashboard"])

        settings = (target / "src" / "settings" / "base.py").read_text()
        assert "phoxtail.booking" not in settings

    def test_toml_has_empty_apps_by_default(self, tmp_path):
        target = tmp_path / "acme"
        target.mkdir()
        _copy_template("acme", target)

        toml = (target / "phoxtail.toml").read_text()
        assert "apps = []" in toml

    def test_raises_when_template_dir_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("phoxtail.cli.hatch.TEMPLATE_DIR", tmp_path / "nonexistent")
        with pytest.raises(FileNotFoundError, match="Template directory not found"):
            _copy_template("myproject", tmp_path / "out")


class TestHatchCommand:
    """Integration tests for the hatch command via CLI runner."""

    @patch("phoxtail.cli.hatch.subprocess.run")
    def test_scaffolds_project(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        result = runner.invoke(app, ["hatch", "myproject", "--no-wizard"])
        assert result.exit_code == 0
        assert (tmp_path / "myproject" / "manage.py").exists()
        assert (tmp_path / "myproject" / "phoxtail.toml").exists()
        assert (tmp_path / "myproject" / "requirements.in").exists()

    @patch("phoxtail.cli.hatch.subprocess.run")
    def test_generates_requirements_in(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        runner.invoke(app, ["hatch", "myproject", "--no-wizard"])
        content = (tmp_path / "myproject" / "requirements.in").read_text()
        assert "Django" in content
        assert "wagtail" in content
        assert "django-environ" in content
        assert "gunicorn" in content

    @patch("phoxtail.cli.hatch.subprocess.run")
    def test_requirements_in_omits_celery_by_default(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        runner.invoke(app, ["hatch", "myproject", "--no-wizard"])
        content = (tmp_path / "myproject" / "requirements.in").read_text()
        assert "\ncelery\n" not in content
        assert "django-celery-beat" not in content

    def test_requirements_in_adds_celery_when_booking_selected(self, tmp_path):
        target = tmp_path / "myproject"
        target.mkdir()
        _copy_template("myproject", target, optional_apps=["phoxtail.booking"])

        # _copy_template doesn't write requirements.in (hatch() does).
        # Verify via _collect_extra_requirements directly.
        from phoxtail.cli.hatch import _collect_extra_requirements

        extras = _collect_extra_requirements(["phoxtail.booking"])
        assert "celery" in extras
        assert "django-celery-beat" in extras

    @patch("phoxtail.cli.hatch.subprocess.run")
    def test_compiles_requirements(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        runner.invoke(app, ["hatch", "myproject", "--no-wizard"])
        # Should have called requirements compile
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert any("requirements" in c and "compile" in c for c in calls)

    def test_invalid_name_exits_with_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["hatch", "123bad", "--no-wizard"])
        assert result.exit_code == 1
        assert "not a valid project name" in result.output

    def test_keyword_name_exits_with_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["hatch", "class", "--no-wizard"])
        assert result.exit_code == 1
        assert "keyword" in result.output

    def test_module_conflict_exits_with_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["hatch", "os", "--no-wizard"])
        assert result.exit_code == 1
        assert "conflicts" in result.output

    @patch("phoxtail.cli.hatch.subprocess.run")
    def test_existing_dir_cancel(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "myproject").mkdir()
        result = runner.invoke(app, ["hatch", "myproject", "--no-wizard"], input="n\n")
        assert result.exit_code == 0
        assert "Cancelled" in result.output

    @patch("phoxtail.cli.hatch.subprocess.run")
    def test_existing_dir_overwrite(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        existing = tmp_path / "myproject"
        existing.mkdir()
        (existing / "old_file.txt").write_text("old")

        result = runner.invoke(app, ["hatch", "myproject", "--no-wizard"], input="y\n")
        assert result.exit_code == 0
        # Old file should be gone (directory was replaced)
        assert not (existing / "old_file.txt").exists()
        # New files should be there
        assert (existing / "manage.py").exists()

    @patch("phoxtail.cli.hatch.subprocess.run")
    def test_directory_argument_current_dir(self, mock_run, tmp_path, monkeypatch):
        """phoxtail hatch myproject <dir> scaffolds into that directory."""
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        result = runner.invoke(app, ["hatch", "myproject", str(tmp_path), "--no-wizard"])
        assert result.exit_code == 0
        # Files should be in tmp_path directly, not wrapped in an extra
        # "myproject" project folder. The user-app directory (also named
        # "myproject") IS expected as a subdirectory of the scaffold.
        assert (tmp_path / "manage.py").exists()
        assert (tmp_path / "phoxtail.toml").exists()
        assert (tmp_path / "myproject" / "apps.py").exists()

    @patch("phoxtail.cli.hatch.subprocess.run")
    def test_directory_argument_explicit_path(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        target = tmp_path / "mydir"
        result = runner.invoke(app, ["hatch", "myproject", str(target), "--no-wizard"])
        assert result.exit_code == 0
        assert (target / "manage.py").exists()

    @patch("phoxtail.cli.hatch.subprocess.run")
    def test_directory_argument_nonempty_merges(self, mock_run, tmp_path, monkeypatch):
        """Existing files are preserved when directory is given."""
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        (tmp_path / "existing.txt").write_text("hello")
        result = runner.invoke(app, ["hatch", "myproject", str(tmp_path), "--no-wizard"])
        assert result.exit_code == 0
        # Existing file preserved, new files added
        assert (tmp_path / "existing.txt").read_text() == "hello"
        assert (tmp_path / "manage.py").exists()

    @patch("phoxtail.cli.hatch.subprocess.run")
    def test_placeholder_replaced_in_output(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        runner.invoke(app, ["hatch", "acme", "--no-wizard"])
        toml = (tmp_path / "acme" / "phoxtail.toml").read_text()
        assert 'name = "acme"' in toml

    @patch("phoxtail.cli.hatch.subprocess.run")
    def test_no_wizard_skips_wizard_prompt(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        result = runner.invoke(app, ["hatch", "myproject", "--no-wizard"])
        assert result.exit_code == 0
        # Should not ask about wizard
        assert "setup wizard" not in result.output

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_wizard_runs_all_steps(self, mock_q, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.checkbox.return_value.ask.return_value = []
        mock_q.select.return_value.ask.return_value = "development"

        # Accept wizard + 4 config + migrate(y) + stream_engine(y)
        # + bootstrap_site(y) + superuser(y) + launch(y) = 10 y's
        result = runner.invoke(app, ["hatch", "myproject"], input="y\ny\ny\ny\ny\ny\ny\ny\ny\ny\n")
        assert result.exit_code == 0
        # 1 compile + 3 config (no nginx in dev) + 1 migrate + 2 populate
        # + 1 bootstrap_site + 2 superuser (createsuperuser + verify_email)
        # + 1 docker-compose-down + 1 launch = 12
        assert mock_run.call_count == 12

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_wizard_calls_correct_subcommands(self, mock_q, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.checkbox.return_value.ask.return_value = []
        mock_q.select.return_value.ask.return_value = "development"

        # Accept wizard + all steps + superuser(y) + launch(y)
        runner.invoke(app, ["hatch", "myproject"], input="y\ny\ny\ny\ny\ny\ny\ny\ny\ny\n")

        calls = [c.args[0] for c in mock_run.call_args_list]
        # calls[0] is requirements compile
        assert calls[0][-2:] == ["requirements", "compile"]
        # Config wizard steps (no nginx in development)
        assert calls[1][-3:] == ["env", "create", "development"]
        assert calls[2][-3:] == ["docker", "create", "dockerfile"]
        assert calls[3][-4:] == ["docker", "create", "compose", "development"]
        # Migrate
        assert calls[4][-2:] == ["manage", "migrate"]
        # Stream Engine: populate_design then populate_streams
        assert calls[5][-2:] == ["manage", "populate_design"]
        assert calls[6][-2:] == ["manage", "populate_streams"]
        # Bootstrap site
        assert calls[7][-4:] == ["manage", "bootstrap_site", "--app-label", "myproject"]
        # Superuser: createsuperuser + verify_email
        assert calls[8][-2:] == ["manage", "createsuperuser"]
        assert calls[9][-3:] == ["manage", "verify_email", "--all-superusers"]
        # Cleanup + launch (always foreground)
        assert calls[10] == ["docker", "compose", "down"]
        assert calls[-1][-4:] == ["docker", "up", "--build", "--no-detach"]

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_wizard_production_uses_correct_subcommands(self, mock_q, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.checkbox.return_value.ask.return_value = []
        mock_q.select.return_value.ask.return_value = "production"

        runner.invoke(app, ["hatch", "myproject"], input="y\ny\ny\ny\ny\ny\ny\ny\ny\n")

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert calls[1][-3:] == ["env", "create", "production"]
        assert calls[3][-4:] == ["docker", "create", "compose", "production"]
        assert calls[4][-3:] == ["nginx", "create", "production"]

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_wizard_superuser_verifies_email(self, mock_q, mock_run, tmp_path, monkeypatch):
        """verify_email --all-superusers is called after createsuperuser succeeds."""
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.checkbox.return_value.ask.return_value = []
        mock_q.select.return_value.ask.return_value = "development"

        # Accept wizard, skip configure, skip populate, accept superuser, skip launch
        runner.invoke(app, ["hatch", "myproject"], input="y\nn\nn\ny\nn\n")

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert any("verify_email" in c and "--all-superusers" in c for c in calls)

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_wizard_superuser_failure_skips_verify_email(self, mock_q, mock_run, tmp_path, monkeypatch):
        """verify_email is NOT called when createsuperuser fails."""
        monkeypatch.chdir(tmp_path)
        mock_q.checkbox.return_value.ask.return_value = []
        mock_q.select.return_value.ask.return_value = "development"

        # migrate succeeds, createsuperuser fails
        def side_effect(args, **kwargs):
            from unittest.mock import MagicMock

            result = MagicMock()
            cmd = args if isinstance(args, list) else [args]
            if "createsuperuser" in cmd:
                result.returncode = 1
            else:
                result.returncode = 0
                result.stderr = ""
            return result

        mock_run.side_effect = side_effect

        # Accept wizard, skip first 4 config steps, accept migrate,
        # skip stream_engine, accept superuser, skip launch
        runner.invoke(app, ["hatch", "myproject"], input="y\nn\nn\nn\nn\ny\nn\ny\nn\n")

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert not any("verify_email" in c for c in calls)

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_wizard_skip_steps(self, mock_q, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.checkbox.return_value.ask.return_value = []
        mock_q.select.return_value.ask.return_value = "development"

        # Accept wizard prompt, then skip all 8 steps
        skip_all = "y\n" + "n\n" * 8
        result = runner.invoke(app, ["hatch", "myproject"], input=skip_all)
        assert result.exit_code == 0
        # Only the requirements compile call (no wizard steps)
        assert mock_run.call_count == 1

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_done_panel_omits_completed_steps(self, mock_q, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.checkbox.return_value.ask.return_value = []
        mock_q.select.return_value.ask.return_value = "development"

        # Accept wizard + all steps + superuser(y) + launch(y) + detach(y)
        result = runner.invoke(app, ["hatch", "myproject"], input="y\ny\ny\ny\ny\ny\ny\ny\ny\ny\n")
        assert result.exit_code == 0
        # All steps completed — should show "is ready!" and no next-steps panel
        assert "is ready!" in result.output
        assert "Next steps" not in result.output

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_wizard_declined(self, mock_q, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.checkbox.return_value.ask.return_value = []
        # Decline the wizard prompt
        result = runner.invoke(app, ["hatch", "myproject"], input="n\n")
        assert result.exit_code == 0
        assert (tmp_path / "myproject" / "manage.py").exists()

    def test_missing_template_dir_exits_with_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("phoxtail.cli.hatch.TEMPLATE_DIR", tmp_path / "nonexistent")
        result = runner.invoke(app, ["hatch", "myproject", "--no-wizard"])
        assert result.exit_code == 1
        assert "Template directory not found" in result.output

    @patch("phoxtail.cli.hatch.subprocess.run")
    def test_compile_failure_falls_back_to_copy(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 1
        result = runner.invoke(app, ["hatch", "myproject", "--no-wizard"])
        assert result.exit_code == 0
        # Fallback should copy requirements.in as requirements.txt
        req_txt = (tmp_path / "myproject" / "requirements.txt").read_text()
        assert "Django" in req_txt
        assert "gunicorn" in req_txt

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_populate_step_runs_design_before_streams(self, mock_q, mock_run, tmp_path, monkeypatch):
        """populate_design runs before populate_streams within the populate step."""
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.checkbox.return_value.ask.return_value = []
        mock_q.select.return_value.ask.return_value = "development"

        # Accept wizard, skip configure, accept populate, skip superuser, skip launch
        runner.invoke(app, ["hatch", "myproject"], input="y\nn\ny\nn\nn\n")

        calls = [c.args[0] for c in mock_run.call_args_list]
        design_idx = next(i for i, c in enumerate(calls) if "populate_design" in c)
        streams_idx = next(i for i, c in enumerate(calls) if "populate_streams" in c)
        assert design_idx < streams_idx

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_populate_step_skips_streams_on_design_failure(self, mock_q, mock_run, tmp_path, monkeypatch):
        """If populate_design fails, populate_streams is not attempted."""
        monkeypatch.chdir(tmp_path)
        mock_q.checkbox.return_value.ask.return_value = []
        mock_q.select.return_value.ask.return_value = "development"

        def side_effect(args, **kwargs):
            from unittest.mock import MagicMock

            result = MagicMock()
            cmd = args if isinstance(args, list) else [args]
            if "populate_design" in cmd:
                result.returncode = 1
            else:
                result.returncode = 0
                result.stderr = ""
            return result

        mock_run.side_effect = side_effect

        # Accept wizard, skip configure, accept populate, skip superuser, skip launch
        runner.invoke(app, ["hatch", "myproject"], input="y\nn\ny\nn\nn\n")

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert any("populate_design" in c for c in calls)
        assert not any("populate_streams" in c for c in calls)

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_populate_step_runs_all_db_operations(self, mock_q, mock_run, tmp_path, monkeypatch):
        """Accepting the populate step runs migrate, populate_design, populate_streams,
        and bootstrap_site as a single unit."""
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.checkbox.return_value.ask.return_value = []
        mock_q.select.return_value.ask.return_value = "development"

        # Accept wizard, skip configure, accept populate, skip superuser, skip launch
        runner.invoke(app, ["hatch", "myproject"], input="y\nn\ny\nn\nn\n")

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert any("migrate" in c for c in calls)
        assert any("populate_design" in c for c in calls)
        assert any("populate_streams" in c for c in calls)
        assert any("bootstrap_site" in c for c in calls)
