"""Tests for the phoxtail hatch command."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from phoxtail.__main__ import app
from phoxtail.cli.hatch import (
    INSTALL_MARKER,
    PLACEHOLDER,
    TEMPLATE_DIR,
    _copy_template,
)

runner = CliRunner()


class TestCopyTemplate:
    """Unit tests for the _copy_template helper."""

    def test_copies_all_template_files(self, tmp_path):
        target = tmp_path / "myproject"
        target.mkdir()
        count = _copy_template("myproject", target)

        template_files = [f for f in TEMPLATE_DIR.rglob("*") if f.is_file()]
        assert count == len(template_files)

    def test_replaces_placeholder_in_toml(self, tmp_path):
        target = tmp_path / "acme"
        target.mkdir()
        _copy_template("acme", target)

        toml = (target / "phoxtail.toml").read_text()
        assert PLACEHOLDER not in toml
        assert 'name = "acme"' in toml

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

    def test_dashboard_always_in_settings(self, tmp_path):
        target = tmp_path / "myproject"
        target.mkdir()
        _copy_template("myproject", target)

        settings = (target / "src" / "settings" / "base.py").read_text()
        assert '"phoxtail.dashboard",' in settings

    def test_install_marker_present_in_settings(self, tmp_path):
        target = tmp_path / "myproject"
        target.mkdir()
        _copy_template("myproject", target)

        settings = (target / "src" / "settings" / "base.py").read_text()
        assert INSTALL_MARKER.strip() in settings
        assert "{{ phoxtail_optional_apps }}" not in settings

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
        assert (tmp_path / "myproject" / "pyproject.toml").exists()

    @patch("phoxtail.cli.hatch.subprocess.run")
    def test_generates_pyproject_toml(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        runner.invoke(app, ["hatch", "myproject", "--no-wizard"])
        content = (tmp_path / "myproject" / "pyproject.toml").read_text()
        assert "django-environ" in content
        assert "gunicorn" in content

    @patch("phoxtail.cli.hatch.subprocess.run")
    def test_locks_dependencies(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        runner.invoke(app, ["hatch", "myproject", "--no-wizard"])
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert any("uv" in c and "lock" in c for c in calls)

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
        mock_q.select.return_value.ask.return_value = "development"

        # Accept wizard + all prompted steps (attach is not offered: the mocked
        # subprocess never writes the config files it requires)
        result = runner.invoke(app, ["hatch", "myproject"], input="y\ny\ny\ny\ny\n")
        assert result.exit_code == 0
        # 1 uv lock + 3 config (no nginx in dev) + 1 migrate
        # + 2 superuser (createsuperuser + verify_email) + 1 compose-down + 1 launch = 9
        assert mock_run.call_count == 9

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_wizard_calls_correct_subcommands(self, mock_q, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.select.return_value.ask.return_value = "development"

        runner.invoke(app, ["hatch", "myproject"], input="y\ny\ny\ny\ny\n")

        calls = [c.args[0] for c in mock_run.call_args_list]
        # calls[0] is uv lock
        assert calls[0] == ["uv", "lock"]
        # Config wizard steps (no nginx in development)
        assert calls[1][-3:] == ["env", "create", "development"]
        assert calls[2][-3:] == ["docker", "create", "dockerfile"]
        assert calls[3][-4:] == ["docker", "create", "compose", "development"]
        # Migrate
        assert calls[4][-2:] == ["manage", "migrate"]
        # Superuser: createsuperuser + verify_email
        assert calls[5][-2:] == ["manage", "createsuperuser"]
        assert calls[6][-3:] == ["manage", "verify_email", "--all-superusers"]
        # Cleanup + launch
        assert calls[7] == ["docker", "compose", "down"]
        assert calls[8][-3:] == ["docker", "up", "--build"]

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_wizard_attaches_to_net_when_accepted(self, mock_q, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_q.select.return_value.ask.return_value = "development"

        target = tmp_path / "myproject"

        # The attach step is gated on the config files existing, so the mock
        # has to actually produce them the way `env`/`docker create` would.
        def side_effect(args, **kwargs):
            from unittest.mock import MagicMock

            cmd = args if isinstance(args, list) else [args]
            if cmd[-3:] == ["env", "create", "development"]:
                (target / ".env").write_text("DJANGO_ENV=development\n")
            elif cmd[-4:] == ["docker", "create", "compose", "development"]:
                (target / "docker-compose.yaml").write_text("services:\n  web: {}\n")
            result = MagicMock()
            result.returncode = 0
            return result

        mock_run.side_effect = side_effect

        # Accept wizard + configure + network, skip database/superuser/launch
        runner.invoke(app, ["hatch", "myproject"], input="y\ny\ny\nn\nn\nn\n")

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert any(c[-2:] == ["net", "attach"] for c in calls)

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_net_attach_not_offered_without_config(self, mock_q, mock_run, tmp_path, monkeypatch):
        """Skipping config must skip attach: `net attach` would write a COMPOSE_FILE
        naming a docker-compose.yaml that was never generated."""
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.select.return_value.ask.return_value = "development"

        # Decline config; the attach prompt must not appear, so the next "y"
        # is consumed by the database step rather than by attach.
        runner.invoke(app, ["hatch", "myproject"], input="y\nn\ny\nn\nn\n")

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert not any(c[-2:] == ["net", "attach"] for c in calls)
        # The "y" landed on the database step, proving no prompt was consumed.
        assert any(c[-2:] == ["manage", "migrate"] for c in calls)

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_wizard_production_uses_correct_subcommands(self, mock_q, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.select.return_value.ask.return_value = "production"

        runner.invoke(app, ["hatch", "myproject"], input="y\ny\ny\ny\ny\n")

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
        mock_q.select.return_value.ask.return_value = "development"

        # Accept wizard, skip configure, skip database, accept superuser, skip launch
        runner.invoke(app, ["hatch", "myproject"], input="y\nn\nn\ny\nn\n")

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert any("verify_email" in c and "--all-superusers" in c for c in calls)

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_wizard_superuser_failure_skips_verify_email(self, mock_q, mock_run, tmp_path, monkeypatch):
        """verify_email is NOT called when createsuperuser fails."""
        monkeypatch.chdir(tmp_path)
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

        # Accept wizard, skip configure, skip database, accept superuser, skip launch
        runner.invoke(app, ["hatch", "myproject"], input="y\nn\nn\nn\ny\nn\n")

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert not any("verify_email" in c for c in calls)

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_wizard_skip_steps(self, mock_q, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.select.return_value.ask.return_value = "development"

        # Accept wizard prompt, then skip all 4 prompted steps (attach not offered)
        skip_all = "y\n" + "n\n" * 4
        result = runner.invoke(app, ["hatch", "myproject"], input=skip_all)
        assert result.exit_code == 0
        # Only the uv lock call (no wizard steps)
        assert mock_run.call_count == 1

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_done_panel_omits_completed_steps(self, mock_q, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.select.return_value.ask.return_value = "development"

        # Accept wizard + all 4 prompted steps
        result = runner.invoke(app, ["hatch", "myproject"], input="y\ny\ny\ny\ny\n")
        assert result.exit_code == 0
        # All steps completed — should show "is ready!" and no next-steps panel
        assert "is ready!" in result.output
        assert "Next steps" not in result.output

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_wizard_declined(self, mock_q, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
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
    def test_lock_failure_still_scaffolds(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 1
        result = runner.invoke(app, ["hatch", "myproject", "--no-wizard"])
        assert result.exit_code == 0
        # Project is still fully scaffolded even if uv lock fails
        assert (tmp_path / "myproject" / "pyproject.toml").exists()
        assert (tmp_path / "myproject" / "manage.py").exists()
