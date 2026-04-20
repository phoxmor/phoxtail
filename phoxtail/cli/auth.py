"""CLI commands for managing Phoxtail API credentials.

These commands read and write ``~/.phoxtail/credentials`` via
``phoxtail.cli.utils.credentials``. The host key for each entry is
derived from ``[studio] api_url`` in the project's ``phoxtail.toml`` so
a designer working on multiple projects gets per-project tokens without
managing the key by hand.
"""

from __future__ import annotations

import getpass
import os

import httpx
import typer
from rich.console import Console

from phoxtail.cli.utils import credentials
from phoxtail.cli.utils.config import get_api_base_url

API_PREFIX = "/api/streams/v1"

app = typer.Typer(help="Manage Phoxtail API credentials.")
console = Console()


def _resolve_base_url(host_option: str | None) -> str:
    if host_option:
        return host_option if "://" in host_option else f"http://{host_option}"
    return get_api_base_url()


def _mask(token: str) -> str:
    if len(token) >= 12:
        return f"{token[:8]}…{token[-4:]}"
    return "(set)"


@app.command("login")
def login(
    token: str | None = typer.Option(
        None, "--token", help="Token value. Prompted (hidden) if omitted."
    ),
    host: str | None = typer.Option(
        None,
        "--host",
        help="Override host key (defaults to the project's api_url host).",
    ),
    no_verify: bool = typer.Option(
        False, "--no-verify", help="Skip live verification against the API."
    ),
) -> None:
    """Store a Personal Access Token for the current project's API."""
    base_url = _resolve_base_url(host)
    host_key = credentials.host_for_url(base_url)

    if token is None:
        try:
            token = getpass.getpass(f"Phoxtail token for {host_key}: ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Aborted.[/yellow]")
            raise typer.Exit(code=1) from None
    token = token.strip()
    if not token:
        console.print("[red]Error:[/red] no token provided.")
        raise typer.Exit(code=1)

    if not no_verify:
        try:
            resp = httpx.get(
                f"{base_url.rstrip('/')}{API_PREFIX}/blocks/",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
                follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            console.print(
                f"[yellow]Warning:[/yellow] could not verify token "
                f"({exc.__class__.__name__}). Saving anyway."
            )
        else:
            if resp.status_code == 401:
                console.print("[red]Token rejected by the API (401). Not saved.[/red]")
                raise typer.Exit(code=1)
            if resp.status_code >= 400:
                console.print(
                    f"[yellow]Warning:[/yellow] verification returned "
                    f"HTTP {resp.status_code}. Saving anyway."
                )

    credentials.save_token(host_key, token)
    console.print(f"[green]Saved token for [bold]{host_key}[/bold].[/green]")


@app.command("status")
def status() -> None:
    """Show configured credentials (env var and stored hosts)."""
    env_value = os.environ.get(credentials.ENV_VAR, "")
    if env_value:
        console.print(
            f"[green]${credentials.ENV_VAR}[/green] is set "
            f"({_mask(env_value.strip())}) — this overrides the file."
        )
    else:
        console.print(f"[dim]${credentials.ENV_VAR} is not set.[/dim]")

    hosts = credentials.list_hosts()
    if not hosts:
        console.print(
            f"No tokens stored in [bold]{credentials.CREDENTIALS_FILE}[/bold]."
        )
    else:
        console.print(f"Stored in [bold]{credentials.CREDENTIALS_FILE}[/bold]:")
        for h in hosts:
            entry = credentials.get_entry(h) or {}
            token = str(entry.get("token", ""))
            console.print(f"  [bold]{h}[/bold]: {_mask(token)}")

    current = credentials.host_for_url(get_api_base_url())
    console.print(f"Current project host: [bold]{current}[/bold]")


@app.command("logout")
def logout(
    host: str | None = typer.Option(
        None,
        "--host",
        help="Override host key (defaults to the project's api_url host).",
    ),
) -> None:
    """Remove the stored token for a host."""
    base_url = _resolve_base_url(host)
    host_key = credentials.host_for_url(base_url)
    if credentials.delete_token(host_key):
        console.print(f"[green]Removed token for [bold]{host_key}[/bold].[/green]")
    else:
        console.print(f"[yellow]No token stored for {host_key}.[/yellow]")
