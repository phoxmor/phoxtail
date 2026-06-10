"""server deploy — copy configs to server and start the application."""

import subprocess
from pathlib import Path

import questionary
import typer
from rich.console import Console
from rich.panel import Panel

from phoxtail.cli.server.utils import (
    _SCP_OPTS,
    scp_to,
    ssh_check,
    ssh_live,
    ssh_run,
)
from phoxtail.cli.utils.config import find_config_file, get_project_name, slugify

console = Console()

_DEPLOY_DIR = Path(".phoxtail/deploy")


def deploy(
    ip: str = typer.Argument(..., help="Server IP address."),
    user: str = typer.Option(
        "phoxtail",
        "--user",
        "-u",
        help="Deploy username on the server.",
    ),
) -> None:
    """Deploy the project to a remote server.

    Generates config files locally, copies them to the server,
    then pulls the image from GHCR and starts the containers.

    The Docker image must already be pushed to GHCR before running this:
        phoxtail docker release

    Re-running is safe — completed steps are skipped, pull+start always runs.

    Examples:
        phoxtail server deploy 1.2.3.4
        phoxtail server deploy 1.2.3.4 --user myuser
    """
    if find_config_file() is None:
        console.print("[red]Error:[/red] No phoxtail.toml found. Run this command from a phoxtail project directory.")
        raise typer.Exit(1)

    project_dir = f"~/{slugify(get_project_name())}"
    local_configs = [
        (
            _DEPLOY_DIR / ".env",
            ["phoxtail", "env", "create", "production", "--server-ip", ip, "--output", str(_DEPLOY_DIR / ".env")],
            ".env",
        ),
        (
            _DEPLOY_DIR / "docker-compose.prod.yaml",
            [
                "phoxtail",
                "docker",
                "create",
                "compose",
                "production",
                "--registry",
                "--output",
                str(_DEPLOY_DIR / "docker-compose.prod.yaml"),
            ],
            "docker-compose.yaml",
        ),
        (
            _DEPLOY_DIR / "nginx.conf",
            ["phoxtail", "nginx", "create", "initial", "--output", str(_DEPLOY_DIR / "nginx.conf")],
            "nginx.conf",
        ),
    ]

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
        # 2. Docker check — only prerequisite on the server
        # ------------------------------------------------------------------
        if not ssh_check(user, ip, "command -v docker"):
            console.print("[red]Docker not found on server.[/red]\n  Cloud-init may not have finished.")
            raise typer.Exit(1)
        console.print("  [green]✓[/green] Docker available")

        # ------------------------------------------------------------------
        # 3. Project directory
        # ------------------------------------------------------------------
        ssh_run(user, ip, f"mkdir -p {project_dir}/db-backups")
        console.print("  [green]✓[/green] Project directory ready")

        # ------------------------------------------------------------------
        # 4. Local config files — generate any that are missing
        # ------------------------------------------------------------------
        _DEPLOY_DIR.mkdir(parents=True, exist_ok=True)
        console.print("\n[bold]Local configuration[/bold]")
        for local_path, cmd, _ in local_configs:
            if local_path.exists():
                console.print(
                    f"  [green]✓[/green] {local_path.name} [dim](exists — delete {local_path} to regenerate)[/dim]"
                )
                continue
            console.print(f"\n  [bold cyan]→[/bold cyan] {local_path.name}")
            rc = subprocess.call(cmd)
            if rc != 0:
                console.print(f"  [red]✗[/red] Failed to generate {local_path.name}")
                raise typer.Exit(1)
            console.print(f"  [green]✓[/green] {local_path.name}")

        # ------------------------------------------------------------------
        # 5. Copy config files to server
        # ------------------------------------------------------------------
        console.print("\n[bold]Uploading config files[/bold]")
        for local_path, _, remote_name in local_configs:
            remote_path = f"{project_dir}/{remote_name}"

            if ssh_check(user, ip, f"test -f {remote_path}"):
                console.print(
                    f"  [green]✓[/green] {remote_name} "
                    f"[dim](already on server — delete {project_dir}/{remote_name} on server to replace)[/dim]"
                )
                continue

            with console.status(f"  Copying {remote_name}..."):
                if not scp_to(user, ip, local_path, remote_path):
                    console.print(f"  [red]✗[/red] Failed to copy {remote_name}")
                    raise typer.Exit(1)
            console.print(f"  [green]✓[/green] {remote_name} uploaded")

        # ------------------------------------------------------------------
        # 6. GHCR login
        # ------------------------------------------------------------------
        console.print()
        if ssh_check(user, ip, "grep -q 'ghcr.io' ~/.docker/config.json 2>/dev/null"):
            console.print("  [green]✓[/green] GHCR [dim](already authenticated)[/dim]")
        else:
            console.print(
                Panel(
                    "A GitHub Personal Access Token with [bold]read:packages[/bold] scope\n"
                    "is needed to pull the image from GHCR.\n\n"
                    "  [dim]GitHub → Settings → Developer settings →\n"
                    "  Personal access tokens → read:packages[/dim]",
                    border_style="cyan",
                    expand=False,
                )
            )
            gh_user = questionary.text("GitHub username:").ask()
            gh_token = questionary.password("Personal Access Token:").ask()
            if not gh_user or not gh_token:
                console.print("[dim]Cancelled.[/dim]")
                raise typer.Exit(0)

            result = subprocess.run(
                [
                    "ssh",
                    *_SCP_OPTS,
                    f"{user}@{ip}",
                    f"docker login ghcr.io -u {gh_user} --password-stdin",
                ],
                input=gh_token,
                text=True,
                capture_output=True,
            )
            if result.returncode != 0:
                console.print(f"[red]GHCR login failed:[/red] {result.stderr.strip()}")
                raise typer.Exit(1)
            console.print("  [green]✓[/green] GHCR login successful")

        # ------------------------------------------------------------------
        # 7. Pull image and start containers (always runs)
        # ------------------------------------------------------------------
        console.print("\n  [bold cyan]→[/bold cyan] Pulling image and starting containers")
        rc = ssh_live(
            user,
            ip,
            f"cd {project_dir} && docker compose pull && docker compose up -d",
        )
        if rc != 0:
            console.print("  [red]✗[/red] Deployment failed")
            raise typer.Exit(1)
        console.print("  [green]✓[/green] Containers started")

        # ------------------------------------------------------------------
        # Done
        # ------------------------------------------------------------------
        console.print()
        console.print(
            Panel(
                "[green]Deployment complete![/green]"
                "\n\n"
                f"  [dim]Application:[/dim]  http://{ip}\n\n"
                "  [dim]Next — point your domain's DNS A record "
                f"to {ip}, then run:[/dim]\n"
                f"  [cyan]phoxtail server ssl {ip}[/cyan]",
                border_style="green",
                expand=False,
            )
        )

    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(0)
