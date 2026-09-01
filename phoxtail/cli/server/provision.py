"""server provision — interactively provision a new server on a cloud provider."""

import os
import time
from typing import TypedDict, Unpack

import questionary
import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel

from phoxtail.cli.server.providers.base import (
    Image,
    Location,
    Provider,
    ProviderError,
    ServerSpec,
    ServerType,
    SSHKey,
)
from phoxtail.cli.server.providers.hetzner import HetznerProvider
from phoxtail.cli.server.providers.linode import LinodeProvider
from phoxtail.cli.server.utils import (
    fmt_memory,
    fmt_price,
    forget_host_key,
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

# Provider registry — order determines display order in the picker
_PROVIDERS: list[type[Provider]] = [HetznerProvider, LinodeProvider]

# OS flavours to show (in display order); others are still available but listed after
_PREFERRED_FLAVOURS = ["ubuntu", "debian", "fedora", "centos", "rocky", "alma"]


# ------------------------------------------------------------------
# Summary panel
# ------------------------------------------------------------------


class _Selections(TypedDict, total=False):
    """The wizard's accumulated answers.

    Mirrors the keywords of :func:`_summary_panel`; every key is optional
    because the panel is redrawn after each step with only what has been
    answered so far.
    """

    provider_name: str | None
    architecture: str | None
    location: Location | None
    server_type: ServerType | None
    image: Image | None
    ssh_keys: list[SSHKey] | None
    name: str | None
    deploy_user: str | None
    currency: str


def _summary_panel(
    *,
    provider_name: str | None = None,
    architecture: str | None = None,
    location: Location | None = None,
    server_type: ServerType | None = None,
    image: Image | None = None,
    ssh_keys: list[SSHKey] | None = None,
    name: str | None = None,
    deploy_user: str | None = None,
    currency: str = "$",
) -> Panel:
    """Build a panel showing current wizard selections."""
    rows = []

    if provider_name:
        rows.append(f"  [dim]Provider:[/dim]      {provider_name}")
    if architecture:
        rows.append(f"  [dim]Architecture:[/dim]  {architecture}")
    if location:
        rows.append(
            f"  [dim]Location:[/dim]      {location.description}, {location.country}  [dim]({location.name})[/dim]"
        )
    if server_type:
        rows.append(
            f"  [dim]Server type:[/dim]  {server_type.name}"
            f"  •  {server_type.cores} vCPU"
            f"  •  {fmt_memory(server_type.memory)}"
            f"  •  {server_type.disk} GB SSD"
            f"  •  {fmt_price(server_type.price_monthly, currency)}"
        )
    if image:
        rows.append(f"  [dim]OS image:[/dim]      {image.os_flavor} {image.os_version or ''}")
    if ssh_keys is not None:
        if ssh_keys:
            names = ", ".join(k.name for k in ssh_keys)
            rows.append(f"  [dim]SSH keys:[/dim]      {names}")
        else:
            rows.append("  [dim]SSH keys:[/dim]      none  [dim](root password will be set)[/dim]")
    if deploy_user:
        rows.append(f"  [dim]Deploy user:[/dim]   {deploy_user}  [dim](root SSH will be disabled)[/dim]")
    if name:
        rows.append(f"  [dim]Server name:[/dim]   {name}")

    return Panel(
        "\n".join(rows) if rows else "  [dim](no selections yet)[/dim]",
        title="[bold cyan]Server Configuration[/bold cyan]",
        border_style="cyan",
        expand=False,
    )


def _clear_and_show(**kwargs: Unpack[_Selections]) -> None:
    """Clear the terminal and redraw the summary panel."""
    console.clear()
    console.print()
    console.print(_summary_panel(**kwargs))
    console.print()


# ------------------------------------------------------------------
# Wizard steps
# ------------------------------------------------------------------


def _ask_provider() -> type[Provider] | None:
    choices = [questionary.Choice(title=cls.display_name, value=cls) for cls in _PROVIDERS]
    return questionary.select("Cloud provider:", choices=choices).ask()


def _ask_architecture(architectures: tuple[str, ...]) -> str | None:
    choices = [
        questionary.Choice(title=_ARCH_LABELS[arch], value=arch) for arch in architectures if arch in _ARCH_LABELS
    ]
    return questionary.select(
        "Architecture:",
        choices=choices,
        default=architectures[0],
    ).ask()


def _ask_location(locations: list[Location]) -> Location | None:
    sorted_locs = sorted(locations, key=lambda loc: (loc.country, loc.city))

    choices = [
        questionary.Choice(
            title=(f"{loc.name:<10}  {loc.description:<28}  {loc.city}, {loc.country}"),
            value=loc,
        )
        for loc in sorted_locs
    ]

    return questionary.select("Location:", choices=choices).ask()


def _ask_server_type(
    server_types: list[ServerType],
    location_name: str,
    *,
    currency: str = "$",
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
        choices.append(questionary.Separator("── Shared vCPU ───────────────────────────────"))
        for st in shared:
            choices.append(
                questionary.Choice(
                    title=(
                        f"{st.name:<12}  "
                        f"{st.cores:>2} vCPU  "
                        f"{fmt_memory(st.memory):<8}  "
                        f"{st.disk:>4} GB SSD  "
                        f"{fmt_price(st.price_monthly, currency):>12}"
                    ),
                    value=st,
                )
            )
    if dedicated:
        choices.append(questionary.Separator("── Dedicated vCPU ────────────────────────────"))
        for st in dedicated:
            choices.append(
                questionary.Choice(
                    title=(
                        f"{st.name:<12}  "
                        f"{st.cores:>2} vCPU  "
                        f"{fmt_memory(st.memory):<8}  "
                        f"{st.disk:>4} GB SSD  "
                        f"{fmt_price(st.price_monthly, currency):>12}"
                    ),
                    value=st,
                )
            )

    if not choices:
        console.print(f"[red]No server types available at {location_name}.[/red]")
        return None

    # Default to cheapest shared option
    default = shared[0] if shared else (dedicated[0] if dedicated else None)

    # questionary matches `default` against the choices' values as well as
    # against Choice objects, so a bare value is valid — its own annotation
    # is narrower than what it accepts.
    return questionary.select("Server type:", choices=choices, default=default).ask()  # type: ignore[arg-type]


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
                    title=(f"{img.os_flavor:<14}  {img.os_version or '':>8}    ({img.name})"),
                    value=img,
                )
            )

    if not choices:
        console.print("[red]No OS images available.[/red]")
        return None

    # Default to ubuntu latest
    ubuntu_imgs = sorted(flavors.get("ubuntu", []), key=lambda i: i.os_version or "", reverse=True)
    default = ubuntu_imgs[0] if ubuntu_imgs else None

    # questionary matches `default` against the choices' values as well as
    # against Choice objects, so a bare value is valid — its own annotation
    # is narrower than what it accepts.
    return questionary.select("OS image:", choices=choices, default=default).ask()  # type: ignore[arg-type]


def _ask_ssh_keys(ssh_keys: list[SSHKey]) -> list[SSHKey] | None:
    if not ssh_keys:
        console.print(
            "  [yellow]No SSH keys found in this cloud account.[/yellow]\n"
            "  [dim]A root password will be provided after server creation.[/dim]\n"
        )
        return []

    choices = [
        questionary.Choice(
            title=f"{key.name:<30}  {key.fingerprint[:32]}…" if key.fingerprint else key.name,
            value=key,
        )
        for key in ssh_keys
    ]
    return questionary.checkbox(
        "SSH keys  (space to select, enter to confirm):",
        choices=choices,
    ).ask()


def _ask_server_name(default: str, validator: object) -> str | None:
    return questionary.text(
        "Server name:",
        default=default,
        validate=validator,
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


def _resolve_token(token: str | None, *, token_env_var: str, provider_name: str) -> str | None:
    if token:
        return token
    env = os.environ.get(token_env_var)
    if env:
        return env
    console.print()
    console.print(f"  [dim]Tip: set [bold]{token_env_var}[/bold] to skip this prompt.[/dim]\n")
    return questionary.password(f"{provider_name} API token:").ask()


def _default_server_name() -> str:
    """Return a hostname-safe default from phoxtail.toml project name, or empty string."""
    try:
        from phoxtail.cli.utils.config import find_config_file, load_config

        if find_config_file():
            name = load_config().get("project", {}).get("name", "")
            return name.replace("_", "-").lower()
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
        help="Cloud provider API token. Defaults to HETZNER_TOKEN or LINODE_TOKEN env var.",
        show_default=False,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show the configuration that would be used without creating anything.",
    ),
) -> None:
    """Interactively provision a new server on Hetzner Cloud or Linode.

    Walks through provider, location, server type, OS image, and SSH key
    selection, then creates the server and waits for it to be ready.

    Examples:
        phoxtail server provision
        phoxtail server provision --token <token>
        phoxtail server provision --dry-run
    """
    try:
        # --- Provider ---
        provider_class = _ask_provider()
        if provider_class is None:
            raise typer.Exit(0)

        api_token = _resolve_token(
            token,
            token_env_var=provider_class.token_env_var,
            provider_name=provider_class.display_name,
        )
        if not api_token:
            console.print("[red]Error:[/red] No API token provided.")
            raise typer.Exit(1)

        provider = provider_class(api_token)
        currency = provider_class.currency

        # Validate token + fetch data that doesn't depend on location/arch
        try:
            with console.status("[bold cyan]Connecting...[/bold cyan]"):
                locations = provider.list_locations()
                ssh_keys = provider.list_ssh_keys()
        except ProviderError as e:
            console.print(f"[red]Error:[/red] {escape(str(e))}")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Connection error:[/red] {e}")
            raise typer.Exit(1)

        console.print()

        # --- Architecture (skip when provider only offers one) ---
        if len(provider_class.architectures) > 1:
            architecture = _ask_architecture(provider_class.architectures)
            if architecture is None:
                raise typer.Exit(0)
        else:
            architecture = provider_class.architectures[0]

        _clear_and_show(
            provider_name=provider_class.display_name,
            architecture=architecture,
            currency=currency,
        )

        # --- Location ---
        location = _ask_location(locations)
        if location is None:
            raise typer.Exit(0)

        _clear_and_show(
            provider_name=provider_class.display_name,
            architecture=architecture,
            location=location,
            currency=currency,
        )

        # --- Server types (fetched after location is known) ---
        try:
            with console.status("[bold cyan]Fetching server types...[/bold cyan]"):
                all_types = provider.list_server_types(location=location.name)
        except ProviderError as e:
            console.print(f"[red]Error:[/red] {escape(str(e))}")
            raise typer.Exit(1)

        arch_types = [st for st in all_types if st.architecture == architecture]
        server_type = _ask_server_type(arch_types, location.name, currency=currency)
        if server_type is None:
            raise typer.Exit(0)

        _clear_and_show(
            provider_name=provider_class.display_name,
            architecture=architecture,
            location=location,
            server_type=server_type,
            currency=currency,
        )

        # --- OS Images (fetched after arch is known) ---
        try:
            with console.status("[bold cyan]Fetching OS images...[/bold cyan]"):
                images = provider.list_images(architecture=architecture)
        except ProviderError as e:
            console.print(f"[red]Error:[/red] {escape(str(e))}")
            raise typer.Exit(1)

        image = _ask_image(images)
        if image is None:
            raise typer.Exit(0)

        # --- Cloud-init gating ---
        # Bootstrap requires both the location to support the metadata service
        # AND the image to have cloud-init installed. Warn loudly when either
        # is missing so the user isn't surprised by a bare server.
        can_bootstrap = location.metadata_support and image.cloud_init
        if not can_bootstrap:
            console.print()
            console.print(
                "  [yellow]Warning:[/yellow] This location/image combination does not support\n"
                "  cloud-init. Docker and security hardening will [bold]not[/bold] be\n"
                "  applied automatically — you will need to set up the server manually.\n"
            )

        _clear_and_show(
            provider_name=provider_class.display_name,
            architecture=architecture,
            location=location,
            server_type=server_type,
            image=image,
            currency=currency,
        )

        # --- SSH Keys ---
        selected_keys = _ask_ssh_keys(ssh_keys)
        if selected_keys is None:
            raise typer.Exit(0)

        _clear_and_show(
            provider_name=provider_class.display_name,
            architecture=architecture,
            location=location,
            server_type=server_type,
            image=image,
            ssh_keys=selected_keys,
            currency=currency,
        )

        # --- Deploy username ---
        deploy_user = _ask_deploy_user()
        if deploy_user is None:
            raise typer.Exit(0)
        deploy_user = deploy_user.strip()

        _clear_and_show(
            provider_name=provider_class.display_name,
            architecture=architecture,
            location=location,
            server_type=server_type,
            image=image,
            ssh_keys=selected_keys,
            deploy_user=deploy_user,
            currency=currency,
        )

        # --- Server name ---
        default_name = _default_server_name()
        server_name = _ask_server_name(default_name, provider.validate_server_name)
        if server_name is None:
            raise typer.Exit(0)
        server_name = server_name.strip()

        # --- Final summary ---
        _clear_and_show(
            provider_name=provider_class.display_name,
            architecture=architecture,
            location=location,
            server_type=server_type,
            image=image,
            ssh_keys=selected_keys,
            deploy_user=deploy_user,
            name=server_name,
            currency=currency,
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

        # Render cloud-init bootstrap (Docker + uv + hardening)
        user_data: str | None = None
        if selected_keys and can_bootstrap:
            user_data = render_bootstrap(deploy_user, selected_keys)
        elif selected_keys and not can_bootstrap:
            console.print(
                "  [yellow]Warning:[/yellow] Skipping cloud-init bootstrap (not supported by this location/image).\n"
            )
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
            ssh_public_keys=[k.public_key for k in selected_keys if k.public_key],
            user_data=user_data,
        )

        console.print()
        try:
            with console.status("[bold cyan]Creating server...[/bold cyan]"):
                server = provider.create_server(spec)
        except ProviderError as e:
            console.print(f"[red]Error creating server:[/red] {escape(str(e))}")
            raise typer.Exit(1)

        # --- Wait for action (server OS installed and running) ---
        if server.action_id:
            with console.status("[bold cyan]Waiting for server to be ready...[/bold cyan]"):
                provisioned = False
                for _ in range(90):  # up to 3 minutes
                    time.sleep(2)
                    try:
                        status = provider.get_action_status(server.action_id)
                    except ProviderError:
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
                        "waiting for server to be ready. "
                        "The server may still be provisioning.\n"
                        "  Check your cloud provider's console."
                    )

        # --- Wait for cloud-init bootstrap ---
        if user_data and server.ipv4:
            # This IP may have belonged to someone else's server yesterday.
            # The stale key would make every SSH attempt below fail closed.
            forget_host_key(server.ipv4)
            console.print()
            console.print("[bold cyan]Waiting for cloud-init to finish (Docker, uv, hardening)...[/bold cyan]\n")
            cloud_init_ok, cloud_init_detail = wait_for_cloud_init(deploy_user, server.ipv4)
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
                # The server exists either way, so this is a warning, not an
                # exit — but it must not read as success.
                console.print(
                    Panel(
                        escape(cloud_init_detail),
                        title="cloud-init",
                        border_style="red",
                        expand=False,
                    )
                )
                console.print()
                bootstrap_note = (
                    "\n\n  [red]Cloud-init did not finish "
                    "cleanly — Docker may be missing.[/red]\n"
                    f"  Inspect the full log:\n"
                    f"  [cyan]ssh {deploy_user}@{server.ipv4} "
                    f"'sudo cat /var/log/cloud-init-output.log'[/cyan]"
                )
        else:
            bootstrap_note = ""
            cloud_init_ok = True

        # Root password note (shown when no SSH keys were provided)
        root_pass_note = ""
        if server.root_password:
            root_pass_note = (
                f"\n\n  [dim]Root password:[/dim]  [bold]{server.root_password}[/bold]"
                "\n  [dim](save this — it will not be shown again)[/dim]"
            )

        # --- Done ---
        headline = (
            f"[green]Server '{server.name}' is ready![/green]"
            if cloud_init_ok
            else f"[yellow]Server '{server.name}' was created, but its bootstrap failed.[/yellow]"
        )
        console.print(
            Panel(
                f"{headline}\n\n"
                f"  [dim]IPv4:[/dim]  "
                f"[bold]{server.ipv4 or 'N/A'}[/bold]\n"
                f"  [dim]IPv6:[/dim]  "
                f"[bold]{server.ipv6 or 'N/A'}[/bold]" + root_pass_note + bootstrap_note,
                border_style="green" if cloud_init_ok else "yellow",
                expand=False,
            )
        )

    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(0)
