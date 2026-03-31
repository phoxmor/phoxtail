"""Database management commands for Phoxtail."""

import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from phoxtail.cli.utils.docker import docker_db, docker_manage
from phoxtail.cli.utils.env import read_env_value

app = typer.Typer()
console = Console()

DUMP_FILENAME = "remote_pull.sql"


@app.command(name="pull")
def pull(
    remote_host: str = typer.Argument(
        ...,
        help="SSH connection string (e.g., user@example.com)",
    ),
    remote_dir: str = typer.Argument(
        ...,
        help="Path to the project on the remote server",
    ),
) -> None:
    """Pull the database from a remote server.

    Creates a pg_dump on the remote, downloads it via SCP, and restores
    it locally.  A safety backup is created automatically before restoring.
    """
    backups_dir = Path.cwd() / "db-backups"
    backups_dir.mkdir(exist_ok=True)
    local_dump_path = backups_dir / DUMP_FILENAME
    local_domain = read_env_value("DOMAIN") or "localhost"

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task(description="Starting...", total=None)
        try:
            # 1. Dump on remote.
            progress.update(task, description="Dumping database on remote...")
            remote_cmd = (
                f"cd {remote_dir} && "
                f"docker compose exec -T db sh -c "
                f"'PGPASSWORD=$POSTGRES_PASSWORD pg_dump -h localhost"
                f" -U $POSTGRES_USER $POSTGRES_DB'"
                f" > {DUMP_FILENAME}"
            )
            subprocess.run(
                ["ssh", remote_host, remote_cmd],
                check=True,
                capture_output=True,
                text=True,
            )

            # 2. Download.
            progress.update(task, description="Downloading dump...")
            subprocess.run(
                [
                    "scp",
                    f"{remote_host}:{remote_dir}/{DUMP_FILENAME}",
                    str(local_dump_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            # Clean up remote dump file (failure is non-critical).
            subprocess.run(
                ["ssh", remote_host, f"rm -f {remote_dir}/{DUMP_FILENAME}"],
                capture_output=True,
            )

            # 3. Safety backup of current local state (non-fatal on fresh projects).
            progress.update(task, description="Creating safety backup...")
            try:
                docker_db(
                    "PGPASSWORD=$POSTGRES_PASSWORD pg_dump -h localhost"
                    " -U $POSTGRES_USER $POSTGRES_DB"
                    " > /db-backups/pre_pull_safety.sql"
                )
            except subprocess.CalledProcessError:
                console.print("  [dim]Safety backup skipped (no existing data)[/dim]")

            # 4. Restore: drop schema, recreate, load dump via stdin
            #    (avoids dependency on the db-backups bind mount).
            progress.update(task, description="Restoring into local database...")
            restore_cmd = [
                "docker",
                "compose",
                "exec",
                "-T",
                "db",
                "sh",
                "-c",
                "PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost"
                " -U $POSTGRES_USER -d $POSTGRES_DB"
                " -v ON_ERROR_STOP=1 --single-transaction"
                ' -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
                ' GRANT ALL ON SCHEMA public TO \\"$POSTGRES_USER\\";'
                ' GRANT ALL ON SCHEMA public TO public;"'
                " -f -",
            ]
            with open(local_dump_path) as f:
                result = subprocess.run(
                    restore_cmd, stdin=f, capture_output=True, text=True
                )
            if result.returncode != 0:
                raise subprocess.CalledProcessError(
                    result.returncode,
                    restore_cmd,
                    output=result.stdout,
                    stderr=result.stderr,
                )

            # 5. Update Wagtail Site hostnames to local domain.
            progress.update(
                task, description=f"Updating hostnames to {local_domain}..."
            )
            docker_db(
                "PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost"
                " -U $POSTGRES_USER -d $POSTGRES_DB"
                ' -c "UPDATE wagtailcore_site SET hostname = CASE'
                "  WHEN hostname = ("
                "    SELECT hostname FROM wagtailcore_site"
                "    WHERE is_default_site = true LIMIT 1"
                f"  ) THEN '{local_domain}'"
                "  ELSE CONCAT("
                "    SPLIT_PART(hostname, '.', 1),"
                f"   '.{local_domain}'"
                "  )"
                ' END"'
            )

            # 6. Reset all superuser passwords for local access.
            progress.update(task, description="Resetting superuser passwords...")
            result = docker_manage(
                "shell",
                "-c",
                (
                    "from django.contrib.auth import get_user_model;"
                    "User = get_user_model();"
                    "emails = ','.join(User.objects.filter(is_superuser=True)"
                    ".values_list('email', flat=True));"
                    "print('__SUPERUSERS__:' + emails)"
                ),
            )
            # Use a unique marker to ignore Django shell startup noise.
            marker_line = next(
                (
                    line
                    for line in result.stdout.splitlines()
                    if line.startswith("__SUPERUSERS__:")
                ),
                None,
            )
            raw = (marker_line or "").removeprefix("__SUPERUSERS__:")
            superuser_emails = [e for e in raw.split(",") if e]

            if superuser_emails:
                progress.stop()
                console.print(f"  Superusers: {', '.join(superuser_emails)}")
                new_password = typer.prompt(
                    "Set local password for all superusers",
                    hide_input=True,
                    confirmation_prompt=False,
                )
                docker_manage(
                    "shell",
                    "-c",
                    (
                        "from django.contrib.auth import get_user_model;"
                        "User = get_user_model();"
                        f"pw={new_password!r};"
                        "[u.set_password(pw) or u.save()"
                        " for u in User.objects.filter(is_superuser=True)]"
                    ),
                )
                console.print("[green bold]✓ Database pulled and restored[/green bold]")
            else:
                console.print(
                    "[green bold]✓ Database pulled and restored[/green bold]\n"
                    "  [yellow]No superuser found — run:[/yellow] "
                    "phoxtail manage createsuperuser"
                )
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if e.stderr else str(e)
            console.print(f"[red]Error:[/red] {stderr}")
            raise typer.Exit(1)
        finally:
            if local_dump_path.exists():
                local_dump_path.unlink()


@app.command(name="backup")
def backup() -> None:
    """Create a database backup.

    Saves a timestamped SQL dump to the db-backups volume.
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Creating database backup...", total=None)
        try:
            docker_db(
                "PGPASSWORD=$POSTGRES_PASSWORD pg_dump -h localhost"
                " -U $POSTGRES_USER $POSTGRES_DB"
                " > /db-backups/$(date +%F_%H-%M-%S).sql"
            )
            console.print("[green bold]✓ Database backup created[/green bold]")
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if e.stderr else str(e)
            console.print(f"[red]Error:[/red] {stderr}")
            raise typer.Exit(1)


@app.command(name="restore")
def restore(
    backup_file: str = typer.Argument(
        ...,
        help="Backup filename to restore (e.g., 2026-03-15_12-00-00.sql)",
    ),
) -> None:
    """Restore the database from a backup file.

    A safety backup of the current state is created automatically before restoring.
    The restore runs in a single transaction and will roll back on error.
    """
    from rich.prompt import Confirm

    if not Confirm.ask(
        "This will replace the current database with "
        f"[bold]{backup_file}[/bold]. Continue?",
        default=False,
    ):
        raise typer.Exit(0)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        try:
            progress.add_task(
                description="Creating safety backup of current state...", total=None
            )
            docker_db(
                "PGPASSWORD=$POSTGRES_PASSWORD pg_dump -h localhost"
                " -U $POSTGRES_USER $POSTGRES_DB"
                " > /db-backups/pre_restore_safety.sql"
            )

            progress.add_task(
                description=f"Restoring from {backup_file}...", total=None
            )
            docker_db(
                "PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost"
                " -U $POSTGRES_USER -d $POSTGRES_DB"
                " -v ON_ERROR_STOP=1 --single-transaction"
                ' -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
                ' GRANT ALL ON SCHEMA public TO \\"$POSTGRES_USER\\";'
                ' GRANT ALL ON SCHEMA public TO public;"'
                f" -f /db-backups/{backup_file}"
            )
            console.print(
                f"[green bold]✓ Database restored from {backup_file}[/green bold]"
            )
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if e.stderr else str(e)
            console.print(f"[red]Error:[/red] {stderr}")
            raise typer.Exit(1)
