"""server deploy — clone the project and deploy the application."""

import questionary
import typer
from rich.console import Console
from rich.panel import Panel

from phoxtail.cli.server.utils import (
    PROJECT_DIR,
    detect_repo_url,
    git_host,
    ssh_check,
    ssh_live,
    ssh_run,
    to_ssh_url,
)

console = Console()

# Steps: (label, phoxtail command, file to check, interactive?)
_APP_STEPS = [
    (
        "Environment file",
        "phoxtail env create production",
        ".env",
        True,
    ),
    (
        "Dockerfile",
        "phoxtail docker create dockerfile",
        "Dockerfile",
        True,
    ),
    (
        ".dockerignore",
        "phoxtail docker create dockerignore",
        ".dockerignore",
        False,
    ),
    (
        "Docker Compose",
        "phoxtail docker create compose production",
        "docker-compose.yaml",
        True,
    ),
    (
        "Nginx config",
        "phoxtail nginx create initial",
        "nginx.conf",
        False,
    ),
]


def deploy(
    ip: str = typer.Argument(
        ...,
        help="Server IP address.",
    ),
    user: str = typer.Option(
        "phoxtail",
        "--user",
        "-u",
        help="Deploy username on the server.",
    ),
    repo: str | None = typer.Option(
        None,
        "--repo",
        "-r",
        help="Git repo URL (SSH format). Auto-detected from local origin.",
    ),
) -> None:
    """Deploy the project to a remote server.

    Generates a deploy key, clones the repository via SSH,
    then runs phoxtail commands over SSH to create
    production configs and start the containers.

    Re-running is safe — completed steps are skipped.

    Examples:
        phoxtail server deploy 1.2.3.4
        phoxtail server deploy 1.2.3.4 --user myuser
        phoxtail server deploy 1.2.3.4 -r git@github.com:o/r.git
    """
    console.print()

    try:
        # ----------------------------------------------------------
        # 1. Verify SSH connectivity + prerequisites
        # ----------------------------------------------------------
        with console.status(f"[bold cyan]Connecting to {user}@{ip}...[/bold cyan]"):
            if not ssh_check(user, ip, "echo ok"):
                console.print(f"[red]Cannot connect to {user}@{ip}.[/red]")
                raise typer.Exit(1)
        console.print(f"  [green]✓[/green] Connected to {user}@{ip}")

        for tool in ("git", "docker", "phoxtail"):
            if not ssh_check(user, ip, f"command -v {tool}"):
                console.print(
                    f"[red]{tool} not found on server.[/red]\n"
                    "  Cloud-init may not have finished."
                )
                raise typer.Exit(1)
        console.print("  [green]✓[/green] Prerequisites (git, docker, phoxtail)")

        # ----------------------------------------------------------
        # 2. Resolve repository URL
        # ----------------------------------------------------------
        if not repo:
            repo = detect_repo_url()
        if repo:
            repo = to_ssh_url(repo)
            console.print(f"  [dim]Repository:[/dim] {repo}")
        if not repo:
            console.print()
            repo = questionary.text(
                "Git repository URL (SSH format):",
                instruction=("e.g. git@github.com:owner/repo.git"),
            ).ask()
            if not repo:
                console.print("[red]No repository URL provided.[/red]")
                raise typer.Exit(1)
            repo = to_ssh_url(repo)

        host = git_host(repo)

        # ----------------------------------------------------------
        # 3. Deploy key
        # ----------------------------------------------------------
        key_exists = ssh_check(
            user,
            ip,
            "test -f ~/.ssh/deploy_key",
        )
        if not key_exists:
            with console.status("[bold cyan]Generating deploy key...[/bold cyan]"):
                r = ssh_run(
                    user,
                    ip,
                    "ssh-keygen -t ed25519 "
                    "-f ~/.ssh/deploy_key "
                    '-N "" -C "phoxtail-deploy"',
                )
                if r.returncode != 0:
                    console.print(
                        f"[red]Failed to generate deploy key:[/red] {r.stderr}"
                    )
                    raise typer.Exit(1)
            console.print("  [green]✓[/green] Deploy key generated")
        else:
            console.print("  [green]✓[/green] Deploy key exists")

        # SSH config for the git host (idempotent)
        has_host = ssh_check(
            user,
            ip,
            f"grep -q 'Host {host}' ~/.ssh/config 2>/dev/null",
        )
        if not has_host:
            ssh_run(
                user,
                ip,
                "{"
                f" echo ''; echo 'Host {host}';"
                " echo '    IdentityFile ~/.ssh/deploy_key';"
                " echo '    StrictHostKeyChecking accept-new';"
                "} >> ~/.ssh/config"
                " && chmod 600 ~/.ssh/config",
            )

        # Show public key
        pub = ssh_run(user, ip, "cat ~/.ssh/deploy_key.pub")
        if pub.returncode != 0:
            console.print("[red]Cannot read public key.[/red]")
            raise typer.Exit(1)

        console.print()
        console.print(
            Panel(
                "[bold]Add this deploy key to your "
                "repository:[/bold]\n\n"
                f"  {pub.stdout.strip()}\n\n"
                f"  [dim]{host}: Settings → Deploy keys"
                " → Add deploy key (read-only)[/dim]",
                border_style="cyan",
                expand=False,
            )
        )

        confirmed = questionary.confirm(
            "Have you added the deploy key?",
            default=True,
        ).ask()
        if not confirmed:
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

        # Verify git access
        console.print()
        with console.status(f"[bold cyan]Testing git access to {host}...[/bold cyan]"):
            test = ssh_run(
                user,
                ip,
                "ssh -o StrictHostKeyChecking=accept-new "
                "-o BatchMode=yes "
                "-i ~/.ssh/deploy_key "
                f"-T git@{host} 2>&1 || true",
            )
        out = test.stdout.lower()
        if "successfully" in out or "welcome" in out:
            console.print(f"  [green]✓[/green] Git access to {host} confirmed")
        else:
            console.print(
                f"  [yellow]Warning:[/yellow] Could not verify access to {host}."
            )
            if test.stdout.strip():
                console.print(f"    [dim]{test.stdout.strip()}[/dim]")
            console.print("  Continuing — clone may still work.")

        # ----------------------------------------------------------
        # 4. Clone repository
        # ----------------------------------------------------------
        clone_exists = ssh_check(
            user,
            ip,
            f"test -d {PROJECT_DIR}/.git",
        )
        if clone_exists:
            console.print("  [green]✓[/green] Repository already cloned")
        else:
            console.print()
            with console.status("[bold cyan]Cloning repository...[/bold cyan]"):
                ssh_run(
                    user,
                    ip,
                    f"rmdir {PROJECT_DIR} 2>/dev/null; true",
                )
                r = ssh_run(
                    user,
                    ip,
                    "GIT_SSH_COMMAND="
                    "'ssh -i ~/.ssh/deploy_key "
                    "-o StrictHostKeyChecking=accept-new' "
                    f"git clone {repo} {PROJECT_DIR}",
                )
                if r.returncode != 0:
                    console.print(f"[red]Clone failed:[/red]\n{r.stderr}")
                    raise typer.Exit(1)
            console.print("  [green]✓[/green] Repository cloned")

        # ----------------------------------------------------------
        # 5. Runtime directories (not in git)
        # ----------------------------------------------------------
        ssh_run(
            user,
            ip,
            f"mkdir -p {PROJECT_DIR}/db-backups "
            f"{PROJECT_DIR}/media "
            f"{PROJECT_DIR}/static",
        )

        # ----------------------------------------------------------
        # 6–9. Application configuration
        # ----------------------------------------------------------
        console.print()
        console.print("[bold]Application configuration[/bold]")

        for label, cmd, check_file, interactive in _APP_STEPS:
            exists = ssh_check(
                user,
                ip,
                f"test -f {PROJECT_DIR}/{check_file}",
            )
            if exists:
                console.print(f"  [green]✓[/green] {label} [dim](exists)[/dim]")
                continue

            console.print(f"\n  [bold cyan]→[/bold cyan] {label}")
            full = f"cd {PROJECT_DIR} && {cmd}"

            if interactive:
                rc = ssh_live(user, ip, full, tty=True)
            else:
                result = ssh_run(user, ip, full)
                rc = result.returncode
                if rc != 0 and result.stderr.strip():
                    console.print(f"    [dim]{result.stderr.strip()}[/dim]")

            if rc != 0:
                console.print(f"  [red]✗[/red] {label} failed")
                console.print(
                    "\n  [dim]Fix the issue and re-run "
                    "server deploy — completed "
                    "steps will be skipped.[/dim]"
                )
                raise typer.Exit(1)
            console.print(f"  [green]✓[/green] {label}")

        # ----------------------------------------------------------
        # 10. Build and start containers
        # ----------------------------------------------------------
        console.print("\n  [bold cyan]→[/bold cyan] Building and starting containers")
        rc = ssh_live(
            user,
            ip,
            f"cd {PROJECT_DIR} && phoxtail docker up --build",
        )
        if rc != 0:
            console.print("  [red]✗[/red] Container startup failed")
            raise typer.Exit(1)
        console.print("  [green]✓[/green] Containers started")

        # ----------------------------------------------------------
        # Done
        # ----------------------------------------------------------
        console.print()
        console.print(
            Panel(
                "[green]Configuration complete![/green]"
                "\n\n"
                f"  [dim]Application:[/dim]  "
                f"http://{ip}\n\n"
                "  [dim]Next — point your domain's DNS "
                f"A record to {ip}, then run:[/dim]\n"
                f"  [cyan]phoxtail server ssl {ip}[/cyan]",
                border_style="green",
                expand=False,
            )
        )

    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(0)
