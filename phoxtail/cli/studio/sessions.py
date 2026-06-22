"""``phoxtail studio sessions`` — manage editing sessions."""

from __future__ import annotations

import typer
from rich.console import Console

from phoxtail.cli.studio import client, format, session
from phoxtail.cli.studio._session_resolve import resolve_session_id

app = typer.Typer(help="Manage editing sessions.")
console = Console()


@app.command("list")
def sessions_list(
    json_output: bool = typer.Option(False, "--json", help="Emit raw JSON instead of a Rich table."),
) -> None:
    """List active editing sessions."""
    active = session.list_sessions()
    if json_output:
        client.emit_json({"sessions": active})
    else:
        format.render_sessions(active, console)


@app.command("start")
def sessions_start(
    variant_id: int = typer.Argument(..., help="Variant ID (from `phoxtail studio list variants`)."),
) -> None:
    """Start a new editing session on a variant.

    Creates a working copy under ``.phoxtail/studio/sessions/<session-id>/``
    with the variant's HTML, CSS, and JavaScript as editable files, plus a
    rendered context briefing as ``context.md``.
    """
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader

    from phoxtail.cli.studio import client as _client

    _TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "studio"
    _jinja_env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        keep_trailing_newline=True,
    )

    variant_data, etag = _client.get_variant_by_id(variant_id)

    session_id = str(variant_data["id"])
    if session.session_exists(session_id):
        sdir = session.session_dir(session_id)
        console.print(
            f"[red]Error:[/red] a session for variant [bold]{variant_id}[/bold] "
            f"is already open at {sdir}\n"
            "  Run [bold]phoxtail studio sessions discard[/bold] first, "
            "or commit it with [bold]phoxtail studio sessions commit[/bold]."
        )
        raise typer.Exit(code=1)

    context_md = ""
    try:
        _collection = variant_data.get("collection") or {}
        data = _client.get_context(
            block_id=variant_data["block"]["id"],
            collection_id=_collection.get("id"),
        )
        jinja_template = _jinja_env.get_template("variant_design_context.md")
        context_md = jinja_template.render(**data)
    except Exception:
        pass

    sdir = session.create_session(
        session_id=session_id,
        variant_data=variant_data,
        context_md=context_md,
        template_used="context",
        etag=etag or "",
    )

    console.print(
        f"[green]Session started:[/green] [bold]{session_id}[/bold]\n"
        f"  [dim]Path:[/dim]    {sdir}\n"
        f"  [dim]Variant:[/dim] {variant_data['identifier']} "
        f"({variant_data['block']['identifier']})\n"
        f"  [dim]Files:[/dim]   template.html, style.css, script.js, "
        f"context.md"
    )


@app.command("get")
def sessions_get(
    session_ref: str | None = typer.Option(
        None,
        "--session",
        help="Session ID. Can be omitted when only one session is active.",
    ),
    path_only: bool = typer.Option(
        False,
        "--path",
        help="Print only the session directory path (useful for agent prompts).",
    ),
) -> None:
    """Show details of an active session, including its directory path."""
    session_id = resolve_session_id(session_ref)
    session_data = session.read_session(session_id)
    session_data["path"] = str(session.session_dir(session_id))

    if path_only:
        console.print(session_data["path"], highlight=False)
    else:
        format.render_session_detail(session_data, console)


@app.command("commit")
def sessions_commit(
    session_ref: str | None = typer.Option(
        None,
        "--session",
        help="Session ID to commit. Can be omitted when only one session is active.",
    ),
    message: str | None = typer.Option(
        None,
        "--message",
        "-m",
        help="Optional commit message for the session history.",
    ),
    clean: bool = typer.Option(
        False,
        "--clean",
        help="Remove the session directory after a successful commit.",
    ),
) -> None:
    """Write an active session's files back to the database.

    On success the session directory is kept unless --clean is passed.
    On conflict (412) or any other error the session is always preserved.
    """
    session_id = resolve_session_id(session_ref)
    session_data = session.read_session(session_id)
    variant_meta = session_data["variant"]
    etag = session_data.get("etag") or ""

    if not etag:
        console.print(
            "[red]Error:[/red] session has no stored ETag. This session "
            "was created before optimistic concurrency was wired; "
            "discard it and start a new one."
        )
        raise typer.Exit(code=1)

    if "id" not in variant_meta:
        console.print("[red]Error:[/red] session predates ID-based routing; discard it and start a new one.")
        raise typer.Exit(code=1)

    updated, status, new_etag = client.update_variant_by_id(
        variant_meta["id"],
        html=session_data["html"],
        css=session_data["css"],
        javascript=session_data["javascript"],
        etag=etag,
    )

    if status == 400:
        detail = updated.get("detail") or updated.get("message") or "validation error"
        console.print(f"[red]Error:[/red] server rejected the commit: {detail}")
        raise typer.Exit(code=1)

    if clean:
        session.discard_session(session_id)
    elif new_etag:
        session.update_session_etag(session_id, new_etag)

    suffix = f" [dim]({message})[/dim]" if message else ""
    kept = "" if clean else " [dim](session kept)[/dim]"
    console.print(
        f"[green]Committed[/green] session [bold]{session_id}[/bold] "
        f"-> variant [cyan]{updated['identifier']}[/cyan] "
        f"(block: {updated['block']['identifier']}){suffix}{kept}"
    )


@app.command("discard")
def sessions_discard(
    session_ref: str | None = typer.Option(
        None,
        "--session",
        help="Session ID to discard. Can be omitted when only one session is active.",
    ),
) -> None:
    """Drop a session without saving any changes."""
    session_id = resolve_session_id(session_ref)
    session.discard_session(session_id)
    console.print(f"[yellow]Discarded[/yellow] session [bold]{session_id}[/bold]")


@app.command("refresh")
def sessions_refresh(
    session_ref: str | None = typer.Option(
        None,
        "--session",
        help="Session ID to refresh. Can be omitted when only one session is active.",
    ),
) -> None:
    """Re-fetch the server ETag for a session without touching local files."""
    session_id = resolve_session_id(session_ref)
    session_data = session.read_session(session_id)
    variant_meta = session_data["variant"]

    if "id" not in variant_meta:
        console.print("[red]Error:[/red] session predates ID-based routing; discard it and start a new one.")
        raise typer.Exit(code=1)

    _, new_etag = client.get_variant_by_id(variant_meta["id"])

    if not new_etag:
        console.print("[red]Error:[/red] server returned no ETag for this variant.")
        raise typer.Exit(code=1)

    session.update_session_etag(session_id, new_etag)
    console.print(f"[green]Refreshed[/green] session [bold]{session_id}[/bold] ETag -> [dim]{new_etag}[/dim]")
