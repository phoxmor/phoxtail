"""phoxtail server ssl — obtain a TLS certificate and activate HTTPS on a deployed server."""

import socket
import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from phoxtail.cli.server.utils import scp_to, ssh_check, ssh_live
from phoxtail.cli.utils.config import find_config_file, get_project_name, slugify

console = Console()

_DEPLOY_DIR = Path(".phoxtail/deploy")


def _read_deploy_env(key: str) -> str | None:
    """Read a single key from the local .phoxtail/deploy/.env file."""
    env_path = _DEPLOY_DIR / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith(f"{key}="):
            return line[len(key) + 1 :].strip()
    return None


def _dns_resolves_to(domain: str, ip: str) -> bool:
    try:
        return socket.gethostbyname(domain) == ip
    except socket.gaierror:
        return False


def ssl(
    ip: str = typer.Argument(..., help="Server IP address."),
    domain: str | None = typer.Option(
        None,
        "--domain",
        "-d",
        help="Domain name. Reads DOMAIN from .phoxtail/deploy/.env if omitted.",
    ),
    email: str | None = typer.Option(
        None,
        "--email",
        "-e",
        help="Let's Encrypt email. Reads DOMAIN_EMAIL from .phoxtail/deploy/.env if omitted.",
    ),
    user: str = typer.Option("phoxtail", "--user", "-u", help="Deploy username on the server."),
    www: bool = typer.Option(False, "--www", help="Also request a certificate for www.{domain}."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Test the ACME challenge without saving a certificate. Skips nginx and cron steps.",
    ),
    staging: bool = typer.Option(
        False,
        "--staging",
        help="Issue a certificate from Let's Encrypt's test CA. Trusted by nobody, but exercises the full flow.",
    ),
    skip_dns_check: bool = typer.Option(False, "--skip-dns-check", help="Skip DNS resolution verification."),
) -> None:
    """Obtain a TLS certificate and switch nginx to HTTPS.

    Reads DOMAIN and DOMAIN_EMAIL from .phoxtail/deploy/.env automatically,
    so in most cases the command is just:

        phoxtail server ssl 1.2.3.4

    What it does:
    1. Checks SSH + Docker on the server.
    2. Verifies the domain's DNS A record points to <ip>.
    3. Runs certbot HTTP-01 on the server (skipped if cert already exists).
    4. Generates production nginx.conf locally and uploads it.
    5. Reloads nginx inside the running container.
    6. Installs a cron job for automatic renewal (idempotent).

    Re-running is safe — cert issuance and cron installation are both skipped
    if already done.

    Testing flags (use before the real run):

      --dry-run   Asks Let's Encrypt to simulate the HTTP-01 challenge without
                  saving anything. nginx stays on initial.conf. No cleanup needed
                  afterwards. Use this first to confirm your domain is reachable.

      --staging   Runs the full pipeline — real cert issuance, nginx switch,
                  cron — but against Let's Encrypt's test CA, so browsers show
                  a certificate warning. Use this to test the complete flow end-
                  to-end. You must delete the staging cert before issuing a real
                  one (the cert existence check will skip issuance otherwise).

    Examples:
        phoxtail server ssl 1.2.3.4
        phoxtail server ssl 1.2.3.4 --dry-run
        phoxtail server ssl 1.2.3.4 --staging
        phoxtail server ssl 1.2.3.4 --domain example.com
        phoxtail server ssl 1.2.3.4 --skip-dns-check
    """
    if find_config_file() is None:
        console.print("[red]Error:[/red] No phoxtail.toml found. Run this command from a phoxtail project directory.")
        raise typer.Exit(1)

    domain = domain or _read_deploy_env("DOMAIN")
    email = email or _read_deploy_env("DOMAIN_EMAIL")

    if not domain:
        console.print(
            "[red]Error:[/red] Domain is required.\n"
            "  Pass [bold]--domain example.com[/bold] or set DOMAIN in .phoxtail/deploy/.env"
        )
        raise typer.Exit(1)

    if not email:
        console.print(
            "[red]Error:[/red] Email is required.\n"
            "  Pass [bold]--email you@example.com[/bold] or set DOMAIN_EMAIL in .phoxtail/deploy/.env"
        )
        raise typer.Exit(1)

    domain = domain.strip()
    email = email.strip()
    project_slug = slugify(get_project_name())
    project_dir = f"~/{project_slug}"
    cron_dir = f"$HOME/{project_slug}"

    console.print()

    try:
        # ------------------------------------------------------------------
        # 1. SSH connectivity
        # ------------------------------------------------------------------
        with console.status(f"[bold cyan]Connecting to {user}@{ip}...[/bold cyan]"):
            if not ssh_check(user, ip, "echo ok"):
                console.print(f"[red]Cannot connect to {user}@{ip}.[/red]")
                raise typer.Exit(1)
        console.print(f"  [green]✓[/green] Connected to {user}@{ip}")

        # ------------------------------------------------------------------
        # 2. Docker check
        # ------------------------------------------------------------------
        if not ssh_check(user, ip, "command -v docker"):
            console.print("[red]Docker not found on server.[/red]")
            raise typer.Exit(1)
        console.print("  [green]✓[/green] Docker available")

        # ------------------------------------------------------------------
        # 3. DNS check
        # ------------------------------------------------------------------
        names_to_check = [domain] + ([f"www.{domain}"] if www else [])
        if not skip_dns_check:
            for name in names_to_check:
                with console.status(f"  Checking DNS for {name}..."):
                    dns_ok = _dns_resolves_to(name, ip)
                if dns_ok:
                    console.print(f"  [green]✓[/green] DNS: {name} → {ip}")
                else:
                    console.print(
                        f"\n  [red]✗[/red]  DNS check failed: {name} does not resolve to {ip}.\n"
                        "\n"
                        "  Let's Encrypt will reject the HTTP-01 challenge if the A record\n"
                        "  hasn't propagated yet. Wait for DNS, then re-run.\n"
                        "\n"
                        "  To skip this check:  [bold]--skip-dns-check[/bold]"
                    )
                    raise typer.Exit(1)

        # ------------------------------------------------------------------
        # 4. Cert existence check (idempotency — skipped for dry-run)
        # ------------------------------------------------------------------
        cert_path = f"/etc/letsencrypt/live/{domain}/fullchain.pem"
        if not dry_run:
            cert_exists = ssh_check(
                user,
                ip,
                f"cd {project_dir} && docker compose run --rm -T --entrypoint sh certbot -c 'test -f {cert_path}'",
            )
        else:
            cert_exists = False

        if cert_exists:
            console.print(f"  [green]✓[/green] Certificate already exists [dim]({domain})[/dim]")
        else:
            # ------------------------------------------------------------------
            # 5. Obtain / simulate certificate (HTTP-01 webroot)
            # ------------------------------------------------------------------
            extra_flags = ""
            if dry_run:
                extra_flags += " --dry-run"
            elif staging:
                extra_flags += " --staging"
            www_flag = f" -d www.{domain}" if www else ""
            certbot_cmd = (
                f"certonly --webroot --webroot-path /var/www/certbot"
                f" -d {domain}{www_flag}"
                f" --email {email} --agree-tos --no-eff-email"
                f"{extra_flags}"
            )
            if dry_run:
                console.print(f"\n  [bold cyan]→[/bold cyan] Simulating ACME challenge for [bold]{domain}[/bold]")
                console.print("  [dim]Dry run — no certificate will be saved[/dim]")
            else:
                console.print(f"\n  [bold cyan]→[/bold cyan] Obtaining certificate for [bold]{domain}[/bold]")
                if staging:
                    console.print("  [yellow]⚠[/yellow]  Staging mode — certificate will not be trusted by browsers")
            rc = ssh_live(
                user,
                ip,
                f"cd {project_dir} && docker compose run --rm -T certbot {certbot_cmd}",
            )
            if rc != 0:
                console.print("  [red]✗[/red] Certificate issuance failed")
                raise typer.Exit(1)
            if dry_run:
                console.print(f"  [green]✓[/green] ACME challenge simulation passed for {domain}")
                console.print()
                console.print(
                    Panel(
                        "[green]Dry run passed![/green]"
                        "\n\n"
                        "  Let's Encrypt can reach your server and complete the HTTP-01\n"
                        "  challenge. No certificate was saved, nothing to clean up.\n\n"
                        "  Ready for the real run:\n"
                        f"  [cyan]phoxtail server ssl {ip}[/cyan]",
                        border_style="green",
                        expand=False,
                    )
                )
                return
            console.print(f"  [green]✓[/green] Certificate obtained for {domain}")

        # ------------------------------------------------------------------
        # 6. Generate production nginx.conf locally
        # ------------------------------------------------------------------
        _DEPLOY_DIR.mkdir(parents=True, exist_ok=True)
        nginx_local = _DEPLOY_DIR / "nginx.prod.conf"
        console.print("\n  [bold cyan]→[/bold cyan] Generating production nginx.conf")
        rc = subprocess.call(
            [
                "phoxtail",
                "nginx",
                "create",
                "production",
                "--domain",
                domain,
                "--output",
                str(nginx_local),
                "--force",
            ]
        )
        if rc != 0:
            console.print("  [red]✗[/red] Failed to generate production nginx.conf")
            raise typer.Exit(1)
        console.print("  [green]✓[/green] Production nginx.conf generated")

        # ------------------------------------------------------------------
        # 7. Upload nginx.conf to server
        # ------------------------------------------------------------------
        remote_nginx = f"{project_dir}/nginx.conf"
        with console.status("  Uploading nginx.conf..."):
            if not scp_to(user, ip, nginx_local, remote_nginx):
                console.print("  [red]✗[/red] Failed to upload nginx.conf")
                raise typer.Exit(1)
        console.print("  [green]✓[/green] nginx.conf uploaded")

        # ------------------------------------------------------------------
        # 8. Reload nginx
        # ------------------------------------------------------------------
        console.print("\n  [bold cyan]→[/bold cyan] Reloading nginx")
        rc = ssh_live(user, ip, f"cd {project_dir} && docker compose exec -T nginx nginx -s reload")
        if rc != 0:
            console.print("  [red]✗[/red] Nginx reload failed")
            raise typer.Exit(1)
        console.print("  [green]✓[/green] Nginx reloaded")

        # ------------------------------------------------------------------
        # 9. Renewal cron (idempotent — marker comment prevents duplicates)
        # ------------------------------------------------------------------
        cron_marker = f"phoxtail-ssl-{project_slug}"
        renew_cmd = (
            f"cd {cron_dir} && docker compose run --rm -T certbot renew -q"
            f" && docker compose exec -T nginx nginx -s reload"
        )
        cron_entry = f"0 3 1,15 * * {renew_cmd}  # {cron_marker}"

        cron_exists = ssh_check(user, ip, f"crontab -l 2>/dev/null | grep -qF '{cron_marker}'")
        cron_success = False
        if cron_exists:
            console.print("  [green]✓[/green] Renewal cron [dim](already installed)[/dim]")
            cron_success = True
        else:
            install_cron = f"(crontab -l 2>/dev/null; echo '{cron_entry}') | crontab -"
            cron_success = ssh_check(user, ip, install_cron)
            if cron_success:
                console.print("  [green]✓[/green] Renewal cron installed [dim](runs 03:00 on the 1st and 15th)[/dim]")
            else:
                console.print("  [yellow]⚠[/yellow]  Could not install renewal cron — renew manually with:")
                console.print(f"  [dim]{renew_cmd}[/dim]")

        # ------------------------------------------------------------------
        # Done
        # ------------------------------------------------------------------
        console.print()
        renewal_line = (
            "  [dim]Renewal:[/dim]   cron — 03:00 on the 1st and 15th\n"
            if cron_success
            else f"  [dim]Renewal:[/dim]   [yellow]manual[/yellow] — {renew_cmd}\n"
        )
        console.print(
            Panel(
                "[green]HTTPS activated![/green]"
                "\n\n"
                f"  [dim]Site:[/dim]      https://{domain}\n"
                f"  [dim]Cert:[/dim]      /etc/letsencrypt/live/{domain}/\n"
                + renewal_line
                + (
                    "\n  [yellow]Staging cert — run without --staging to issue a trusted cert.[/yellow]"
                    if staging
                    else ""
                ),
                border_style="green",
                expand=False,
            )
        )

    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(0)
