"""Environment file generation commands."""

import secrets
from pathlib import Path

import questionary
import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt

from phoxtail.cli.utils.config import get_project_name
from phoxtail.cli.utils.templates import render_template

app = typer.Typer()
console = Console()


def _generate_secret_key() -> str:
    """Generate a Django-compatible SECRET_KEY.

    Replicates Django's get_random_secret_key() implementation exactly.
    Returns a 50 character random string usable as a SECRET_KEY setting value.
    """
    chars = "abcdefghijklmnopqrstuvwxyz0123456789!@#%^&*(-_=+)"
    return "".join(secrets.choice(chars) for i in range(50))


def _generate_password() -> str:
    """Generate a cryptographically secure password using industry standard method.

    Uses secrets.token_urlsafe() which generates a URL-safe, base64-encoded
    random token. 32 bytes = 256 bits of entropy (43 characters when encoded).
    """
    return secrets.token_urlsafe(32)


def _prompt_common_config() -> dict:
    """Prompt for configuration shared between development and production."""
    console.print("[dim]Generating secure values...[/dim]")
    secret_key = _generate_secret_key()
    postgres_password = _generate_password()
    console.print("[green]✓[/green] Secure values generated\n")

    console.print("[bold]Project Configuration:[/bold]")
    default_name = get_project_name().replace("_", " ").title()
    site_name = Prompt.ask("Site name", default=default_name)

    console.print("\n[bold]Database Configuration:[/bold]")
    postgres_db = Prompt.ask("PostgreSQL database name", default="postgres")
    postgres_user = Prompt.ask("PostgreSQL username", default="postgres")

    use_auto_password = Confirm.ask(
        "Use auto-generated password? (recommended)",
        default=True,
    )
    if not use_auto_password:
        postgres_password = Prompt.ask("PostgreSQL password", password=True)

    console.print("\n[bold]Feature Flags:[/bold]")

    return {
        "secret_key": secret_key,
        "postgres_password": postgres_password,
        "site_name": site_name,
        "postgres_db": postgres_db,
        "postgres_user": postgres_user,
    }


def _prompt_development_env(output_file: Path) -> None:
    """Create a development .env file with interactive prompts."""
    console.print("\n[bold cyan]Creating Development Environment File[/bold cyan]\n")

    context = _prompt_common_config()
    context["allow_signup"] = Confirm.ask("Allow user signup?", default=True)

    content = render_template("env/development.env", context)
    output_file.write_text(content)
    console.print(f"\n[green]✓[/green] Environment file created: [bold]{output_file}[/bold]")


def _prompt_production_env(output_file: Path, server_ip: str | None = None) -> None:
    """Create a production .env file with interactive prompts."""
    console.print("\n[bold cyan]Creating Production Environment File[/bold cyan]\n")

    context = _prompt_common_config()

    console.print("\n[bold]Domain Configuration:[/bold]")
    domain = Prompt.ask("[red]*[/red] Domain name (e.g., example.com)")
    while not domain.strip():
        console.print("[red]Error:[/red] Domain is required for production")
        domain = Prompt.ask("[red]*[/red] Domain name (e.g., example.com)")

    domain_email = Prompt.ask("[red]*[/red] Domain email")
    while not domain_email.strip():
        console.print("[red]Error:[/red] Domain email is required")
        domain_email = Prompt.ask("[red]*[/red] Domain email")

    wildcard_subdomains = Confirm.ask("Enable wildcard subdomains?", default=False)

    if wildcard_subdomains:
        allowed_hosts = f".{domain}"
        csrf_origins = f"https://{domain},https://*.{domain}"
    else:
        allowed_hosts = domain
        csrf_origins = f"https://{domain}"

    if server_ip:
        allowed_hosts = f"{allowed_hosts},{server_ip}"
        csrf_origins = f"{csrf_origins},http://{server_ip}"

    context.update(
        {
            "domain": domain,
            "domain_email": domain_email,
            "allowed_hosts": allowed_hosts,
            "csrf_origins": csrf_origins,
        }
    )

    console.print("\n[bold]Email Configuration:[/bold]")
    use_smtp = Confirm.ask("Use SMTP email backend?", default=True)
    context["use_smtp"] = use_smtp

    if use_smtp:
        context["email_host"] = Prompt.ask("SMTP host", default="smtp.gmail.com")
        context["email_port"] = Prompt.ask("SMTP port", default="587")
        context["email_use_tls"] = Confirm.ask("Use TLS?", default=True)

        email_host_user = Prompt.ask("[red]*[/red] SMTP username")
        while not email_host_user.strip():
            console.print("[red]Error:[/red] SMTP username is required")
            email_host_user = Prompt.ask("[red]*[/red] SMTP username")
        context["email_host_user"] = email_host_user

        email_host_password = Prompt.ask("[red]*[/red] SMTP password", password=True)
        while not email_host_password.strip():
            console.print("[red]Error:[/red] SMTP password is required")
            email_host_password = Prompt.ask("[red]*[/red] SMTP password", password=True)
        context["email_host_password"] = email_host_password
        context["default_from_email"] = Prompt.ask("Default from email", default=domain_email)

    context["allow_signup"] = Confirm.ask("Allow user signup?", default=False)

    content = render_template("env/production.env", context)
    output_file.write_text(content)

    console.print(f"\n[green]✓[/green] Environment file created: [bold]{output_file}[/bold]")
    console.print("\n[yellow]⚠[/yellow]  [bold]Security Reminder:[/bold]")
    console.print("   • Keep your .env file secure and never commit it to version control")
    console.print("   • Ensure .env is listed in your .gitignore file")


@app.command()
def create(
    environment: str | None = typer.Argument(
        None,
        help="Environment type: 'development' or 'production'",
    ),
    output: Path = typer.Option(
        Path(".env"),
        "--output",
        "-o",
        help="Output file path",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing file without prompting",
    ),
    server_ip: str | None = typer.Option(
        None,
        "--server-ip",
        help=(
            "Server IP to add to ALLOWED_HOSTS and CSRF_TRUSTED_ORIGINS"
            " for HTTP access while DNS is not yet configured."
        ),
    ),
) -> None:
    """Create an environment configuration file with interactive prompts.

    Generates a .env file for either development or production environments
    with auto-generated secure values for secrets and passwords.

    Examples:
        phoxtail env create
        phoxtail env create development
        phoxtail env create production -o .env
        phoxtail env create production --server-ip 1.2.3.4
    """
    if environment is None:
        environment = questionary.select(
            "Select environment type:",
            choices=["development", "production"],
        ).ask()

        if environment is None:
            console.print("\n[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    env_lower = environment.lower()
    if env_lower not in ["development", "production"]:
        console.print(f"[red]Error:[/red] Invalid environment '{environment}'. Must be 'development' or 'production'.")
        raise typer.Exit(1)

    if output.exists() and not force:
        if not Confirm.ask(
            f"[yellow]Warning:[/yellow] {output} already exists. Overwrite?",
            default=False,
        ):
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    try:
        if env_lower == "development":
            _prompt_development_env(output)
        else:
            _prompt_production_env(output, server_ip=server_ip)
    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled.[/dim]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"[red]Error creating environment file:[/red] {e}")
        raise typer.Exit(1)
