"""Nginx configuration file generation commands."""

from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt

from phoxtail.cli.utils.env import read_env_value
from phoxtail.cli.utils.templates import render_template

app = typer.Typer()
create_app = typer.Typer()
app.add_typer(create_app, name="create", help="Create nginx configuration files")
console = Console()


@create_app.command("initial")
def initial(
    output: Path = typer.Option(
        Path("nginx.conf"), "--output", "-o", help="Output file path"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing file"),
) -> None:
    """Create initial nginx.conf for SSL retrieval."""
    if output.exists() and not force:
        if not Confirm.ask(f"Overwrite {output}?", default=False):
            raise typer.Exit(0)

    content = render_template("nginx/initial.conf", {})
    output.write_text(content)

    console.print(f"[green]✓[/green] Initial nginx.conf created: [bold]{output}[/bold]")
    console.print("[dim]Purpose:[/dim] Let's Encrypt certificate retrieval")


@create_app.command("production")
def production(
    domain: str | None = typer.Option(None, "--domain", "-d"),
    output: Path = typer.Option(Path("nginx.conf"), "--output", "-o"),
    force: bool = typer.Option(False, "--force", "-f"),
    wildcard: bool = typer.Option(
        False, "--wildcard", "-w", help="Enable wildcard subdomains"
    ),
) -> None:
    """Create production nginx.conf with optional wildcard support."""
    if output.exists() and not force:
        if not Confirm.ask(f"Overwrite {output}?", default=False):
            raise typer.Exit(0)

    env_domain = read_env_value("DOMAIN")
    if domain is None:
        domain = (
            Prompt.ask("Domain name", default=env_domain)
            if env_domain
            else Prompt.ask("Domain name")
        )

    if not domain:
        console.print("[red]Error:[/red] Domain is required")
        raise typer.Exit(1)

    domain = domain.strip()

    if wildcard:
        server_name = f"{domain} .{domain}"
        redirect_target = "$host"
    else:
        server_name = f"{domain} www.{domain}"
        redirect_target = domain

    content = render_template(
        "nginx/production.conf",
        {
            "domain": domain,
            "server_name": server_name,
            "redirect_target": redirect_target,
            "wildcard": wildcard,
        },
    )
    output.write_text(content)

    console.print(
        f"[green]✓[/green] Production nginx.conf created: [bold]{output}[/bold]"
    )
    console.print(f"[dim]Domain:[/dim] {domain}")
    console.print("[dim]SSL:[/dim] TLS 1.2/1.3 with Let's Encrypt certificates")
    console.print("[dim]HTTP/2:[/dim] Enabled (with IPv6 resolver fix)")
    console.print("[dim]Gzip:[/dim] Enabled for text content")
    if wildcard:
        console.print("[dim]Redirects:[/dim] HTTP → HTTPS (preserves subdomain)")
        console.print(f"[yellow]Wildcard support enabled (.{domain})[/yellow]")
        console.print(
            "[dim]Note:[/dim] Wildcard certs require DNS-01 challenge, not HTTP-01"
        )
    else:
        console.print("[dim]Redirects:[/dim] HTTP → HTTPS, www → non-www")
