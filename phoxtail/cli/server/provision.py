"""server provision — interactively provision a new server on Hetzner Cloud."""

import os
import time

import questionary
import typer
from rich.console import Console
from rich.panel import Panel

from phoxtail.cli.server.providers.base import (
    Image,
    Location,
    ServerSpec,
    ServerType,
    SSHKey,
)
from phoxtail.cli.server.providers.hetzner import (
    HetznerError,
    HetznerProvider,
)
from phoxtail.cli.server.utils import (
    fmt_memory,
    fmt_price,
    price_key,
    render_bootstrap,
    wait_for_cloud_init,
)

console = Console()

# Architecture choices shown to the user
_ARCH_LABELS = {
    "x86": "x86 (Intel/AMD)  — most compatible",
    "arm": "arm64 (Ampere)   — lower cost on some types",
}

# OS flavours to show (in display order); others are still available but listed after
_PREFERRED_FLAVOURS = ["ubuntu", "debian", "fedora", "centos", "rocky", "alma"]


# ------------------------------------------------------------------
# Summary panel
# ------------------------------------------------------------------


def _summary_panel(
    *,
    architecture: str | None = None,
    location: Location | None = None,
    server_type: ServerType | None = None,
    image: Image | None = None,
    ssh_keys: list[SSHKey] | None = None,
    name: str | None = None,
    deploy_user: str | None = None,
) -> Panel:
    """Build a panel showing current wizard selections."""
    rows = []

    if architecture:
        rows.append(f"  [dim]Architecture:[/dim]  {architecture}")
    if location:
        rows.append(
            f"  [dim]Location:[/dim]      "
            f"{location.description}, {location.country}"
            f"  [dim]({location.name})[/dim]"
        )
    if server_type:
        rows.append(
            f"  [dim]Server type:[/dim]  {server_type.name}"
            f"  •  {server_type.cores} vCPU"
            f"  •  {fmt_memory(server_type.memory)}"
            f"  •  {server_type.disk} GB SSD"
            f"  •  {fmt_price(server_type.price_monthly)}"
        )
    if image:
        rows.append(
            f"  [dim]OS image:[/dim]      {image.os_flavor} {image.os_version or ''}"
        )
    if ssh_keys is not None:
        if ssh_keys:
            names = ", ".join(k.name for k in ssh_keys)
            rows.append(f"  [dim]SSH keys:[/dim]      {names}")
        else:
            rows.append(
                "  [dim]SSH keys:[/dim]      none"
                "  [dim](root password will be set)[/dim]"
            )
    if deploy_user:
        rows.append(
            f"  [dim]Deploy user:[/dim]   {deploy_user}"
            f"  [dim](root SSH will be disabled)[/dim]"
        )
    if name:
        rows.append(f"  [dim]Server name:[/dim]   {name}")

    return Panel(
        "\n".join(rows) if rows else "  [dim](no selections yet)[/dim]",
        title="[bold cyan]Server Configuration[/bold cyan]",
        border_style="cyan",
        expand=False,
    )


def _clear_and_show(**kwargs: object) -> None:
    """Clear the terminal and redraw the summary panel."""
    console.clear()
    console.print()
    console.print(_summary_panel(**kwargs))
    console.print()


# ------------------------------------------------------------------
# Wizard steps
# ------------------------------------------------------------------


def _ask_architecture() -> str | None:
    return questionary.select(
        "Architecture:",
        choices=[
            questionary.Choice(title=label, value=arch)
            for arch, label in _ARCH_LABELS.items()
        ],
        default="x86",
    ).ask()


def _ask_location(locations: list[Location]) -> Location | None:
    sorted_locs = sorted(
        locations,
        key=lambda loc: (loc.country, loc.city),
    )

    choices = [
        questionary.Choice(
            title=(f"{loc.name:<6}  {loc.description:<24}  {loc.city}, {loc.country}"),
            value=loc,
        )
        for loc in sorted_locs
    ]

    return questionary.select(
        "Location:",
        choices=choices,
    ).ask()


def _ask_server_type(
    server_types: list[ServerType], location_name: str
) -> ServerType | None:
    shared = sorted(
        [st for st in server_types if st.cpu_type == "shared"],
        key=lambda t: price_key(t.price_monthly),
    )
    dedicated = sorted(
        [st for st in server_types if st.cpu_type == "dedicated"],
        key=lambda t: price_key(t.price_monthly),
    )

    choices: list = []
    if shared:
        choices.append(
            questionary.Separator("── Shared vCPU ───────────────────────────────")
        )
        for st in shared:
            choices.append(
                questionary.Choice(
                    title=(
                        f"{st.name:<8}  "
                        f"{st.cores:>2} vCPU  "
                        f"{fmt_memory(st.memory):<7}  "
                        f"{st.disk:>4} GB SSD  "
                        f"{fmt_price(st.price_monthly):>12}"
                    ),
                    value=st,
                )
            )
    if dedicated:
        choices.append(
            questionary.Separator("── Dedicated vCPU ────────────────────────────")
        )
        for st in dedicated:
            choices.append(
                questionary.Choice(
                    title=(
                        f"{st.name:<8}  "
                        f"{st.cores:>2} vCPU  "
                        f"{fmt_memory(st.memory):<7}  "
                        f"{st.disk:>4} GB SSD  "
                        f"{fmt_price(st.price_monthly):>12}"
                    ),
                    value=st,
                )
            )

    if not choices:
        console.print(f"[red]No server types available at {location_name}.[/red]")
        return None

    # Default to CX22/CPX22 or cheapest
    default = next(
        (st for st in shared if st.name.lower() in ("cx22", "cpx22")),
        shared[0] if shared else (dedicated[0] if dedicated else None),
    )

    return questionary.select("Server type:", choices=choices, default=default).ask()


def _ask_image(images: list[Image]) -> Image | None:
    # Group by os_flavor, sort versions descending within each flavor
    flavors: dict[str, list[Image]] = {}
    for img in images:
        flavors.setdefault(img.os_flavor, []).append(img)

    # Order: preferred flavors first, rest alphabetically
    ordered_flavors = [f for f in _PREFERRED_FLAVOURS if f in flavors]
    ordered_flavors += sorted(f for f in flavors if f not in _PREFERRED_FLAVOURS)

    choices: list = []
    for flavor in ordered_flavors:
        imgs = sorted(flavors[flavor], key=lambda i: i.os_version or "", reverse=True)
        for img in imgs:
            choices.append(
                questionary.Choice(
                    title=(
                        f"{img.os_flavor:<14}"
                        f"  {img.os_version or '':>8}"
                        f"    ({img.name})"
                    ),
                    value=img,
                )
            )

    if not choices:
        console.print("[red]No OS images available.[/red]")
        return None

    # Default to ubuntu latest
    ubuntu_imgs = sorted(
        flavors.get("ubuntu", []), key=lambda i: i.os_version or "", reverse=True
    )
    default = ubuntu_imgs[0] if ubuntu_imgs else None

    return questionary.select("OS image:", choices=choices, default=default).ask()


def _ask_ssh_keys(ssh_keys: list[SSHKey]) -> list[SSHKey] | None:
    if not ssh_keys:
        console.print(
            "  [yellow]No SSH keys found in this Hetzner project.[/yellow]\n"
            "  [dim]A root password will be provided after server creation.[/dim]\n"
        )
        return []

    choices = [
        questionary.Choice(
            title=f"{key.name:<30}  {key.fingerprint[:32]}…",
            value=key,
        )
        for key in ssh_keys
    ]
    return questionary.checkbox(
        "SSH keys  (space to select, enter to confirm):",
        choices=choices,
    ).ask()


def _ask_server_name(default: str) -> str | None:
    return questionary.text(
        "Server name:",
        default=default,
        validate=lambda v: True if v.strip() else "Server name cannot be empty.",
    ).ask()


def _ask_deploy_user() -> str | None:
    return questionary.text(
        "Deploy username:",
        default="phoxtail",
        instruction="(non-root user created on the server — root SSH will be disabled)",
        validate=lambda v: True if v.strip() else "Username cannot be empty.",
    ).ask()


# ------------------------------------------------------------------
# Token resolution
# ------------------------------------------------------------------


def _resolve_token(token: str | None) -> str | None:
    if token:
        return token
    env = os.environ.get("HETZNER_TOKEN")
    if env:
        return env
    console.print()
    console.print(
        "  [dim]Tip: set [bold]HETZNER_TOKEN[/bold] to skip this prompt.[/dim]\n"
    )
    return questionary.password("Hetzner API token:").ask()


def _default_server_name() -> str:
    """Return the project name from phoxtail.toml if available, else empty string."""
    try:
        from phoxtail.cli.utils.config import _find_config_file, load_config

        if _find_config_file():
            return load_config().get("project", {}).get("name", "")
    except Exception:
        pass
    return ""


# ------------------------------------------------------------------
# Command
# ------------------------------------------------------------------


def provision(
    token: str | None = typer.Option(
        None,
        "--token",
        envvar="HETZNER_TOKEN",
        help="Hetzner API token. Defaults to HETZNER_TOKEN env var.",
        show_default=False,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show the configuration that would be used without creating anything.",
    ),
) -> None:
    """Interactively provision a new server on Hetzner Cloud.

    Walks through location, server type, OS image, and SSH key selection —
    mirroring the Hetzner Cloud Console experience — then creates the server
    and waits for it to be ready.

    Examples:
        phoxtail server provision
        phoxtail server provision --token <token>
        phoxtail server provision --dry-run
    """
    api_token = _resolve_token(token)
    if not api_token:
        console.print("[red]Error:[/red] No API token provided.")
        raise typer.Exit(1)

    provider = HetznerProvider(api_token)

    # Validate token + fetch data that doesn't depend on location/arch
    try:
        with console.status("[bold cyan]Connecting to Hetzner Cloud...[/bold cyan]"):
            locations = provider.list_locations()
            ssh_keys = provider.list_ssh_keys()
    except HetznerError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Connection error:[/red] {e}")
        raise typer.Exit(1)

    console.print()

    try:
        # --- Architecture ---
        architecture = _ask_architecture()
        if architecture is None:
            raise typer.Exit(0)

        _clear_and_show(architecture=architecture)

        # --- Location ---
        location = _ask_location(locations)
        if location is None:
            raise typer.Exit(0)

        _clear_and_show(
            architecture=architecture,
            location=location,
        )

        # --- Server types (fetched after location is known) ---
        try:
            with console.status("[bold cyan]Fetching server types...[/bold cyan]"):
                all_types = provider.list_server_types(
                    location=location.name,
                )
        except HetznerError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        arch_types = [st for st in all_types if st.architecture == architecture]
        server_type = _ask_server_type(arch_types, location.name)
        if server_type is None:
            raise typer.Exit(0)

        _clear_and_show(
            architecture=architecture,
            location=location,
            server_type=server_type,
        )

        # --- OS Images (fetched after arch is known) ---
        try:
            with console.status("[bold cyan]Fetching OS images...[/bold cyan]"):
                images = provider.list_images(
                    architecture=architecture,
                )
        except HetznerError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

        image = _ask_image(images)
        if image is None:
            raise typer.Exit(0)

        _clear_and_show(
            architecture=architecture,
            location=location,
            server_type=server_type,
            image=image,
        )

        # --- SSH Keys ---
        selected_keys = _ask_ssh_keys(ssh_keys)
        if selected_keys is None:
            raise typer.Exit(0)

        _clear_and_show(
            architecture=architecture,
            location=location,
            server_type=server_type,
            image=image,
            ssh_keys=selected_keys,
        )

        # --- Deploy username ---
        deploy_user = _ask_deploy_user()
        if deploy_user is None:
            raise typer.Exit(0)
        deploy_user = deploy_user.strip()

        _clear_and_show(
            architecture=architecture,
            location=location,
            server_type=server_type,
            image=image,
            ssh_keys=selected_keys,
            deploy_user=deploy_user,
        )

        # --- Server name ---
        default_name = _default_server_name()
        server_name = _ask_server_name(default_name)
        if server_name is None:
            raise typer.Exit(0)
        server_name = server_name.strip()

        # --- Final summary ---
        _clear_and_show(
            architecture=architecture,
            location=location,
            server_type=server_type,
            image=image,
            ssh_keys=selected_keys,
            deploy_user=deploy_user,
            name=server_name,
        )

        if dry_run:
            console.print(
                Panel(
                    "[yellow]Dry run — no server was created.[/yellow]",
                    border_style="yellow",
                    expand=False,
                )
            )
            return

        if not questionary.confirm("Create this server now?", default=True).ask():
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

        # Render cloud-init bootstrap (Docker + uv + phoxtail + hardening)
        user_data: str | None = None
        if selected_keys:
            user_data = render_bootstrap(deploy_user, selected_keys)
        else:
            console.print(
                "  [yellow]Warning:[/yellow] No SSH keys selected"
                " — cloud-init bootstrap will be skipped.\n"
                "  Docker and security hardening will not be"
                " applied automatically.\n"
            )

        # --- Create ---
        spec = ServerSpec(
            name=server_name,
            server_type=server_type.name,
            image=image.name,
            location=location.name,
            ssh_key_ids=[k.id for k in selected_keys],
            user_data=user_data,
        )

        console.print()
        try:
            with console.status("[bold cyan]Creating server...[/bold cyan]"):
                server = provider.create_server(spec)
        except HetznerError as e:
            console.print(f"[red]Error creating server:[/red] {e}")
            raise typer.Exit(1)

        # --- Wait for Hetzner action (server OS installed and running) ---
        if server.action_id:
            with console.status(
                "[bold cyan]Waiting for server to be ready...[/bold cyan]"
            ):
                provisioned = False
                for _ in range(90):  # up to 3 minutes
                    time.sleep(2)
                    try:
                        status = provider.get_action_status(server.action_id)
                    except HetznerError:
                        continue  # transient — keep polling
                    if status == "success":
                        provisioned = True
                        break
                    if status == "error":
                        console.print("[red]Server provisioning failed.[/red]")
                        raise typer.Exit(1)
                if not provisioned:
                    console.print(
                        "[yellow]Warning:[/yellow] Timed out "
                        "waiting for server action. "
                        "The server may still be provisioning.\n"
                        "  Check: https://console.hetzner.cloud"
                    )

        # --- Wait for cloud-init bootstrap ---
        if user_data and server.ipv4:
            console.print()
            console.print(
                "[bold cyan]Waiting for cloud-init to finish "
                "(Docker, uv, phoxtail, hardening)...[/bold cyan]\n"
            )
            cloud_init_ok = wait_for_cloud_init(deploy_user, server.ipv4)
            console.print()

            if cloud_init_ok:
                bootstrap_note = (
                    "\n\n  [green]Cloud-init completed "
                    "successfully.[/green]\n\n"
                    f"  [dim]Connect:[/dim]  "
                    f"[cyan]ssh {deploy_user}@{server.ipv4}"
                    f"[/cyan]\n"
                    f"  [dim]Next:[/dim]    "
                    f"[cyan]phoxtail server deploy "
                    f"{server.ipv4}[/cyan]"
                )
            else:
                bootstrap_note = (
                    "\n\n  [yellow]Cloud-init is still "
                    "running.[/yellow]\n"
                    f"  SSH in manually to check:\n"
                    f"  [cyan]ssh {deploy_user}@{server.ipv4}"
                    f"[/cyan]"
                )
        else:
            bootstrap_note = ""

        # --- Done ---
        console.print(
            Panel(
                f"[green]Server '{server.name}' is ready!"
                f"[/green]\n\n"
                f"  [dim]IPv4:[/dim]  "
                f"[bold]{server.ipv4 or 'N/A'}[/bold]\n"
                f"  [dim]IPv6:[/dim]  "
                f"[bold]{server.ipv6 or 'N/A'}[/bold]" + bootstrap_note,
                border_style="green",
                expand=False,
            )
        )

    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(0)
