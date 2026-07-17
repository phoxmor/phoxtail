"""Tests for cloud-init bootstrap template rendering."""

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
