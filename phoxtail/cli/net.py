"""The shared local network: one Traefik stack, many projects reachable by name."""

import json
import subprocess
import sys
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from phoxtail.cli.utils.config import (
    DEFAULT_API_BASE_URL,
    DEFAULTS,
    find_config_file,
    get_project_name,
    load_config,
    require_project,
    slugify,
)
from phoxtail.cli.utils.credentials import resolve_token
from phoxtail.cli.utils.docker import docker_env
from phoxtail.cli.utils.net import (
    NET_COMPOSE_FILE,
    NET_DIR,
    NETWORK_NAME,
    PROJECT_NET_FILE,
    SLUG_LABEL,
    Member,
    add_member,
    check_compose_version,
    ensure_network,
    is_wired,
    list_peers,
    net_stack_running,
    network_exists,
    read_members,
    remove_env_key,
    remove_env_list_value,
    remove_member,
    set_api_url,
    slug_in_use_elsewhere,
    upsert_env_list,
)
from phoxtail.cli.utils.templates import render_template

app = typer.Typer()
console = Console()


def _project_root() -> Path:
    """The directory holding phoxtail.toml — where attach/detach must write.

    ``find_config_file`` searches upward, so these commands work from a
    subdirectory too; anchoring every path here (rather than the cwd)
    keeps the fragment, ``.env`` and ``.gitignore`` edits landing next to
    the config they belong to.
    """
    config_path = find_config_file()
    assert config_path is not None, "call require_project() first"
    return config_path.parent


def _project_compose(member: Member, args: list[str]) -> int:
    """Run a compose command inside a member project, as typing it there would.

    ``cwd`` rather than ``--project-directory``: the project's ``.env`` (which
    carries ``COMPOSE_FILE``), its relative build contexts and its derived
    project name all resolve from the working directory, so running there
    reproduces the user's own invocation instead of approximating it.

    ``COMPOSE_FILE``/``COMPOSE_PROJECT_NAME`` are dropped from the inherited
    environment because a real environment variable outranks the ``.env``
    file. Exported in the caller's shell they describe *one* project, and
    would then be imposed on every other one here — overriding the very
    ``COMPOSE_FILE`` :func:`is_wired` just checked, or worse, starting each
    project's services under a single shared project name.
    """
    env = {k: v for k, v in docker_env().items() if k not in ("COMPOSE_FILE", "COMPOSE_PROJECT_NAME")}
    return subprocess.call(["docker", "compose", *args], cwd=str(member.root), env=env)


def _fan_out(args: list[str], *, require_wiring: bool, when_empty: str) -> bool:
    """Run one compose command in every attached project. True if all succeeded.

    Never aborts on the first failure: one project with a broken build must
    not strand the other five, so every member is attempted and the outcome
    is reported at the end.
    """
    members = read_members()
    if not members:
        console.print(when_empty)
        return True

    failures: list[str] = []
    skipped: list[str] = []
    for member in members:
        # Only starting is gated. A project whose .env lost COMPOSE_FILE would
        # come up from the base file alone, publish its own port 80 and fight
        # Traefik for it — worse than not starting. Stopping one is harmless.
        if require_wiring and not is_wired(member.root):
            console.print(
                f"  [yellow]skipped[/yellow] {member.slug} — .env no longer loads {PROJECT_NET_FILE}; "
                f"run [bold]phoxtail net attach[/bold] in {member.root}"
            )
            skipped.append(member.slug)
            continue

        console.print(f"  [dim]{member.slug}[/dim]")
        if _project_compose(member, args) != 0:
            console.print(f"  [red]failed[/red] {member.slug}")
            failures.append(member.slug)

    if skipped:
        console.print(f"  [yellow]skipped {len(skipped)} of {len(members)}:[/yellow] {', '.join(skipped)}")
    if failures:
        console.print(f"  [red]failed {len(failures)} of {len(members)}:[/red] {', '.join(failures)}")

    # Only real failures set the exit code. A skip is a standing config fault
    # that would otherwise make every future `net up` exit non-zero, long
    # after the router and every other project came up fine — loud in the
    # output is the right volume for it, not a failed command.
    return not failures


@app.command()
def up(
    projects: bool = typer.Option(True, "--projects/--no-projects", help="Also start every attached project."),
) -> None:
    """Start the shared local network, its Traefik router, and every attached project."""
    try:
        ensure_network()
    except (RuntimeError, FileNotFoundError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    NET_DIR.mkdir(parents=True, exist_ok=True)
    NET_COMPOSE_FILE.write_text(render_template("net/docker-compose.yaml", {"network": NETWORK_NAME}))

    cmd = ["docker", "compose", "-f", str(NET_COMPOSE_FILE), "up", "-d"]
    rc = subprocess.call(cmd, env=docker_env())
    if rc != 0:
        sys.exit(rc)
    console.print(f"[green]✓[/green] Shared net up on [bold]{NETWORK_NAME}[/bold]")

    if not projects:
        return

    # Router before projects: a project starting first would be routable only
    # once Traefik catches up, and no `--build` here — matching what the user
    # types by hand, rather than turning a first `net up` into a long build.
    console.print("\n[bold]Starting attached projects[/bold]")
    if not _fan_out(
        ["up", "-d"],
        require_wiring=True,
        when_empty="[dim]  none yet — run [/dim][bold]phoxtail net attach[/bold][dim] in a project.[/dim]",
    ):
        sys.exit(1)


@app.command()
def down(
    projects: bool = typer.Option(True, "--projects/--no-projects", help="Also stop every attached project."),
    remove: bool = typer.Option(
        False, "--remove", help="Remove the projects' containers instead of only stopping them."
    ),
) -> None:
    """Stop every attached project, then the Traefik router. Leaves the network in place."""
    ok = True
    if projects:
        console.print("[bold]Stopping attached projects[/bold]")
        # Projects first: taking the router down ahead of them would leave
        # every running project up but unroutable — the worst intermediate
        # state, and the one a user is most likely to hit Ctrl-C in.
        ok = _fan_out(
            ["down"] if remove else ["stop"],
            require_wiring=False,
            when_empty="[dim]  none attached[/dim]",
        )

    if not NET_COMPOSE_FILE.exists():
        console.print("[dim]The shared net is not set up — nothing more to stop.[/dim]")
        sys.exit(0 if ok else 1)

    cmd = ["docker", "compose", "-f", str(NET_COMPOSE_FILE), "down"]
    rc = subprocess.call(cmd, env=docker_env())
    sys.exit(rc if rc != 0 else (0 if ok else 1))


@app.command()
def status() -> None:
    """Show the shared net's state, and this project's attachment to it."""
    compose_file_state = "[green]present[/green]" if NET_COMPOSE_FILE.exists() else "[dim]not created[/dim]"
    network_state = "[green]present[/green]" if network_exists() else "[dim]absent[/dim]"
    traefik_state = "[green]running[/green]" if net_stack_running() else "[yellow]not running[/yellow]"

    console.print("[bold]Shared net[/bold]")
    console.print(f"  compose file: {compose_file_state} ({NET_COMPOSE_FILE})")
    console.print(f"  network:      {network_state} ({NETWORK_NAME})")
    console.print(f"  traefik:      {traefik_state}")

    if find_config_file() is None:
        return

    root = _project_root()
    slug = slugify(get_project_name())
    net_file = root / PROJECT_NET_FILE
    net_file_state = "[green]present[/green]" if net_file.exists() else "[dim]absent[/dim]"

    wired_state = "[green]wired[/green]" if is_wired(root) else "[dim]not wired[/dim]"

    console.print(f"\n[bold]This project[/bold] (slug: {slug})")
    console.print(f"  {PROJECT_NET_FILE}: {net_file_state}")
    console.print(f"  COMPOSE_FILE:  {wired_state} in .env")

    try:
        other = slug_in_use_elsewhere(slug, root)
    except (RuntimeError, FileNotFoundError):
        other = None  # status stays informative without Docker; attach is where this is fatal
    if other is not None:
        console.print(f"  [yellow]warning:[/yellow] slug also in use by another attached project at {other}")


@app.command()
def peers(
    json_output: bool = typer.Option(False, "--json", help="Print peers as a JSON array, for scripting."),
) -> None:
    """List every project attached to the shared net, and how to reach it."""
    # Two sources answering two questions: the members file says who is attached,
    # Docker says who is reachable. Merged only here, for display — merging
    # them in `list_peers` would let `resolve_peer` hand out an address that
    # silently loops back to the caller.
    members = read_members()
    live = {peer.slug: peer for peer in list_peers()}

    # slug, state, path, attached, address
    rows: list[tuple[str, str, Path | None, bool, str]] = []
    for member in members:
        peer = live.get(member.slug)
        if peer is None:
            state = "not created"
        elif peer.running:
            state = "running"
        else:
            state = "stopped"
        rows.append((member.slug, state, member.root, True, member.address))

    # A container can carry the slug label while its project is no longer
    # attached: `detach` edits files, and the label was stamped at container
    # creation. Showing it as detached explains a name that would otherwise
    # look like an unexplained peer — and it really is still routable while
    # it runs, which is why it cannot simply be hidden.
    attached_slugs = {member.slug for member in members}
    for slug, peer in sorted(live.items()):
        if slug not in attached_slugs:
            state = "detached" if peer.running else "detached, stopped"
            rows.append((slug, state, peer.working_dir, False, peer.address))

    if json_output:
        # Plain echo, not console.print: Rich fold-wraps long unbroken
        # tokens (a deep working_dir) with literal newlines, corrupting
        # the very output a parser is waiting on.
        typer.echo(
            json.dumps(
                [
                    {
                        "slug": slug,
                        "address": address,
                        "attached": attached,
                        "running": slug in live and live[slug].running,
                        "working_dir": str(root) if root else None,
                    }
                    for slug, _state, root, attached, address in rows
                ]
            )
        )
        return

    if not rows:
        console.print("[dim]No projects attached yet — run [bold]phoxtail net attach[/bold] in one.[/dim]")
        return

    here = slugify(get_project_name()) if find_config_file() is not None else None

    # No `address` column: it is always http://<slug>.localhost, so a column
    # would spend the terminal's width restating the first one — and it was
    # that width pressure truncating the slugs, the part you actually copy.
    # The slug carries the address as a terminal hyperlink instead, which
    # buys the click without the width; terminals without OSC 8 support just
    # render the slug, which is what the column said anyway.
    table = Table(box=box.SIMPLE, header_style="bold")
    table.add_column("slug", no_wrap=True)
    table.add_column("state", no_wrap=True)
    table.add_column("path", overflow="fold", style="dim")

    styles = {
        "running": "[green]running[/green]",
        "stopped": "[yellow]stopped[/yellow]",
        "not created": "[dim]not created[/dim]",
    }
    for slug, state, root, attached, address in rows:
        here_marker = " [dim](this project)[/dim]" if slug == here else ""
        slug_cell = f"[bold][link={address}]{slug}[/link][/bold]{here_marker}"
        table.add_row(
            slug_cell if attached else f"[dim]{slug}[/dim]{here_marker}",
            styles.get(state, f"[dim]{state}[/dim]"),
            str(root) if root else "unknown",
        )

    console.print(table)
    console.print(
        "[dim]Reachable at [/dim][bold]http://<slug>.localhost[/bold][dim] "
        "from the host and from inside any attached container — "
        "click a slug above to open it.[/dim]"
    )
    if any(not row[3] for row in rows):
        console.print(
            "[dim]Rows marked [/dim]detached[dim] are containers still carrying the net label from "
            "before they were detached; they clear on the next [/dim][bold]docker compose up -d[/bold][dim].[/dim]"
        )


@app.command()
def attach() -> None:
    """Attach this project to the shared net at <project>.localhost.

    Writes a phoxtail-owned docker-compose.net.yaml (never touches your
    own docker-compose.override.yml), and wires it into .env via
    COMPOSE_FILE. Safe to re-run.
    """
    require_project()
    config_path = find_config_file()
    root = _project_root()

    slug = slugify(get_project_name())
    if slug == slugify(DEFAULTS["project"]["name"]):
        console.print(
            "[red]Error:[/red] This project has no [bold]\\[project] name[/bold] set in phoxtail.toml "
            "(or it's set to the default). Set a unique project name before attaching to the net, "
            "otherwise it will collide with every other unnamed project."
        )
        raise typer.Exit(code=1)

    meets_min, raw_version = check_compose_version()
    if not meets_min:
        console.print(
            f"[red]Error:[/red] Docker Compose {raw_version} is too old for `net attach` "
            f"(need >= 2.24, for the compose 'ports: !reset []' directive). Please upgrade Docker."
        )
        raise typer.Exit(code=1)

    try:
        other = slug_in_use_elsewhere(slug, root)
        ensure_network()
    except (RuntimeError, FileNotFoundError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    if other is not None:
        console.print(
            f"[red]Error:[/red] Slug [bold]{slug}[/bold] is already attached to another project at "
            f"[bold]{other}[/bold]. Set a different, unique [project] name in phoxtail.toml."
        )
        raise typer.Exit(code=1)

    # The fragment re-addresses the base file's `mcp` service; a project
    # hatched before that service existed would make Compose fail with
    # "service mcp has neither an image nor a build context".
    base_compose = root / "docker-compose.yaml"
    if base_compose.exists() and "\n  mcp:" not in base_compose.read_text():
        console.print(
            "[yellow]Warning:[/yellow] docker-compose.yaml has no [bold]mcp[/bold] service "
            "(project hatched before the always-on MCP server). "
            "Re-render it with [bold]phoxtail docker create compose[/bold] or add the service by hand."
        )

    net_file = root / PROJECT_NET_FILE
    net_file.write_text(
        render_template(
            "net/docker-compose.net.yaml",
            {"slug": slug, "network": NETWORK_NAME, "slug_label": SLUG_LABEL},
        )
    )
    env_file = root / ".env"

    # Setting COMPOSE_FILE at all disables Compose's automatic override
    # pickup, so any override the project relies on (phoxtail bind-mounts,
    # extra services) must be carried into the list explicitly — both
    # spellings Compose itself would auto-load.
    compose_files = ["docker-compose.yaml"]
    for override in ("docker-compose.override.yml", "docker-compose.override.yaml"):
        if (root / override).exists():
            compose_files.append(override)
    compose_files.append(PROJECT_NET_FILE)

    # The net fragment must stay *last*: later files win, and it is the one
    # that releases the ports to Traefik. Dropping it before upserting means
    # a re-run re-appends it at the end — so re-running attach repairs a
    # list that gained an override file since, without disturbing entries
    # the user added by hand.
    remove_env_list_value(env_file, "COMPOSE_FILE", PROJECT_NET_FILE, ":")
    for f in compose_files:
        upsert_env_list(env_file, "COMPOSE_FILE", f, ":")

    hostname = f"{slug}.localhost"
    # Both hostnames, because this project answers to two names once attached:
    # `<slug>.localhost` (browser and sibling containers alike) and the bare
    # `<slug>` (the container-side alias). Django matches ALLOWED_HOSTS
    # exactly — the dotted entry does not cover the bare one — so a call
    # arriving under either name would 400 with DisallowedHost without both.
    upsert_env_list(env_file, "ALLOWED_HOSTS", hostname, ",")
    upsert_env_list(env_file, "ALLOWED_HOSTS", slug, ",")
    # `web` is not attachment state — it's how the mcp service addresses
    # the API from inside the project (newer env templates ship it). The
    # upsert here repairs older projects; detach deliberately leaves it,
    # because the mcp service needs it attached or not.
    upsert_env_list(env_file, "ALLOWED_HOSTS", "web", ",")
    upsert_env_list(env_file, "CSRF_TRUSTED_ORIGINS", f"http://{hostname}", ",")

    # While attached, port 80 belongs to Traefik, so the default
    # `http://localhost` api_url reaches Traefik under a Host header no router
    # claims and 404s. `detach` puts it back.
    set_api_url(config_path, f"http://{hostname}")
    load_config.cache_clear()

    gitignore = root / ".gitignore"
    if gitignore.exists():
        ignore_content = gitignore.read_text()
        if PROJECT_NET_FILE not in ignore_content and "docker-compose.*.yaml" not in ignore_content:
            with gitignore.open("a") as f:
                f.write(f"{PROJECT_NET_FILE}\n")

    # Recorded last, once nothing left can fail. `net up` fans out over this
    # file, so an entry must never outlive an attach the user was told did
    # not succeed — a project reported as failed that then starts anyway is
    # worse than one that has to be attached twice.
    add_member(root, slug)

    message = (
        f"[green]✓[/green] Attached — restart with [bold]docker compose up -d[/bold], "
        f"then visit [bold]http://{hostname}[/bold]"
    )
    if resolve_token(f"http://{hostname}") is None:
        message += (
            f"\n[yellow]  No token stored yet for [/yellow][bold]{hostname}[/bold]"
            f"[yellow] — run [/yellow][bold]phoxtail auth login[/bold][yellow] to store one.[/yellow]"
        )
    console.print(message)


@app.command()
def detach() -> None:
    """Detach this project from the shared net, reversing `attach`."""
    require_project()
    config_path = find_config_file()
    root = _project_root()

    slug = slugify(get_project_name())
    hostname = f"{slug}.localhost"

    net_file = root / PROJECT_NET_FILE
    if net_file.exists():
        net_file.unlink()

    # Membership ends here, not when the container is recreated. The slug
    # label lives on the existing container until the next `up`, so Docker
    # goes on reporting this project until then — the members file is what
    # makes `peers` and `net up` agree with the user's intent immediately.
    remove_member(root)

    env_file = root / ".env"
    remove_env_key(env_file, "COMPOSE_FILE")
    remove_env_list_value(env_file, "ALLOWED_HOSTS", hostname, ",")
    remove_env_list_value(env_file, "ALLOWED_HOSTS", slug, ",")
    # `web` stays: the always-on mcp service addresses the API by that
    # name whether or not the project is on the shared net.
    remove_env_list_value(env_file, "CSRF_TRUSTED_ORIGINS", f"http://{hostname}", ",")

    # Detached, the project publishes its own port 80 again, so the default
    # address is correct once more.
    set_api_url(config_path, DEFAULT_API_BASE_URL)
    load_config.cache_clear()

    console.print("[green]✓[/green] Detached — restart with [bold]docker compose up -d[/bold] to apply.")
