# Phoxtail

The engine behind every Phoxtail project.

Phoxtail is a CLI toolkit that automates the development and deployment workflow for Phoxtail projects — Docker configuration, environment setup, database operations, nginx, SSL, media sync, and more.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

### As a CLI tool

```bash
# Recommended: installs in an isolated environment
uv tool install phoxtail

# Or with pip/pipx
pip install phoxtail
```

### For development

```bash
git clone git@github.com:phoxmor/phoxtail.git
cd phoxtail
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Usage

Run `phoxtail` from the root of any Phoxtail project (where `phoxtail.toml` lives):

```bash
phoxtail --help
```

### Commands

| Command | Description |
|---|---|
| `phoxtail docker up/down/restart` | Docker lifecycle management |
| `phoxtail docker create compose` | Generate docker-compose.yaml |
| `phoxtail docker create dockerfile` | Generate Dockerfile |
| `phoxtail env create` | Generate .env files (dev/production) |
| `phoxtail nginx create initial` | Nginx config for SSL certificate retrieval |
| `phoxtail nginx create production` | Nginx config with SSL/TLS |
| `phoxtail ssl obtain/renew` | SSL certificate management |
| `phoxtail db backup/restore` | Database backup and restore |
| `phoxtail db pull` | Pull database from remote server |
| `phoxtail media pull` | Sync media files from remote server |
| `phoxtail requirements compile` | Compile Python dependencies |
| `phoxtail manage <command>` | Run Django management commands |
| `phoxtail test` | Run the test suite |
| `phoxtail lint` | Run linting and formatting |
| `phoxtail version` | Show CLI version |

## Project detection

Phoxtail detects projects by looking for `phoxtail.toml` in the current directory. This file declares the project name, Docker image prefix, database clusters, and their dependencies.

## Development

### Running tests

```bash
pytest
```

### Project structure

```
phoxtail/
  phoxtail/
    __init__.py         # Package version
    __main__.py         # CLI entry point (Typer app)
    commands/           # Command modules
    utils/              # Shared utilities (config, docker, env, templates)
    templates/          # Jinja2 templates (Dockerfile, compose, nginx, env)
    tests/              # Test suite
  pyproject.toml
  LICENSE
  README.md
```

## License

BSD 3-Clause. See [LICENSE](LICENSE).
