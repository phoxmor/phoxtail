# Quick Start

## Prerequisites

Install `uv` (Python package manager):

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with pip
pip install uv
```

## Setup with CLI

The recommended way to set up a new Phoxtail project is using the CLI:

```bash
# Scaffold a new project
phoxtail hatch myproject
cd myproject

# Generate environment configuration
phoxtail env create development

# Generate Docker files
phoxtail docker create dockerfile
phoxtail docker create compose development

# Compile Python requirements
phoxtail requirements compile

# Start the project
phoxtail docker up
```

For production deployment, see the [Deployment Guide](deployment.md).

## Project Structure

After scaffolding, your project looks like this:

```
myproject/
├── manage.py
├── phoxtail.toml
├── requirements.txt
│
├── src/                    # Django configuration (project-owned)
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   ├── production.py
│   │   └── test.py
│   ├── urls.py
│   ├── celery.py
│   └── wsgi.py
│
├── users/                  # Custom User model (project-owned)
│   ├── models.py
│   ├── adapters.py
│   └── forms.py
│
└── app/                    # Site pages and config (project-owned)
    ├── models.py           # SitePage, SiteConfig
    ├── streams.py          # BodyStreamField
    ├── views.py
    ├── templates/app/
    └── static/app/
```

## Library vs Scaffold

**Library apps** (`phoxtail.core`, `phoxtail.design`, `phoxtail.streams`) live in the pip package. You import them by reference in `INSTALLED_APPS` and get updates via `pip install --upgrade`.

**Scaffolded apps** (`src/`, `users/`, `app/`) are copied into your project at creation time. You own them entirely and modify them freely.

See [Package Vision](../internal/package-vision.md) for the full rationale behind this split.
