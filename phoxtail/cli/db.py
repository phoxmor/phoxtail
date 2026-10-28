"""Database management commands for Phoxtail."""

import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm

from phoxtail.cli.server.utils import _SCP_OPTS, _SSH_MUX, read_deploy_env, verify_server_identity
from phoxtail.cli.utils.config import get_project_name, slugify
from phoxtail.cli.utils.docker import docker_db, docker_env, docker_manage
from phoxtail.cli.utils.env import read_env_value

app = typer.Typer()
console = Console()

DUMP_FILENAME = "remote_pull.sql"
PUSH_DUMP_FILENAME = "local_push.sql"

PG_DUMP = "PGPASSWORD=$POSTGRES_PASSWORD pg_dump -h localhost -U $POSTGRES_USER $POSTGRES_DB"

# DJANGO_ENV becomes part of a file name and of a remote shell command, so it
# must be a plain word. No underscore: that is the separator in the name.
_ENVIRONMENT = re.compile(r"[A-Za-z0-9-]+")


@app.command(name="pull")
def pull(
    ip: str = typer.Argument(..., help="Server IP address."),
    user: str = typer.Option(
        "phoxtail",
        "--user",
        "-u",
        help="Deploy username on the server.",
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

    verify_server_identity(user, ip)

    remote_host = f"{user}@{ip}"
    project_dir = f"~/{slugify(get_project_name())}"

    if not Confirm.ask(
        f"This will replace the local [bold]{get_project_name()}[/bold] database "
        f"with the one from [bold]{ip}[/bold]. Continue?",
        default=False,
    ):
        raise typer.Exit(0)

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
                f"cd {project_dir} && "
                f"docker compose exec -T db sh -c "
                f"'PGPASSWORD=$POSTGRES_PASSWORD pg_dump -h localhost"
                f" -U $POSTGRES_USER $POSTGRES_DB'"
                f" > {DUMP_FILENAME}"
            )
            subprocess.run(
                ["ssh", *_SSH_MUX, remote_host, remote_cmd],
                check=True,
                capture_output=True,
                text=True,
            )

            # 2. Download.
            progress.update(task, description="Downloading dump...")
            subprocess.run(
                [
                    "scp",
                    *_SCP_OPTS,
                    f"{remote_host}:{project_dir}/{DUMP_FILENAME}",
                    str(local_dump_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            # Clean up remote dump file (failure is non-critical).
            subprocess.run(
                ["ssh", *_SSH_MUX, remote_host, f"rm -f {project_dir}/{DUMP_FILENAME}"],
                capture_output=True,
            )

            # 3. Safety backup of current local state.
            progress.update(task, description="Creating safety backup...")
            try:
                docker_db(
                    "PGPASSWORD=$POSTGRES_PASSWORD pg_dump -h localhost"
                    " -U $POSTGRES_USER $POSTGRES_DB"
                    " > /db-backups/pre_pull_safety.sql"
                )
            except subprocess.CalledProcessError as e:
                console.print(f"  [yellow]Safety backup skipped:[/yellow] {e.stderr or str(e)}")

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
                result = subprocess.run(restore_cmd, stdin=f, capture_output=True, text=True)
            if result.returncode != 0:
                raise subprocess.CalledProcessError(
                    result.returncode,
                    restore_cmd,
                    output=result.stdout,
                    stderr=result.stderr,
                )

            # 5. Update Wagtail Site hostnames to local domain.
            progress.update(task, description=f"Updating hostnames to {local_domain}...")
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
                (line for line in result.stdout.splitlines() if line.startswith("__SUPERUSERS__:")),
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


@app.command(name="push")
def push(
    ip: str = typer.Argument(..., help="Server IP address."),
    user: str = typer.Option(
        "phoxtail",
        "--user",
        "-u",
        help="Deploy username on the server.",
    ),
) -> None:
    """Push the local database to a remote server.

    Dumps the local database, uploads it, takes a remote safety backup,
    then restores the local dump on the server. Rewrites Wagtail site
    hostnames to the production domain from .phoxtail/deploy/.env.
    """
    verify_server_identity(user, ip)

    remote_domain = read_deploy_env("DOMAIN")
    if not remote_domain:
        console.print(
            "[red]Error:[/red] DOMAIN not set in .phoxtail/deploy/.env — "
            "cannot rewrite Wagtail hostnames for production."
        )
        raise typer.Exit(1)

    if not Confirm.ask(
        f"This will REPLACE the [bold]{get_project_name()}[/bold] database on "
        f"[bold]{ip}[/bold] ({remote_domain}) with your local database. Continue?",
        default=False,
    ):
        raise typer.Exit(0)

    remote_host = f"{user}@{ip}"
    project_dir = f"~/{slugify(get_project_name())}"
    remote_dump_path = f"{project_dir}/db-backups/{PUSH_DUMP_FILENAME}"

    backups_dir = Path.cwd() / "db-backups"
    backups_dir.mkdir(exist_ok=True)
    local_dump_path = backups_dir / PUSH_DUMP_FILENAME

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task(description="Starting...", total=None)
        try:
            # 1. Dump local database.
            progress.update(task, description="Dumping local database...")
            result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "db",
                    "sh",
                    "-c",
                    "PGPASSWORD=$POSTGRES_PASSWORD pg_dump -h localhost -U $POSTGRES_USER $POSTGRES_DB",
                ],
                capture_output=True,
                text=True,
                env=docker_env(),
            )
            if result.returncode != 0:
                console.print(f"[red]Failed to dump local database:[/red] {result.stderr.strip()}")
                raise typer.Exit(1)
            local_dump_path.write_text(result.stdout)

            # 2. Upload dump to remote db-backups dir (bind-mounted into container).
            progress.update(task, description="Uploading dump to server...")
            subprocess.run(
                ["scp", *_SCP_OPTS, str(local_dump_path), f"{remote_host}:{remote_dump_path}"],
                check=True,
                capture_output=True,
                text=True,
            )

            # 3. Remote safety backup — must succeed before the remote schema is dropped.
            progress.update(task, description="Creating remote safety backup...")
            result = subprocess.run(
                [
                    "ssh",
                    *_SSH_MUX,
                    remote_host,
                    f"cd {project_dir} && docker compose exec -T db sh -c "
                    f"'PGPASSWORD=$POSTGRES_PASSWORD pg_dump -h localhost"
                    f" -U $POSTGRES_USER $POSTGRES_DB"
                    f" > /db-backups/pre_push_safety.sql"
                    f" && test -s /db-backups/pre_push_safety.sql'",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                console.print(
                    f"[red]Remote safety backup failed:[/red] {result.stderr.strip()}\n"
                    "[red]Aborting — remote database not modified.[/red]"
                )
                raise typer.Exit(1)

            # 4. Restore: drop remote schema and load the uploaded dump.
            progress.update(task, description="Restoring on remote server...")
            result = subprocess.run(
                [
                    "ssh",
                    *_SSH_MUX,
                    remote_host,
                    f"cd {project_dir} && docker compose exec -T db sh -c "
                    f"'PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost"
                    f" -U $POSTGRES_USER -d $POSTGRES_DB"
                    f" -v ON_ERROR_STOP=1 --single-transaction"
                    f' -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
                    f' GRANT ALL ON SCHEMA public TO \\"$POSTGRES_USER\\";'
                    f' GRANT ALL ON SCHEMA public TO public;"'
                    f" -f /db-backups/{PUSH_DUMP_FILENAME}'",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                console.print(f"[red]Failed to restore on remote:[/red] {result.stderr.strip()}")
                raise typer.Exit(1)

            # 5. Rewrite Wagtail site hostnames to the production domain.
            #    SQL is piped via stdin to avoid quoting issues with shell escaping.
            progress.update(task, description=f"Updating hostnames to {remote_domain}...")
            update_sql = (
                f"UPDATE wagtailcore_site SET hostname = CASE "
                f"WHEN hostname = ("
                f"  SELECT hostname FROM wagtailcore_site"
                f"  WHERE is_default_site = true LIMIT 1"
                f") THEN '{remote_domain}' "
                f"ELSE CONCAT(SPLIT_PART(hostname, '.', 1), '.{remote_domain}') "
                f"END;"
            )
            result = subprocess.run(
                [
                    "ssh",
                    *_SSH_MUX,
                    remote_host,
                    f"cd {project_dir} && docker compose exec -T db sh -c "
                    f"'PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost"
                    f" -U $POSTGRES_USER -d $POSTGRES_DB -v ON_ERROR_STOP=1'",
                ],
                input=update_sql,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                console.print(f"[red]Failed to update hostnames:[/red] {result.stderr.strip()}")
                raise typer.Exit(1)

            console.print("[green bold]✓ Database pushed to server[/green bold]")

        except subprocess.CalledProcessError as e:
            stderr = e.stderr if e.stderr else str(e)
            console.print(f"[red]Error:[/red] {stderr}")
            raise typer.Exit(1)
        finally:
            if local_dump_path.exists():
                local_dump_path.unlink()
            subprocess.run(
                ["ssh", *_SSH_MUX, remote_host, f"rm -f {remote_dump_path}"],
                capture_output=True,
            )


def backup_name(environment: str | None, source: str = ".env") -> str:
    """Name a backup after the database it holds: ``<slug>_<env>_<UTC time>.sql``.

    The environment is the one recorded next to that database, never the
    place the command runs, so a copy moved anywhere still says what it is.
    """
    if not environment or not _ENVIRONMENT.fullmatch(environment):
        problem = "is not set" if not environment else f"is not a plain word ({environment!r})"
        console.print(
            f"[red]Error:[/red] DJANGO_ENV in {source} {problem}. It names the backup (development, production, …)."
        )
        raise typer.Exit(1)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
    return f"{slugify(get_project_name())}_{environment}_{stamp}.sql"


def _dump_into(name: str) -> str:
    """Shell that dumps into ``/db-backups/<name>`` only when the dump is whole.

    The dump goes to a ``.partial`` file first and is renamed once pg_dump
    succeeded and wrote something, so a file with a backup's name is always
    a complete backup. A failed dump leaves nothing behind.
    """
    partial = f"/db-backups/{name}.partial"
    return (
        f"{PG_DUMP} > {partial} && test -s {partial} && mv {partial} /db-backups/{name}"
        f" || {{ rm -f {partial}; exit 1; }}"
    )


def _remote_environment(remote_host: str, project_dir: str) -> str | None:
    """Read DJANGO_ENV from the server's own .env, which deploy never overwrites."""
    result = subprocess.run(
        ["ssh", *_SSH_MUX, remote_host, f"grep -m1 '^DJANGO_ENV=' {project_dir}/.env"],
        capture_output=True,
        text=True,
    )
    # grep exits 1 when the key is absent (reported by backup_name); 2 means
    # no readable .env, and 255 is ssh itself failing.
    if result.returncode not in (0, 1):
        reason = "could not reach the server" if result.returncode == 255 else f"cannot read {project_dir}/.env"
        console.print(f"[red]Error:[/red] {reason}: {result.stderr.strip()}")
        raise typer.Exit(1)
    value = result.stdout.strip().partition("=")[2].strip()
    return value.strip("'\"") or None


@app.command(name="backup")
def backup(
    ip: str | None = typer.Argument(None, help="Server IP address. Omit to back up the local database."),
    user: str = typer.Option(
        "phoxtail",
        "--user",
        "-u",
        help="Deploy username on the server.",
    ),
) -> None:
    """Create a database backup, locally or on a server.

    Saves an SQL dump named ``<slug>_<DJANGO_ENV>_<UTC time>.sql`` to
    db-backups/. With an IP, the dump is made on the server, kept in the
    server's db-backups/, and copied into the local db-backups/.

    Examples:
        phoxtail db backup
        phoxtail db backup 203.0.113.5
    """
    if ip is None:
        _backup_local()
    else:
        _backup_remote(ip, user)


def _backup_local() -> None:
    name = backup_name(read_env_value("DJANGO_ENV"))
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Creating database backup...", total=None)
        try:
            docker_db(_dump_into(name))
            console.print(f"[green bold]✓ Database backup created:[/green bold] db-backups/{name}")
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if e.stderr else str(e)
            console.print(f"[red]Error:[/red] {stderr}")
            raise typer.Exit(1)


def _backup_remote(ip: str, user: str) -> None:
    verify_server_identity(user, ip)

    remote_host = f"{user}@{ip}"
    project_dir = f"~/{slugify(get_project_name())}"
    name = backup_name(_remote_environment(remote_host, project_dir), source=f"the server's {project_dir}/.env")
    remote_path = f"{project_dir}/db-backups/{name}"
    backups_dir = Path.cwd() / "db-backups"
    backups_dir.mkdir(exist_ok=True)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task(description="Dumping database on server...", total=None)
        result = subprocess.run(
            [
                "ssh",
                *_SSH_MUX,
                remote_host,
                f"cd {project_dir} && docker compose exec -T db sh -c '{_dump_into(name)}'",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            console.print(f"[red]Server backup failed:[/red] {result.stderr.strip()}")
            raise typer.Exit(1)

        progress.update(task, description="Downloading backup...")
        # Downloaded under a .partial name too, for the same reason as the dump.
        partial = backups_dir / f"{name}.partial"
        result = subprocess.run(
            ["scp", *_SCP_OPTS, f"{remote_host}:{remote_path}", str(partial)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            partial.replace(backups_dir / name)
        else:
            partial.unlink(missing_ok=True)
            console.print(
                f"[red]Download failed:[/red] {result.stderr.strip()}\n"
                f"  The backup is safe on the server: {remote_path}"
            )
            raise typer.Exit(1)

    console.print(f"[green bold]✓ Server backup created:[/green bold] {remote_path}\n  Copied to db-backups/{name}")


@app.command(name="restore")
def restore(
    backup_file: str = typer.Argument(
        ...,
        help="Backup filename in db-backups/ (e.g., mysite_production_2026-03-15_12-00-00.sql)",
    ),
) -> None:
    """Restore the database from a backup file.

    A safety backup of the current state is created automatically before restoring.
    The restore runs in a single transaction and will roll back on error.
    """
    if not Confirm.ask(
        f"This will replace the current database with [bold]{backup_file}[/bold]. Continue?",
        default=False,
    ):
        raise typer.Exit(0)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        try:
            progress.add_task(description="Creating safety backup of current state...", total=None)
            docker_db(
                "PGPASSWORD=$POSTGRES_PASSWORD pg_dump -h localhost"
                " -U $POSTGRES_USER $POSTGRES_DB"
                " > /db-backups/pre_restore_safety.sql"
            )

            progress.add_task(description=f"Restoring from {backup_file}...", total=None)
            docker_db(
                "PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost"
                " -U $POSTGRES_USER -d $POSTGRES_DB"
                " -v ON_ERROR_STOP=1 --single-transaction"
                ' -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
                ' GRANT ALL ON SCHEMA public TO \\"$POSTGRES_USER\\";'
                ' GRANT ALL ON SCHEMA public TO public;"'
                f" -f /db-backups/{backup_file}"
            )
            console.print(f"[green bold]✓ Database restored from {backup_file}[/green bold]")
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if e.stderr else str(e)
            console.print(f"[red]Error:[/red] {stderr}")
            raise typer.Exit(1)
