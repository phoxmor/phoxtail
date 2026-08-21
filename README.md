<p align="center">
  <a href="https://phoxtail.com">
    <picture>
      <source media="(prefers-color-scheme: dark)"
              srcset="https://phoxtail.com/static/phoxtail_core/phoxtail/logo/wordmark-on-dark.svg">
      <img src="https://phoxtail.com/static/phoxtail_core/phoxtail/logo/wordmark-on-light.svg"
           width="400" height="95" alt="Phoxtail">
    </picture>
  </a>
</p>

<p align="center">
  <em>The framework for agentic platforms.</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/phoxtail/"><img src="https://img.shields.io/pypi/v/phoxtail.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/phoxtail/"><img src="https://img.shields.io/pypi/pyversions/phoxtail.svg" alt="Python versions"></a>
  <a href="https://github.com/phoxmor/phoxtail/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/phoxtail.svg" alt="License"></a>
</p>

<p align="center">
  <a href="https://docs.phoxtail.com/">Documentation</a> ·
  <a href="https://github.com/phoxmor/phoxtail">Source code</a> ·
  <a href="https://community.phoxtail.com/">Community</a>
</p>

Phoxtail is a web framework to help you build platforms focused on agentic interactions and generated user interfaces.

## Features

An A-B-C-D Management System:

- **Agentic** — every capability is an MCP (Model Context Protocol) interface, so agents operate the platform through the same surface you do.
- **Business** — your domain logic installs as dedicated apps, automatically exposing API namespaces, agent tools, and more, while plugging into a dashboard for users to sign in to and interact with.
- **Content** — a full CMS (Content Management System) equipped with page trees, multi-site, localization, a media library, and more to power the data layer behind your public surface.
- **Design** — dynamic UI components, themes, typography, and more, held in the database layer and editable at runtime.

## Getting started

Phoxtail ships a CLI that drives a platform from hatching to production.

```bash
# Recommended
uv tool install phoxtail

# Or with pip
pip install phoxtail
```

## 🐣 Hatch a platform

Phoxtail does not scaffold a website. It scaffolds a platform.

```bash
phoxtail hatch my_platform
```

```
  ┌  Hatching 'my_platform' development  ┐
  │  ✓ 1. Config                         │
  │  ✓ 2. Network                        │
  │  ✓ 3. Database                       │
  │  ✓ 4. Access                         │
  │  ▸ 5. Launch                         │
  └──────────────────────────────────────┘
```

## 🐦‍🔥 Grow the platform

`phoxtail install` takes a package from name to running app:

```bash
phoxtail install <package>
```

```
  ┌  Installing '<package>'  ┐
  │  ✓ 1. Check              │
  │  ✓ 2. Lock               │
  │  ✓ 3. Sync               │
  │  ✓ 4. Register           │
  │  ✓ 5. Compose            │
  │  ✓ 6. Build              │
  │  ✓ 7. Migrate            │
  │  ✓ 8. Populate           │
  │  ▸ 9. Launch             │
  └──────────────────────────┘
```

## Commands

| Group | What it does |
|---|---|
| `hatch` · `install` · `upgrade` | Scaffold a project, add packages, move versions forward |
| `docker` · `net` · `server` | Containers, the shared local network, remote hosts |
| `db` · `media` | Backup, restore, and pull production data down |
| `env` · `requirements` | Environment files and dependency compilation |
| `nginx` · `ssl` | Production web server config and certificates |
| `studio` · `content` | Component variants and themes; pages, locales and sites |
| `mcp` · `auth` | The agent server and its API credentials |
| `manage` · `test` · `lint` | Management commands and the local toolchain |

Run `phoxtail --help`, or `phoxtail <group> --help`, for the full list.

## Documentation

The CLI is where a platform starts.
**[docs.phoxtail.com](https://docs.phoxtail.com/)** takes it from there,
covering the development of your own phoxtail applications, the engine behind
content and design, the API and MCP surfaces, going to production, and more.

## Compatibility

| | |
|---|---|
| Python | 3.11+ |
| Database | PostgreSQL |
| Runtime | Docker and Docker Compose |

## Stability

Phoxtail is pre-1.0. Alongside the usual caveat that minor releases may break
things, one consequence is easy to miss: **before 1.0, Phoxtail may rebase its
migration history.** Upgrading across such a release means re-hatching or
rebuilding your database rather than migrating into it. Pin a version you have
tested, and read the [changelog](https://github.com/phoxmor/phoxtail/blob/main/CHANGELOG.md) before upgrading.

## Community

Questions and discussion at [community.phoxtail.com](https://community.phoxtail.com/).
Bugs and feature requests at
[GitHub issues](https://github.com/phoxmor/phoxtail/issues).

## Contributing

See [CONTRIBUTING.md](https://github.com/phoxmor/phoxtail/blob/main/CONTRIBUTING.md).
Commits carry a `Signed-off-by` line — the
[DCO](https://github.com/phoxmor/phoxtail/blob/main/DCO). Participation is
covered by the
[Contributor Covenant](https://github.com/phoxmor/phoxtail/blob/main/CODE_OF_CONDUCT.md).

## License

BSD 3-Clause. See
[LICENSE](https://github.com/phoxmor/phoxtail/blob/main/LICENSE).

The code is open source; the Phoxtail name and logo are not. See
[TRADEMARK.md](https://github.com/phoxmor/phoxtail/blob/main/TRADEMARK.md).
