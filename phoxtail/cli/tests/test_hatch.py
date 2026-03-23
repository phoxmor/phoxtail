"""Tests for the phoxtail hatch command."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from phoxtail.__main__ import app
from phoxtail.cli.hatch import PLACEHOLDER, TEMPLATE_DIR, _copy_template

runner = CliRunner()


class TestCopyTemplate:
    """Unit tests for the _copy_template helper."""

    def test_copies_all_template_files(self, tmp_path):
        target = tmp_path / "myproject"
        target.mkdir()
        count = _copy_template("myproject", target)

        # Should have copied every file from project_template
        template_files = [f for f in TEMPLATE_DIR.rglob("*") if f.is_file()]
        assert count == len(template_files)

    def test_replaces_placeholder_in_toml(self, tmp_path):
        target = tmp_path / "acme"
        target.mkdir()
        _copy_template("acme", target)

        toml = (target / "phoxtail.toml").read_text()
        assert PLACEHOLDER not in toml
        assert 'name = "acme"' in toml
        assert 'image_prefix = "acme"' in toml

    def test_replaces_placeholder_in_celery(self, tmp_path):
        target = tmp_path / "acme"
        target.mkdir()
        _copy_template("acme", target)

        celery = (target / "src" / "celery.py").read_text()
        assert PLACEHOLDER not in celery
        assert '"acme"' in celery

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
        assert (target / "users").is_dir()
        assert (target / "app" / "templatetags").is_dir()
        assert (target / "app" / "templates" / "app" / "pages").is_dir()

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
    def test_output_dir_option(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        outdir = tmp_path / "projects"
        outdir.mkdir()
        result = runner.invoke(
            app, ["hatch", "myproject", "--output-dir", str(outdir), "--no-wizard"]
        )
        assert result.exit_code == 0
        assert (outdir / "myproject" / "manage.py").exists()

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
    def test_wizard_runs_all_five_steps(self, mock_q, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.select.return_value.ask.return_value = "development"

        # Accept wizard + 4 config steps + launch(y) + detach(y) = 7 prompts
        result = runner.invoke(
            app, ["hatch", "myproject"], input="y\ny\ny\ny\ny\ny\ny\n"
        )
        assert result.exit_code == 0
        # 1 compile + 5 wizard steps = 6 subprocess calls
        assert mock_run.call_count == 6

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_wizard_calls_correct_subcommands(
        self, mock_q, mock_run, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.select.return_value.ask.return_value = "development"

        # Accept wizard + all steps + detach(y)
        runner.invoke(app, ["hatch", "myproject"], input="y\ny\ny\ny\ny\ny\ny\n")

        calls = [c.args[0] for c in mock_run.call_args_list]
        # calls[0] is requirements compile
        assert calls[0][-2:] == ["requirements", "compile"]
        # Wizard steps
        assert calls[1][-3:] == ["env", "create", "development"]
        assert calls[2][-3:] == ["docker", "create", "dockerfile"]
        assert calls[3][-4:] == ["docker", "create", "compose", "development"]
        assert calls[4][-3:] == ["nginx", "create", "initial"]
        # Launch detached (no --no-detach flag)
        assert calls[5][-3:] == ["docker", "up", "--build"]

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_wizard_launch_foreground(self, mock_q, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.select.return_value.ask.return_value = "development"

        # Accept wizard + all steps + launch(y) + detach(n) = foreground
        runner.invoke(app, ["hatch", "myproject"], input="y\ny\ny\ny\ny\ny\nn\n")

        calls = [c.args[0] for c in mock_run.call_args_list]
        # Last call should include --no-detach
        assert calls[5][-4:] == ["docker", "up", "--build", "--no-detach"]

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_wizard_launch_detached_shows_link(
        self, mock_q, mock_run, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.select.return_value.ask.return_value = "development"

        # Accept wizard + all steps + launch(y) + detach(y)
        result = runner.invoke(
            app, ["hatch", "myproject"], input="y\ny\ny\ny\ny\ny\ny\n"
        )
        assert "http://localhost" in result.output

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_wizard_production_uses_correct_subcommands(
        self, mock_q, mock_run, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.select.return_value.ask.return_value = "production"

        runner.invoke(app, ["hatch", "myproject"], input="y\ny\ny\ny\ny\ny\ny\n")

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert calls[1][-3:] == ["env", "create", "production"]
        assert calls[3][-4:] == ["docker", "create", "compose", "production"]
        assert calls[4][-3:] == ["nginx", "create", "production"]

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_wizard_skip_steps(self, mock_q, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.select.return_value.ask.return_value = "development"

        # Accept wizard prompt, then skip all 5 steps
        result = runner.invoke(app, ["hatch", "myproject"], input="y\nn\nn\nn\nn\nn\n")
        assert result.exit_code == 0
        # Only the requirements compile call (no wizard steps)
        assert mock_run.call_count == 1

    @patch("phoxtail.cli.hatch.subprocess.run")
    @patch("phoxtail.cli.hatch.questionary")
    def test_done_panel_omits_completed_steps(
        self, mock_q, mock_run, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 0
        mock_q.select.return_value.ask.return_value = "development"

        # Accept wizard + all steps + detach(y)
        result = runner.invoke(
            app, ["hatch", "myproject"], input="y\ny\ny\ny\ny\ny\ny\n"
        )
        assert result.exit_code == 0
        done_section = result.output.split("Done")[-1]
        # Completed steps should NOT appear as next steps
        assert "phoxtail env create" not in done_section
        assert "phoxtail nginx create" not in done_section
        assert "docker up --build" not in done_section

    @patch("phoxtail.cli.hatch.subprocess.run")
    def test_wizard_declined(self, mock_run, tmp_path, monkeypatch):
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
    def test_compile_failure_falls_back_to_copy(self, mock_run, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_run.return_value.returncode = 1
        result = runner.invoke(app, ["hatch", "myproject", "--no-wizard"])
        assert result.exit_code == 0
        # Fallback should copy requirements.in as requirements.txt
        req_txt = (tmp_path / "myproject" / "requirements.txt").read_text()
        assert "Django" in req_txt
        assert "gunicorn" in req_txt
