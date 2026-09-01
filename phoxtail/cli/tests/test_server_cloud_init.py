"""Tests for cloud-init bootstrap template rendering and status reporting."""

import subprocess
from unittest.mock import patch

from phoxtail.cli.server.utils import cloud_init_report
from phoxtail.cli.utils.templates import render_template


def _render(deploy_user="phoxtail", ssh_public_keys=None):
    return render_template(
        "cloud_init/bootstrap.yml.j2",
        {
            "deploy_user": deploy_user,
            "ssh_public_keys": ssh_public_keys or ["ssh-ed25519 AAAAC3 user@host"],
        },
    )


class TestBootstrapTemplate:
    def test_starts_with_cloud_config_directive(self):
        output = _render()
        assert output.startswith("#cloud-config")

    def test_deploy_user_is_substituted(self):
        output = _render(deploy_user="mydeployer")
        assert "name: mydeployer" in output
        assert "AllowUsers mydeployer" in output
        assert "usermod -aG docker mydeployer" in output

    def test_ssh_public_keys_are_injected(self):
        keys = [
            "ssh-ed25519 AAAAC3 user@laptop",
            "ssh-ed25519 BBBBB4 user@desktop",
        ]
        output = _render(ssh_public_keys=keys)
        assert "ssh-ed25519 AAAAC3 user@laptop" in output
        assert "ssh-ed25519 BBBBB4 user@desktop" in output

    def test_root_login_is_disabled(self):
        output = _render()
        assert "PermitRootLogin no" in output

    def test_password_auth_is_disabled(self):
        output = _render()
        assert "PasswordAuthentication no" in output

    def test_docker_is_installed(self):
        output = _render()
        assert "get.docker.com" in output
        assert "usermod -aG docker" in output

    def test_uv_is_installed_as_deploy_user(self):
        output = _render()
        assert "astral.sh/uv/install.sh" in output
        # uv installed as deploy user, not root
        assert "su - phoxtail" in output
        assert "/root" not in output
        # The phoxtail CLI is deliberately not installed on the server —
        # deploys drive the server over SSH from the operator's machine.
        assert "uv tool install phoxtail" not in output

    def test_ufw_opens_http_https_ssh(self):
        output = _render()
        assert "ufw allow ssh" in output
        assert "ufw allow 80/tcp" in output
        assert "ufw allow 443/tcp" in output
        assert "ufw --force enable" in output

    def test_fail2ban_is_configured(self):
        output = _render()
        assert "fail2ban" in output
        assert "[sshd]" in output

    def test_no_project_directories_in_cloud_init(self):
        """Project dirs are created by deploy configure, not cloud-init."""
        output = _render()
        assert "db-backups" not in output
        assert "mkdir -p /home" not in output

    def test_unattended_upgrades_configured(self):
        output = _render()
        assert "unattended-upgrades" in output
        assert 'Automatic-Reboot "false"' in output

    def test_valid_yaml_structure(self):
        """Rendered output must be parseable as YAML."""
        import yaml

        output = _render()
        # Strip the #cloud-config line (not valid YAML by itself)
        yaml_body = "\n".join(output.split("\n")[1:])
        parsed = yaml.safe_load(yaml_body)
        assert "users" in parsed
        assert "runcmd" in parsed
        assert "packages" in parsed
        assert "write_files" in parsed
        assert "bootcmd" in parsed

    def test_dpkg_is_unstuck_before_docker_installs(self):
        """A half-configured package fails every later apt-get, Docker's included."""
        output = _render()
        runcmd = output.split("runcmd:", 1)[1]
        # Must precede Docker: the package step above is what breaks dpkg, so
        # clearing it in bootcmd alone would be a no-op on a first boot.
        assert runcmd.index("dpkg --configure -a") < runcmd.index("get.docker.com")

    def test_grub_install_is_declined_only_when_the_device_is_invalid(self):
        output = _render()
        bootcmd = output.split("bootcmd:", 1)[1].split("# Install security", 1)[0]
        # Guarded on the stored value not existing, so a healthy image is
        # untouched and the fix needs no removal when such an image is fixed.
        assert '[ ! -e "$current" ]' in bootcmd
        # Declining beats redirecting: grub-install fails outright on a
        # whole-disk filesystem, which is the layout that ships the bad value.
        assert "grub-pc/install_devices_empty boolean true" in bootcmd
        assert "lsblk" not in bootcmd

    def test_bootstrap_ends_on_a_docker_check(self):
        """cloud-init reports only the last runcmd's status — make it Docker's."""
        import yaml

        parsed = yaml.safe_load("\n".join(_render().split("\n")[1:]))
        assert parsed["runcmd"][-1] == "docker --version"


class TestCloudInitReport:
    def _run(self, stdout, returncode=0, settle=0):
        completed = subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")
        with patch("phoxtail.cli.server.utils.subprocess.run", return_value=completed):
            return cloud_init_report("phoxtail", "203.0.113.1", settle=settle)

    def test_done_is_success(self):
        ok, _ = self._run("status: done\n")
        assert ok

    def test_error_is_failure(self):
        ok, detail = self._run("status: error\nerrors:\n\t- package install failed\n")
        assert not ok
        assert "package install failed" in detail

    def test_degraded_done_is_success_despite_nonzero_exit(self):
        """A warning a provider logs on every boot must not read as failure."""
        ok, _ = self._run("status: done\nextended_status: degraded done\n", returncode=2)
        assert ok

    def test_unreadable_status_is_failure(self):
        ok, _ = self._run("", returncode=255)
        assert not ok

    def test_still_running_is_not_success(self):
        """The sentinel file can land before the status settles."""
        ok, _ = self._run("status: running\n")
        assert not ok

    def test_running_is_repolled_until_it_settles(self):
        completed = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="status: running\n", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="status: done\n", stderr=""),
        ]
        with (
            patch("phoxtail.cli.server.utils.subprocess.run", side_effect=completed),
            patch("phoxtail.cli.server.utils.time.sleep"),
        ):
            ok, _ = cloud_init_report("phoxtail", "203.0.113.1", settle=30)
        assert ok


class TestForgetHostKey:
    def test_drops_the_entry_for_the_given_ip(self):
        from phoxtail.cli.server.utils import forget_host_key

        with patch("phoxtail.cli.server.utils.subprocess.run") as run:
            forget_host_key("203.0.113.1")
        assert run.call_args[0][0] == ["ssh-keygen", "-R", "203.0.113.1"]
