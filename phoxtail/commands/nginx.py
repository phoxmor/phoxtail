"""Nginx configuration file generation commands."""

from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt

from phoxtail.utils.env import read_env_value
from phoxtail.utils.templates import render_template

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

    console.print("\n[yellow]⚠[/yellow]  [bold]Next Steps:[/bold]")
    console.print("   1. Start your Docker services with this nginx.conf")
    console.print("   2. Run certbot to obtain SSL certificates:")
    console.print(
        "      [cyan]docker compose --profile ssl run"
        " certbot certonly --webroot \\[/cyan]"
    )
    console.print(
        "        [cyan]-w /var/www/certbot -d yourdomain.com"
        " -d www.yourdomain.com \\[/cyan]"
    )
    console.print(
        "        [cyan]--email your@email.com --agree-tos --no-eff-email[/cyan]"
    )
    console.print(
        "   3. After certificates are obtained, generate production nginx.conf:"
    )
    console.print("      [cyan]phoxtail nginx create production[/cyan]")
    console.print("   4. Reload nginx to use the new configuration:")
    console.print("      [cyan]docker compose exec nginx nginx -s reload[/cyan]")


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

    console.print("\n[yellow]⚠[/yellow]  [bold]Next Steps:[/bold]")
    console.print("   1. Test configuration:")
    console.print("      [cyan]docker compose exec nginx nginx -t[/cyan]")
    console.print("   2. Reload nginx to apply changes:")
    console.print("      [cyan]docker compose exec nginx nginx -s reload[/cyan]")
