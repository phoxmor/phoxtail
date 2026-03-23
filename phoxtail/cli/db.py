"""Database management commands for Phoxtail."""

import ipaddress
import json
import subprocess
from enum import Enum
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from phoxtail.cli.utils.config import (
    get_cluster_names,
    get_clusters,
    resolve_cluster_order,
)
from phoxtail.cli.utils.docker import docker_db, docker_manage
from phoxtail.cli.utils.env import read_env_value

app = typer.Typer()
console = Console()


def _build_data_cluster_enum():
    """Build DataCluster enum from phoxtail.toml cluster names + 'all'."""
    members = {name.upper(): name for name in get_cluster_names()}
    members["ALL"] = "all"
    return Enum("DataCluster", members, type=str)


DataCluster = _build_data_cluster_enum()


def _deep_localize(val, hostname_map: dict[str, str]):
    """Recursively replace hostnames in a data structure.

    Handles plain dicts/lists and JSON-encoded strings that may
    contain hostname references (e.g. StreamField data).
    """
    if isinstance(val, dict):
        return {k: _deep_localize(v, hostname_map) for k, v in val.items()}
    elif isinstance(val, list):
        # Natural key format: ["hostname", port]
        if len(val) == 2 and isinstance(val[0], str) and isinstance(val[1], int):
            h = val[0].lower()
            if h in hostname_map:
                return [hostname_map[h], val[1]]
        return [_deep_localize(i, hostname_map) for i in val]
    elif isinstance(val, str):
        if (val.startswith("{") and val.endswith("}")) or (
            val.startswith("[") and val.endswith("]")
        ):
            try:
                parsed = json.loads(val)
                translated = _deep_localize(parsed, hostname_map)
                return json.dumps(translated)
            except (json.JSONDecodeError, TypeError):
                pass
    return val


def _localize_hostnames(data: list, target_domain: str) -> list:
    """Translate remote hostnames to the target domain.

    Builds a hostname map from wagtailcore.site entries, then applies it
    across the entire fixture data including JSON-encoded string fields.
    """
    hostname_map = {}
    for entry in data:
        if entry.get("model") == "wagtailcore.site":
            fields = entry.get("fields", {})
            old_h = fields.get("hostname", "").lower()
            if (
                not old_h
                or old_h == target_domain
                or old_h.endswith(f".{target_domain}")
            ):
                continue
            try:
                ipaddress.ip_address(old_h)
                continue
            except ValueError:
                pass

            parts = old_h.split(".")
            if len(parts) > 2:
                subdomain = ".".join(parts[:-2])
                new_h = f"{subdomain}.{target_domain}"
            else:
                new_h = target_domain
            hostname_map[old_h] = new_h
            fields["hostname"] = new_h

    if not hostname_map:
        return data

    for entry in data:
        entry["fields"] = _deep_localize(entry.get("fields", {}), hostname_map)

    return data


def _pull_single_cluster(
    cluster_name: str,
    remote_host: str,
    remote_dir: str,
    localize: bool,
    progress,
    task,
) -> None:
    """Pull and load a single cluster from the remote server."""
    clusters = get_clusters()
    selected_apps = clusters[cluster_name]["apps"]
    dump_filename = f"remote_{cluster_name}_pull.json"
    local_dump_path = Path.cwd() / dump_filename

    try:
        remote_cmd = (
            f"cd {remote_dir} && "
            f"docker compose exec web python manage.py dumpdata "
            f"{' '.join(selected_apps)} "
            f"--natural-foreign --indent 2 > {dump_filename}"
        )
        progress.update(
            task, description=f"Dumping {cluster_name.upper()} on remote..."
        )
        subprocess.run(
            ["ssh", remote_host, remote_cmd],
            check=True,
            capture_output=True,
            text=True,
        )
        progress.update(task, description=f"Downloading {cluster_name.upper()} dump...")
        subprocess.run(
            [
                "scp",
                f"{remote_host}:{remote_dir}/{dump_filename}",
                str(local_dump_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        # Clean up remote dump file (failure is non-critical)
        subprocess.run(
            ["ssh", remote_host, f"rm -f {remote_dir}/{dump_filename}"],
            capture_output=True,
        )

        if localize:
            target_domain = read_env_value("DOMAIN") or "localhost"
            progress.update(
                task,
                description=(
                    f"Localizing {cluster_name.upper()} hostnames to {target_domain}..."
                ),
            )
            with open(local_dump_path) as f:
                data = json.load(f)
            data = _localize_hostnames(data, target_domain)
            with open(local_dump_path, "w") as f:
                json.dump(data, f, indent=2)

        progress.update(
            task, description=f"Loading {cluster_name.upper()} into database..."
        )
        docker_manage("loaddata", local_dump_path.name)
    finally:
        if local_dump_path.exists():
            local_dump_path.unlink()


@app.command(name="pull")
def pull(
    cluster: DataCluster = typer.Argument(
        ...,
        help="The data cluster to pull from the remote server",
    ),
    remote_host: str = typer.Argument(
        ...,
        help="SSH connection string (e.g., user@example.com)",
    ),
    remote_dir: str = typer.Argument(
        ...,
        help="Path to the project on the remote server",
    ),
    localize: bool = typer.Option(
        True,
        "--localize/--no-localize",
        help="Whether to translate remote hostnames to localhost/subdomains.localhost",
    ),
) -> None:
    """Pull data clusters from a remote server to the local environment.

    DANGER: This will FLUSH your local database before loading.
    A safety backup is created automatically before flushing.

    Dependencies are resolved automatically. For example, pulling 'booking'
    will pull 'cms' first since booking data depends on it.
    """
    try:
        cluster_order = resolve_cluster_order(cluster.value)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if len(cluster_order) > 1:
        names = " → ".join(c.upper() for c in cluster_order)
        console.print(f"[dim]Resolved pull order: {names}[/dim]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task(description="Starting...", total=None)
        try:
            progress.update(task, description="Creating safety backup...")
            docker_db(
                "PGPASSWORD=$POSTGRES_PASSWORD pg_dump -h localhost"
                " -U $POSTGRES_USER $POSTGRES_DB"
                " > /db-backups/pre_pull_safety.sql"
            )

            progress.update(task, description="Flushing local database...")
            docker_manage("flush", "--no-input")

            for cluster_name in cluster_order:
                _pull_single_cluster(
                    cluster_name, remote_host, remote_dir, localize, progress, task
                )

            pulled = ", ".join(c.upper() for c in cluster_order)
            console.print(f"[green bold]✓ {pulled} data pulled and loaded[/green bold]")
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if e.stderr else str(e)
            console.print(f"[red]Error:[/red] {stderr}")
            raise typer.Exit(1)


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
