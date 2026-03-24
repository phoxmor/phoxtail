# Phoxtail

Phoxtail is a modular digital ecosystem built on Django and Wagtail CMS, designed as a foundation for combining multiple applications into a complete digital solution.

## What's in the box

| Component | Description |
|-----------|-------------|
| **CLI** | Project management commands — Docker, DB, env, nginx, SSL, media, requirements |
| **Engine** | Library apps (`phoxtail.core`, `phoxtail.design`, `phoxtail.streams`) installed via pip |
| **Scaffold** | `phoxtail hatch <project>` generates a new project with opinionated, project-owned apps |

## Quick Start

```bash
# Install phoxtail
pip install phoxtail

# Scaffold a new project
phoxtail hatch myproject
cd myproject

# Generate configuration and start developing
phoxtail env create development
phoxtail docker create dockerfile
phoxtail docker create compose development
phoxtail docker up
```

## Architecture

### Core Applications

| Application | Purpose |
|-------------|---------|
| `app/` | Main site pages and content models |
| `users/` | Custom user model and authentication |
| `core/` | Shared utilities, middleware, and base functionality |

### Key Technologies

- **CMS**: Wagtail 7.0+ for content management and website building
- **Database**: PostgreSQL with psycopg3
- **Authentication**: Django Allauth
- **Frontend**: HTMX for dynamic interactivity with minimal JavaScript
- **Styling**: Custom CSS with design token architecture
- **Infrastructure**: Docker and Nginx for deployment

### URL Structure

| Path | Purpose |
|------|---------|
| `/admin/` | Wagtail admin interface |
| `/django-admin/` | Django admin (fallback) |
| `/accounts/` | Authentication URLs (allauth) |
| `/dashboard/` | Dashboard interface (if enabled) |

## Development Commands

```bash
# Docker environment
phoxtail docker up          # Start services
phoxtail docker down        # Stop services
phoxtail docker restart     # Restart services

# Code quality
phoxtail lint               # Run ruff + djlint

# Database
phoxtail manage makemigrations   # Create migrations
phoxtail manage migrate          # Apply migrations
phoxtail db backup               # Backup database
phoxtail db restore <file>       # Restore from backup

# Dependencies
phoxtail requirements compile    # Compile requirements.txt
```

## Serving these docs

```bash
phoxtail docs
```

Then visit [http://localhost:8000](http://localhost:8000).
