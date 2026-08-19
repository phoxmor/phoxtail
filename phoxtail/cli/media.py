"""Media management commands for Phoxtail."""

import re
import subprocess
from pathlib import Path
from typing import TypedDict

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn
from rich.prompt import Confirm

from phoxtail.cli.server.utils import _SSH_MUX, read_deploy_env, verify_server_identity
from phoxtail.cli.utils.config import get_project_name, slugify

app = typer.Typer()
console = Console()

# Matches rsync --info=progress2 output like:
#   1,234,567  45%  12.34MB/s    0:01:23
_PROGRESS_RE = re.compile(r"(\d+)%")

_STAGING_DIR = ".media_sync_tmp"


class RsyncStats(TypedDict, total=False):
    """What rsync --stats reports, when it reports it.

    Both keys are absent for a run that transferred nothing, which is why
    every reader supplies a default.
    """

    files: int
    size: str


def _parse_rsync_stats(output: str) -> RsyncStats:
    """Parse rsync --stats output into a summary dict."""
    stats: RsyncStats = {}

    match = re.search(r"Number of regular files transferred:\s*([\d,]+)", output)
    if match:
        stats["files"] = int(match.group(1).replace(",", ""))

    match = re.search(r"Total transferred file size:\s*([\d,]+)", output)
    if match:
        size_bytes = int(match.group(1).replace(",", ""))
        if size_bytes >= 1_073_741_824:
            stats["size"] = f"{size_bytes / 1_073_741_824:.1f} GB"
        elif size_bytes >= 1_048_576:
            stats["size"] = f"{size_bytes / 1_048_576:.1f} MB"
        elif size_bytes >= 1024:
            stats["size"] = f"{size_bytes / 1024:.1f} KB"
        else:
            stats["size"] = f"{size_bytes} bytes"

    return stats


def _run_rsync_with_progress(rsync_cmd: list[str], label: str = "Syncing media") -> str:
    """Run rsync and display a Rich progress bar from --info=progress2 output.

    Returns the combined stdout/stderr output for stats parsing.
    """
    proc = subprocess.Popen(
        rsync_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    output_lines = []

    with Progress(
        TextColumn(f"[bold cyan]{label}"),
        BarColumn(),
        TaskProgressColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("sync", total=100)

        assert proc.stdout is not None, "Popen was given stdout=PIPE"

        for line in proc.stdout:
            output_lines.append(line)
            match = _PROGRESS_RE.search(line)
            if match:
                progress.update(task, completed=int(match.group(1)))

    proc.wait()
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, rsync_cmd)

    return "".join(output_lines)


def _print_rsync_result(output: str) -> None:
    stats = _parse_rsync_stats(output)
    files = stats.get("files", 0)
    size = stats.get("size", "0 bytes")
    if files > 0:
        console.print(f"[green bold]✓ Synced {files} file{'s' if files != 1 else ''} ({size})[/green bold]")
    else:
        console.print("[green bold]✓ Already up to date[/green bold]")


@app.command(name="pull")
def pull(
    ip: str = typer.Argument(..., help="Server IP address."),
    user: str = typer.Option(
        "phoxtail",
        "--user",
        "-u",
        help="Deploy username on the server.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be synced without transferring",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show raw rsync output",
    ),
) -> None:
    """Sync media files from the remote server to the local environment.

    Exports media from the running web container via docker compose cp,
    then rsyncs it locally. Works for both volume and bind-mount deployments.
    """
    verify_server_identity(user, ip)

    local_media_dir = Path.cwd() / "media"
    local_media_dir.mkdir(parents=True, exist_ok=True)

    remote_host = f"{user}@{ip}"
    project_dir = f"~/{slugify(get_project_name())}"
    remote_staging = f"{project_dir}/{_STAGING_DIR}"

    try:
        # 1. Export media out of the container into a staging dir on the server.
        with console.status("[bold cyan]Exporting media from container...[/bold cyan]"):
            result = subprocess.run(
                [
                    "ssh",
                    *_SSH_MUX,
                    remote_host,
                    f"mkdir -p {remote_staging} && cd {project_dir} && "
                    f"docker compose cp web:/app/media/. {remote_staging}/",
                ],
                capture_output=True,
                text=True,
            )
        if result.returncode != 0:
            console.print(f"[red]Failed to export media from container:[/red] {result.stderr.strip()}")
            raise typer.Exit(1)

        # 2. Rsync staging dir → local media.
        remote_path = f"{remote_host}:{remote_staging}/"
        ssh_e = "ssh " + " ".join(_SSH_MUX)
        rsync_cmd = [
            "rsync",
            "-az",
            "-e",
            ssh_e,
            "--info=progress2",
            "--stats",
            remote_path,
            str(local_media_dir),
        ]

        if dry_run:
            rsync_cmd[4:4] = ["--dry-run", "--verbose"]
            rsync_cmd.remove("--info=progress2")
            console.print("[bold]Dry run:[/bold] showing what would be downloaded.\n")
            subprocess.run(rsync_cmd, check=True)
            console.print("\n[dim]No files were transferred. Remove --dry-run to sync.[/dim]")
        elif verbose:
            rsync_cmd[4:4] = ["--verbose", "--progress"]
            rsync_cmd.remove("--info=progress2")
            subprocess.run(rsync_cmd, check=True)
        else:
            output = _run_rsync_with_progress(rsync_cmd, label="Downloading media")
            _print_rsync_result(output)

    except subprocess.CalledProcessError:
        console.print("[red]Error syncing media[/red]")
        raise typer.Exit(1)
    finally:
        subprocess.run(
            ["ssh", *_SSH_MUX, remote_host, f"rm -rf {remote_staging}"],
            capture_output=True,
        )


@app.command(name="push")
def push(
    ip: str = typer.Argument(..., help="Server IP address."),
    user: str = typer.Option(
        "phoxtail",
        "--user",
        "-u",
        help="Deploy username on the server.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be synced without transferring",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show raw rsync output",
    ),
) -> None:
    """Push local media files to the remote server.

    Rsyncs local media to a staging directory on the server, then loads
    it into the running web container via docker compose cp. Works for
    both volume and bind-mount deployments.
    """
    verify_server_identity(user, ip)

    local_media_dir = Path.cwd() / "media"
    if not local_media_dir.exists() or not any(local_media_dir.iterdir()):
        console.print("[yellow]No local media files found.[/yellow]")
        raise typer.Exit(0)

    domain = read_deploy_env("DOMAIN")
    if not dry_run and not Confirm.ask(
        f"This will overwrite [bold]{get_project_name()}[/bold] media on "
        f"[bold]{ip}[/bold]{f' ({domain})' if domain else ''}. Continue?",
        default=False,
    ):
        raise typer.Exit(0)

    remote_host = f"{user}@{ip}"
    project_dir = f"~/{slugify(get_project_name())}"
    remote_staging = f"{project_dir}/{_STAGING_DIR}"

    try:
        result = subprocess.run(
            ["ssh", *_SSH_MUX, remote_host, f"mkdir -p {remote_staging}"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            console.print(f"[red]Failed to create staging directory:[/red] {result.stderr.strip()}")
            raise typer.Exit(1)

        # For dry-run, populate staging with the server's current media so
        # rsync reports the real delta rather than listing every local file as new.
        if dry_run:
            with console.status("[bold cyan]Exporting server media for comparison...[/bold cyan]"):
                result = subprocess.run(
                    [
                        "ssh",
                        *_SSH_MUX,
                        remote_host,
                        f"cd {project_dir} && docker compose cp web:/app/media/. {remote_staging}/",
                    ],
                    capture_output=True,
                    text=True,
                )
            if result.returncode != 0:
                console.print(f"[red]Failed to export server media:[/red] {result.stderr.strip()}")
                raise typer.Exit(1)

        # 1. Rsync local media → staging dir on server.
        remote_path = f"{remote_host}:{remote_staging}/"
        ssh_e = "ssh " + " ".join(_SSH_MUX)
        rsync_cmd = [
            "rsync",
            "-az",
            "-e",
            ssh_e,
            "--info=progress2",
            "--stats",
            str(local_media_dir) + "/",
            remote_path,
        ]

        if dry_run:
            rsync_cmd[4:4] = ["--dry-run", "--verbose"]
            rsync_cmd.remove("--info=progress2")
            console.print("[bold]Dry run:[/bold] showing what would be uploaded.\n")
            subprocess.run(rsync_cmd, check=True)
            console.print("\n[dim]No files were transferred. Remove --dry-run to push.[/dim]")
            return
        elif verbose:
            rsync_cmd[4:4] = ["--verbose", "--progress"]
            rsync_cmd.remove("--info=progress2")
            subprocess.run(rsync_cmd, check=True)
        else:
            output = _run_rsync_with_progress(rsync_cmd, label="Uploading media")
            _print_rsync_result(output)

        # 2. Load staging dir into the container.
        with console.status("[bold cyan]Loading media into container...[/bold cyan]"):
            result = subprocess.run(
                [
                    "ssh",
                    *_SSH_MUX,
                    remote_host,
                    f"cd {project_dir} && "
                    f"docker compose cp {remote_staging}/. web:/app/media/ && "
                    f"docker compose exec -u root web chown -R 1000:1000 /app/media",
                ],
                capture_output=True,
                text=True,
            )
        if result.returncode != 0:
            console.print(f"[red]Failed to load media into container:[/red] {result.stderr.strip()}")
            raise typer.Exit(1)

        console.print("[green bold]✓ Media pushed to server[/green bold]")

    except subprocess.CalledProcessError:
        console.print("[red]Error pushing media[/red]")
        raise typer.Exit(1)
    finally:
        subprocess.run(
            ["ssh", *_SSH_MUX, remote_host, f"rm -rf {remote_staging}"],
            capture_output=True,
        )
