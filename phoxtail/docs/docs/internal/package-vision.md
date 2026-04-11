# Package Vision — phoxtail

## One package, three roles

`phoxtail` ships as a single PyPI package that gives projects three things:

1. **The CLI** — project management commands (Docker, DB, env, nginx, SSL, media, etc.)
2. **The engine** — library apps (streams, design, core) that projects install and reference in `INSTALLED_APPS`
3. **The scaffold** — `phoxtail hatch <project_name>` generates a new project with opinionated, project-owned apps

This mirrors how Wagtail works: `pip install wagtail` gives you the library, `wagtail start myproject` gives you a project to build on. The library updates via pip. The scaffolded code is yours to modify.

## Current state (0.2.0-dev)

All three library apps, all three scaffold templates, and the `phoxtail hatch` command are extracted and in-repo.

**Completed:**
- `phoxtail.core` — library app with mixins, fields, permissions, views, templates, static files
- `phoxtail.design` — library app with FontFamily/FontWeight/FontRole, Palette/PaletteRole, CSS variable generation, `populate_design` management command with bundled data files
- `phoxtail.streams` — library app with Block/BlockVariant/SharedBlock/VariantCollection, dynamic block factory (3 modes), schema blocks (24 field types + structures + layers), in-memory cache with signal-driven invalidation, CodeEditorPanel (Monaco), permissions, `populate_streams` + `setup_streams_groups` management commands with bundled block data (20 blocks with schemas, variants, collections)
- `project_template/src/` — Django settings (base/dev/prod/test), URLs, Celery, WSGI
- `project_template/users/` — Custom User model, allauth adapters, forms, validators
- `project_template/app/` — SitePage (with BodyStreamField), SiteConfig (branding + design token inlines), HTMX views, templatetags
- `phoxtail hatch` command — renders project_template into a working project, with interactive setup wizard (env, docker, nginx, launch), project name validation, and requirements scaffolding

**Remaining for v0.2.0:**
- Migrations for library apps (core, design, streams)
- Tests for design and streams apps
- Final publication (remove exclusions from pyproject.toml)

```
phoxtail/
├── __init__.py          # __version__, package metadata
├── __main__.py          # Typer CLI entry point
├── cli/                 # CLI subsystem (commands, utils, templates, tests)
├── core/                # Library app: shared infrastructure
├── design/              # Library app: design tokens
├── streams/             # Library app: block system
└── project_template/    # Scaffold templates for `phoxtail hatch`
```

## Library vs. Scaffold — the core principle

When distributing reusable Django/Wagtail code, there are two mechanisms:

**Library** — code lives in the pip package, imported by reference (`"phoxtail.core"` in `INSTALLED_APPS`). Users get updates via `pip install --upgrade`. Customization is limited to what the package explicitly exposes.

**Scaffold** — code is copied into the project at creation time (`phoxtail hatch myproject`). The user owns it entirely. They modify it freely, run their own migrations, and never receive automatic updates for that code.

These are not competing approaches — they solve different problems:

> **If the code is the same across every project and benefits from centralized fixes, it's a library. If every project customizes it, it's a scaffold.**

### Why core is a library

`phoxtail.core` contains shared infrastructure that projects use but don't modify:

- Model mixins (UUID, Timestamp, AdminURL)
- Custom form fields (MultiSelectChips, SingleSelectSearch)
- A permission system (policies, decorators, CBV mixins, viewsets)
- An HTMX modal engine and widget search views
- Template tags (pagination, feature flags)
- Wagtail hooks (icon registration, menu customization)

This code is generic, well-abstracted, and benefits from centralized fixes. Projects import from it (`from phoxtail.core.mixins import UUIDMixin`) but never modify it.

**Note:** `sitemaps.py` in the existing project has a dependency on the scaffolded `app` package (`app.templatetags.app_tags.decode_url`). This must be resolved during extraction — either by inverting the dependency (core provides the utility, app uses it) or by moving sitemaps to the scaffold.

### Why the streams engine is a library

`phoxtail.streams` and `phoxtail.design` are the most valuable IP in the package. They contain:

- A schema-driven block system — blocks are defined in the database, not in code. 24 field schema types, nested structures, and layers allow editors to compose blocks without developer intervention
- A dynamic block factory with 3 modes (full content + variant, shared reference, shared edit)
- An in-memory cache with signal-driven invalidation for block resolution
- A Studio UI for AI-assisted variant generation (system prompts, context modal, search endpoints)
- A CodeEditorPanel (Monaco) for editing HTML/CSS/JS variant templates in Wagtail admin
- A permission system for block-level access control
- A design token system — font families/weights/roles, color palettes/roles, CSS custom property generation
- 20 bundled block definitions with schemas, variants, collections, and system prompts

This is hundreds of files of intricate, interconnected code:

1. **Bug fixes propagate.** A rendering bug in the carousel block gets fixed once. Every project gets the fix on their next `pip install --upgrade`.
2. **New blocks benefit everyone.** When a new block type is added, every project gets access immediately.
3. **Projects don't modify block internals.** They compose blocks into StreamFields, configure which ones are available, set permissions. The API surface is the contract.
4. **Divergence is dangerous.** If ten projects each have their own copy of the streams engine, they will drift within months.

### Why User, App, and Src are scaffolds

The User model is the canonical problem in Django package design. Django allows exactly one User model per project (`AUTH_USER_MODEL`), set before the first migration runs. If `phoxtail.users.User` ships as a library app, projects can't add fields to it — the model lives in site-packages, managed by pip. Their options (Profile model, monkey-patching, forking) are all bad.

The correct approach: `phoxtail hatch` copies the `users/` app into the project. The developer owns it from day one — adds fields, changes behavior, runs `makemigrations`.

The same logic applies to other scaffolded apps:

| App | Why scaffolded |
|-----|----------------|
| `src/` (settings, URLs) | Always project-specific — database config, installed apps list, middleware, URL routing |
| `users/` | AUTH_USER_MODEL constraint; every project adds custom fields |
| `app/` | SitePage and SiteConfig gain project-specific fields (custom StreamField compositions, branding options, page types) |

This is the same approach used by cookiecutter-django, Wagtail (`wagtail start`), and Django itself (which strongly recommends defining a custom User model at project start).

### How Wagtail draws the same line

Wagtail is the closest analogy:

**Library (pip package, never modified):**
- `wagtail.admin` — the admin interface
- `wagtail.images`, `wagtail.documents` — media management
- `wagtail.blocks` — StreamField block types
- `wagtail.search` — search backend abstraction

**Scaffolded (`wagtail start myproject`):**
- `home/` — the first page app, project-owned
- `search/` — search view, project-owned
- Settings files, manage.py, URLs

**Customization hooks (the middle ground):**
- `WAGTAILIMAGES_IMAGE_MODEL` — lets projects swap the Image model
- Abstract base classes (`AbstractImage`, `AbstractDocument`) for adding fields
- Template overrides via Django's `DIRS` and `APP_DIRS` mechanism

Phoxtail follows the same pattern. The streams engine is like Wagtail's blocks — library code that projects use but don't modify. The scaffolded apps are like Wagtail's `home/` — project-owned starting points.

### The upgrade story

This split creates two distinct upgrade paths:

**Library apps** — upgraded automatically via pip. The package maintains backwards compatibility within a major version. Migrations ship with the package. Projects run `migrate` after upgrading and the library app tables update.

**Scaffolded apps** — never updated automatically. If phoxtail improves the scaffolded User model in a future version, existing projects don't get those changes (and shouldn't — they've likely modified the model). New projects created with `phoxtail hatch` get the latest scaffold.

This means the package's compatibility contract is only about the library apps. The scaffolded code, once generated, is the project's responsibility.

## Optional apps and the `PhoxtailAppConfig` interface

The long-term goal is for optional clusters like `phoxtail.booking`,
`phoxtail.dashboard`, or a future `phoxtail-blog` to ship as separate
PyPI packages that a project can install independently. To make that
possible, optional apps cannot require changes to the project's
settings, URL conf, or scaffold when they are added or removed.

The enabling abstraction is the `PhoxtailAppConfig` base class in
`phoxtail.core.app_config`. Every optional app subclasses it in its
`apps.py` and declares — in one place — everything it needs to be
wired into a Django project:

- `depends_on` — other phoxtail apps this one pulls in
- `url_mount` — where to mount its URL conf and under which namespace
- `context_processors` / `middleware` — appended to the project's
  `TEMPLATES` / `MIDDLEWARE`
- `default_settings` — setting defaults, applied only when the
  project hasn't already set them
- `requires_celery` — toggles `PHOXTAIL_CELERY_ENABLED` for the
  project's celery integration
- `requirements` — extra pip requirements appended to the generated
  `requirements.in` at hatch time

At Django startup, each generated settings module calls
`wire_apps(globals())` from `phoxtail.core.wiring`. That function
walks `INSTALLED_APPS`, finds every `PhoxtailAppConfig`, expands
`depends_on`, and merges the declared fields into the settings
module. Nothing about the project template, the hatch command, or
the settings scaffold needs to know which optional apps exist. Adding
a new optional app means: ship a package, subclass
`PhoxtailAppConfig`, and users put its dotted name in
`INSTALLED_APPS`. Removing an app means: take its dotted name out.

This is what makes the eventual `phoxtail-blog` / `phoxtail-booking`
package split a purely administrative change rather than a coupled
refactor of the engine, the scaffold, and the CLI. See the
[PhoxtailAppConfig reference](../apps/phoxtail-app-config.md) for the
full field list, precedence rules, and examples.

## Publication strategy

Library apps and scaffold templates are developed in-repo but **excluded from the published package until v0.2.0**. The current v0.1.x releases distribute the CLI only:

```toml
[tool.setuptools.packages.find]
include = ["phoxtail*"]
exclude = [
    "phoxtail.cli.tests*",
    # Engine apps and scaffold excluded until v0.2.0
    "phoxtail.core*",
    "phoxtail.design*",
    "phoxtail.streams*",
    "phoxtail.project_template*",
]

[tool.setuptools.package-data]
"phoxtail.cli" = ["templates/**/*"]
# Below entries take effect once engine apps are included (v0.2.0)
"phoxtail.core" = ["templates/**/*", "static/**/*"]
"phoxtail.design" = ["management/commands/data/**/*"]
"phoxtail.streams" = [
    "templates/**/*",
    "static/**/*",
    "management/commands/data/**/*",
]
```

**v0.1.x (current):** `pip install phoxtail` installs the CLI only. Engine apps exist in the repo but are excluded from the wheel. The `[engine]` optional dependency group is defined but has no corresponding code in the package yet.

**v0.2.0 (target):** Remove the engine/scaffold exclusions from `pyproject.toml`. Then:
- `pip install phoxtail` — CLI-only, no Django dependency
- `pip install phoxtail[engine]` — CLI + all library apps (Django, Wagtail, design tokens, block system)
- Non-Python assets (templates, static files, management data) are included via `package-data`

## Target state

### Library apps (all v0.2.0)

| App | Purpose |
|-----|---------|
| `phoxtail.core` | Shared mixins, custom fields, permission policies, HTMX view utilities |
| `phoxtail.design` | Design token system — fonts, color palettes, semantic roles, CSS custom property generation |
| `phoxtail.streams` | Schema-driven block system — dynamic block factory, 24 field schema types, structures, layers, cache layer, block-level permissions, Studio UI |

### Scaffolded apps (v0.2.0)

| App | Purpose |
|-----|---------|
| `src/` | Django settings (base/dev/prod/test), root URL conf, Celery config, WSGI |
| `users/` | Custom User model (email auth via allauth), profile fields, signup/login forms |
| `app/` | SitePage (with BodyStreamField), SiteConfig (branding + design token inlines), ScheduleItem, HTMX endpoints, templatetags |

**Deferred:**

| App          | Purpose                                                             | Why deferred                                                                                                |
| ------------ | ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `dashboard/` | Authenticated user portal with widget registry, i18n-enabled routes | Only becomes valuable when there are apps providing the widgets and views it hosts |

Plus project infrastructure: `manage.py`, `phoxtail.toml`, `requirements.txt`.

### What stays project-local (not in the package at all)

- **`booking/`** and other domain-specific apps — too specialized for the framework
- **`blog/`** — may become a separate optional package (`phoxtail-blog`) in the future
- **Templates and static overrides** — projects customize the look and feel
- **`media/`** — user-uploaded content

## Package layout

```
phoxtail/
├── __init__.py              # __version__, package metadata
├── __main__.py              # CLI entry point (Typer)
│
├── cli/                     # CLI subsystem
│   ├── __init__.py
│   ├── docker.py            # Docker lifecycle and file generation
│   ├── db.py                # Database operations
│   ├── env.py               # Environment file generation
│   ├── nginx.py             # Nginx configuration
│   ├── ssl.py               # SSL certificate management
│   ├── media.py             # Media sync
│   ├── requirements.py      # Python requirements
│   ├── manage.py            # Django management command passthrough
│   ├── test.py              # Test runner
│   ├── lint.py              # Linting
│   ├── hatch.py             # Scaffold command (TODO)
│   ├── utils/               # Config loader, Docker/env helpers, template renderer
│   ├── templates/           # Jinja2 templates (Docker, nginx, env files)
│   └── tests/               # CLI test suite
│
├── core/                    # Library app: shared infrastructure
│   ├── apps.py
│   ├── mixins.py            # UUIDMixin, TimestampMixin, AdminURLMixin
│   ├── fields.py            # MultiSelectChips, SingleSelectSearch
│   ├── permissions/         # AppPermissionPolicy, decorators, mixins, viewsets
│   ├── views.py             # HTMX modal system, widget search CBVs
│   ├── templatetags/
│   ├── templates/phoxtail_core/
│   ├── static/phoxtail_core/
│   └── ...
│
├── design/                  # Library app: design tokens
│   ├── apps.py
│   ├── models.py            # FontFamily, FontWeight, FontRole, Palette, PaletteRole
│   ├── viewsets.py
│   ├── management/commands/ # populate_design + bundled data
│   └── ...
│
├── streams/                 # Library app: schema-driven block system
│   ├── apps.py
│   ├── models.py            # Block, BlockVariant, SharedBlock, VariantCollection
│   ├── blocks/
│   │   ├── factory.py       # Dynamic block factory (3 modes)
│   │   ├── __init__.py      # get_dynamic_blocks entry point
│   │   └── schema/          # 24 field types + structures + layers
│   ├── fields.py            # SchemaStreamField, SharedBlockStreamField
│   ├── cache.py             # In-memory cache with signal-driven invalidation
│   ├── viewsets.py          # Wagtail snippet viewsets + Studio
│   ├── views.py             # Studio views + search endpoints
│   ├── permissions.py       # Stream-specific permissions
│   ├── admin/panels/        # CodeEditorPanel (Monaco editor)
│   ├── templatetags/
│   ├── templates/
│   │   ├── phoxtail_streams/studio/   # Studio UI templates
│   │   └── admin/panels/code_editor/  # Monaco panel template
│   ├── static/phoxtail_streams/       # Studio CSS, Monaco assets, SVGs
│   ├── management/
│   │   ├── commands/        # populate_streams, setup_streams_groups
│   │   └── data/            # 20 block definitions (schemas, variants, prompts, collections)
│   └── ...
│
└── project_template/        # Scaffolding templates for `phoxtail hatch`
    ├── src/                 # Django settings, URLs, WSGI
    ├── users/               # Custom User model, forms, adapters
    ├── app/                 # SitePage, SiteConfig, HTMX endpoints, templatetags
    ├── manage.py
    ├── phoxtail.toml
    └── requirements.txt
```

### Scaffold template convention

Files in `project_template/` use normal extensions (`.py`, `.toml`, `.html`) — no `-tpl` suffix. This gives full IDE support (syntax highlighting, linting, import resolution) on every scaffold file.

Files that need project-specific values use `{{ phoxtail_project_name }}` as a placeholder inside string literals. The `phoxtail_` prefix distinguishes scaffold variables from Django template tags. The `hatch` command replaces these placeholders when copying files into the target project. Currently only 3 files use this: `phoxtail.toml`, `src/celery.py`, and `src/settings/base.py`.

Project names are validated before scaffolding via `validate_project_name()` — the same checks Django's `startproject` performs (valid Python identifier, not a keyword, no module name conflicts).

**Implementation warning:** The `hatch` command must use `str.replace()` for placeholder substitution, **not** Jinja2's `Template` or `Environment`. Scaffold files contain Django template syntax (`{{ page.title }}`, `{% block %}`, etc.) in their HTML templates. If processed through Jinja2, those Django tags would be interpreted as Jinja2 expressions and either error or produce empty output. Plain string replacement only touches the exact `{{ phoxtail_project_name }}` placeholder and leaves everything else untouched.

## `phoxtail hatch` output

```bash
phoxtail hatch myproject
```

Generates:

```
myproject/
├── manage.py
├── phoxtail.toml
├── requirements.txt             # includes phoxtail[engine]
│
├── src/                         # Django configuration (scaffolded, project-owned)
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   ├── production.py
│   │   └── test.py
│   ├── urls.py
│   ├── celery.py
│   └── wsgi.py
│
├── users/                       # Scaffolded, project-owned
│   ├── models.py
│   ├── adapters.py
│   ├── forms.py
│   └── ...
│
└── app/                         # Scaffolded, project-owned
    ├── models.py                # SitePage, SiteConfig
    ├── streams.py               # BodyStreamField (uses SchemaStreamField)
    ├── views.py                 # HTMX modal views
    ├── urls.py
    ├── wagtail_hooks.py
    ├── templatetags/app_tags.py
    ├── templates/app/
    └── static/app/
```

### The hatch wizard

The name "hatch" implies a project that is born ready to run — not just scaffolded files on disk. After generating the Django project structure, hatch walks the user through the deployment steps as an interactive wizard, orchestrating the existing CLI commands:

1. **Environment** — `phoxtail env create` → generate `.env` files
2. **Docker** — `phoxtail docker create` → generate `Dockerfile`, `docker-compose.yaml`
3. **Nginx** — `phoxtail nginx create` → generate reverse-proxy config
4. **Build & run** — build the image and spin up containers

Each step is optional — the user can skip any of them. But the default path produces a fully running project: containers up, database migrated, ready to develop against. If the user declines a step, it becomes their responsibility to handle it later using the standalone CLI commands.

This means the standalone commands (`docker create`, `env create`, `nginx create`, etc.) serve dual roles: they are independently useful for existing projects, and they are the building blocks that hatch composes into a complete setup experience. The logic lives in the individual commands — hatch simply orchestrates them.

In `src/settings/base.py`:

```python
INSTALLED_APPS = [
    # Wagtail
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail.contrib.settings",
    "wagtail.locales",
    "wagtail.contrib.simple_translation",
    "wagtail",
    "wagtailmedia",
    "modelcluster",
    "taggit",
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.postgres",
    "django_htmx",
    # Project apps (scaffolded — you own these)
    "users",
    "wagtail.users",
    "app",
    # Phoxtail library apps (from pip — updates via pip)
    "phoxtail.core",
    "phoxtail.design",
    "phoxtail.streams",
    # Third-party
    "allauth",
    "allauth.account",
    "django_celery_beat",
    "sorl.thumbnail",
    "wagtail_color_panel",
]
```

## Dependencies

```toml
[project]
dependencies = [
    "typer>=0.9.0",
    "rich>=13.0.0",
    "questionary>=2.0.0",
    "jinja2>=3.1.0",
]

[project.optional-dependencies]
engine = [
    "django>=4.2",
    "wagtail>=6.0",
    "django-allauth>=0.60",
    "django-htmx>=1.17.0",
    "celery>=5.3",
    "wagtail-color-panel>=0.4.0",
    "pyyaml>=6.0",
    "wagtailmedia>=0.15",
    "modelcluster>=6.0",
    "sorl-thumbnail>=12.10",
]
dev = [
    "pip-tools>=7.0.0",
    "pytest>=8.0.0",
    "pytest-django>=4.8.0",
    "ruff>=0.4.0",
    "phoxtail[engine]",
]
```

- `pip install phoxtail` — CLI-only, no Django dependency
- `pip install phoxtail[engine]` — CLI + all library apps (Django, Wagtail, design tokens, block system)
- `pip install phoxtail[dev]` — includes engine + testing/linting tools

## Migration strategy

### v0.1.x — CLI-only

Published on PyPI. Commands for Docker, DB, env, nginx, SSL, media, requirements. No Django dependency.

The CLI covers the core deployment workflows and is actively used with existing projects. Further CLI improvements (deploy meta-command, `phoxtail init` for existing projects) will be revisited as patch releases.

### v0.2.0 (in progress) — Full engine + scaffold

All three library apps, all three scaffold templates, and the hatch command — shipped together:

1. **`phoxtail.core`** — shared infrastructure (mixins, fields, permissions, HTMX views). **Done.**
2. **`phoxtail.design`** — design token system (fonts, palettes, CSS generation). **Done.**
3. **`phoxtail.streams`** — schema-driven block system (dynamic factory, 24 field types, Studio UI, caching, permissions). **Done.**
4. **`phoxtail/project_template/`** — scaffold templates for `src/`, `users/`, `app/`. **Done.**
5. **`phoxtail hatch`** command — renders the template into a working project with interactive wizard. **Done.**
6. **Migrations** for all three library apps. **TODO.**
7. **Tests** for design and streams apps. **TODO.**

These are interdependent — `src/settings/base.py` lists all three library apps in `INSTALLED_APPS`, `app/models.py` imports core mixins and design token FKs, `app/streams.py` uses the streams block factory.

### v0.3.0+ — Refinement and hardening

Further milestones before a stable release. The list below is not exhaustive — additional items will be documented as they are identified:

- End-to-end integration tests (hatch → build → migrate → serve)
- `phoxtail init` for adopting existing Django projects
- `phoxtail deploy` meta-command orchestrating the full deployment pipeline
- Documentation site / usage guides
- Template override strategy for library apps
- Optional scaffolded app flags for hatch (`--with-blog`, etc.)

### v1.0.0 — Stable API

Full hatch output, stable library app APIs, migration path documented, comprehensive test coverage. Potentially add `dashboard/` scaffold.

## Open questions

- Should `blog/` become a separate optional package (`phoxtail-blog`) or always stay project-local?
- Template override strategy for library apps: Django's `DIRS` approach, or something more structured?
- Should `phoxtail hatch` support flags for optional scaffolded apps (e.g., `--with-booking`, `--with-blog`)?
- When should `dashboard/` be added to the scaffold — v1.0.0 or earlier?
