"""SSL certificate management commands."""

import subprocess
import sys

import typer
from rich.console import Console

from phoxtail.cli.utils.docker import docker_env
from phoxtail.cli.utils.env import read_env_value

app = typer.Typer()
console = Console()


@app.command()
def obtain(
    wildcard: bool = typer.Option(
        False,
        "--wildcard",
        "-w",
        help="Obtain a wildcard certificate (requires DNS-01 challenge)",
    ),
) -> None:
    """Obtain SSL certificates via Let's Encrypt.

    Reads DOMAIN and DOMAIN_EMAIL from .env.
    Standard certificates use HTTP-01 (webroot) challenge.
    Wildcard certificates use DNS-01 (manual) challenge.

    Examples:
        phoxtail ssl obtain
        phoxtail ssl obtain --wildcard
    """
    domain = read_env_value("DOMAIN")
    email = read_env_value("DOMAIN_EMAIL")

    if not domain or not email:
        console.print("[red]Error:[/red] DOMAIN and DOMAIN_EMAIL must be set in .env")
        raise typer.Exit(1)

    if wildcard:
        cmd = [
            "docker",
            "compose",
            "run",
            "--rm",
            "-it",
            "--entrypoint",
            "/bin/sh",
            "certbot",
            "-c",
            f"certbot certonly --manual --preferred-challenges=dns "
            f"-d {domain} -d *.{domain} "
            f"--email {email} --agree-tos --no-eff-email",
        ]
    else:
        cmd = [
            "docker",
            "compose",
            "run",
            "--rm",
            "-it",
            "--entrypoint",
            "/bin/sh",
            "certbot",
            "-c",
            f"certbot certonly --webroot --webroot-path /var/www/certbot "
            f"-d {domain} -d www.{domain} "
            f"--email {email} --agree-tos --no-eff-email",
        ]

    sys.exit(subprocess.call(cmd, env=docker_env()))


@app.command()
def renew() -> None:
    """Renew SSL certificates and reload nginx.

    Examples:
        phoxtail ssl renew
    """
    env = docker_env()
    result = subprocess.call(["docker", "compose", "run", "--rm", "certbot", "renew", "-q"], env=env)
    if result != 0:
        console.print("[red]Error:[/red] Certificate renewal failed")
        raise typer.Exit(1)

    result = subprocess.call(["docker", "compose", "exec", "nginx", "nginx", "-s", "reload"], env=env)
    if result != 0:
        console.print("[red]Error:[/red] Nginx reload failed")
        raise typer.Exit(1)

    console.print("[green bold]✓ Certificates renewed and nginx reloaded[/green bold]")
