# Changelog

All notable changes to Phoxtail are recorded here, in the format of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Phoxtail is pre-1.0 and follows [Semantic Versioning](https://semver.org/) with
one caveat: **minor releases may contain breaking changes** until 1.0. Pin a
version you have tested.

Migrations carry their own pre-1.0 clause: the history may be rebased, in which
case upgrading means re-hatching or rebuilding the database rather than
migrating into it. Any release that does so says so here.

<!-- towncrier release notes start -->

## [0.2.0] — 2026-09-06

Upgrade notes below — a dependency that moved, renamed CSS classes, an app that
must change position in `INSTALLED_APPS` — address projects built against an
earlier version of the package. A fresh install needs none of them.

### Added

- Shared blocks can now be pinned to a site-wide slot (`Block.site_slot`: head/body
  anchors in the page template) and render automatically on every page of a site that
  fills in their shared content — no per-page placement needed; combined with
  page-type restrictions it scopes to every page of those types. A page that places
  the block itself takes over (its own position and variant, or a "hide on this page"
  toggle), variants cascade page → site (`SharedBlock.variant`) → block default,
  missing locales fall back to the default locale's content, and
  `Block.render_in_preview` keeps tracking scripts out of previews and screenshots.
  The streams v1 API, the MCP studio tools, and the cross-project push envelope all
  carry the new fields.
- Platform menus: an editor writes a site's navigation in the Wagtail admin, scoped
  to a site and a language, under a new Platform section. Entries point at a page, a
  named route, an address elsewhere, or a group of those. The menu renders along the
  top of the dashboard and inside the small-screen drawer, with dropdowns,
  separators, and the entry for the page being read marked as current; unpublished
  pages are shown only to editors, linked to their draft. A site with no menu written
  for it shows no bar and no drawer section. Menus are also readable and writable
  over `/api/dashboard/v1/menus/` and through the `phoxtail_dashboard_*` MCP tools,
  so an agent can list, create, update and delete them — updates take an `If-Match`
  ETag, and an entry type the menu does not define is refused rather than silently
  dropped.
- Dashboard widgets are declarative: give `add_widget()` a title, description, icon
  and `url_name` and phoxtail renders the card, so an app no longer ships a template
  and a context function for a link. Cards are grouped under a heading per app
  (`DashboardModule(verbose_name=...)`), and the Account group opens with a card for
  the Wagtail admin, shown only to users who may reach it. A site can amend what
  other apps contribute — `registry.get_module()`, `unregister()`,
  `DashboardModule.remove_widget()` and `remove_nav_item()` — override the index view
  itself through the new `PHOXTAIL_DASHBOARD_VIEW` setting, and shadow any phoxtail
  template from a project-level `templates/` directory, which hatched projects now
  get.
- The dashboard is served under a language prefix (`/en/dashboard/`) and carries a
  language switcher offering every language the project serves. A language with no
  menu written for it still opens the platform — the menu bar is simply absent, and
  the dashboard's own screens are translated regardless.
- `UrlMount` accepts `i18n=True`, mounting an app's URLs under a language prefix
  (`/en/shop/`). Set it for anything a person reads; machine endpoints stay
  unprefixed so their callers need not learn a locale. When at least one app opts in,
  Django's `set_language` view is published at `i18n/` alongside it.
- `phoxtail hatch` and `phoxtail install` take a `--source` option that says where a
  package is resolved from, using uv's own locator syntax: `git+ssh://…@ref` or
  `git+https://…@tag` for a repository, a directory for a local checkout (added as an
  editable path), or a `.whl`/`.tar.gz` URL for a built artefact. PyPI stays the
  default and nothing changes without the flag. Both commands check a non-default
  source before writing anything, and neither treats an unanswered check as a
  failure: with no network the check is skipped and uv, which can resolve from its
  own cache, has the final say.
- `phoxtail upgrade phoxtail` now compares the project's phoxtail-owned declarations
  in `pyproject.toml` against the current project template and offers to apply the
  difference before locking. Previously it only advanced the lockfile, so a project
  kept declaring whatever extras it was hatched with even after the template moved a
  dependency to a different one. Projects hatched before the dependency-groups split
  get the `[dependency-groups]` table created for them.
- `TRADEMARK.md` sets out the permitted use of the Phoxtail name, wordmark and logo,
  which the BSD licence does not grant. Saying a product is built with Phoxtail needs
  no permission; naming a product after it does.
- `SECURITY.md` — how to report a vulnerability privately.

### Changed

- Wagtail 8.0 is now the supported version, raising the `engine` extra from
  `wagtail>=7.4.2,<8.0` to `wagtail>=8.0,<9.0`. Django stays at `<6.0` and the Python
  floor stays at 3.11: Wagtail 8 runs on Django 5.2, so neither has to move yet.
  `wagtailmedia` is raised to `>=0.18.1`, which carries a permission fix for the
  media chooser — it previously exposed a media item's id, title and edit URL to
  users without access to it.

  Two Wagtail 8 changes are worth knowing about. Image renditions no longer convert
  AVIF and WebP to PNG, so sites serving those formats will now emit them directly;
  set `WAGTAILIMAGES_FORMAT_CONVERSIONS` to restore the old behaviour. And
  `menu_order` is now respected between viewsets inside a `ViewSetGroup`, which
  reorders some admin menus.
- **Breaking for projects built against an earlier version.** `playwright` and
  `Pillow` are no longer installed by default. They moved to a new `studio` extra,
  which carries the screenshot tools in `phoxtail.mcp.studio` and nothing else — a
  base install no longer pulls a browser stack it may never use.

  Newly hatched projects get `phoxtail[studio]` in their `dev` dependency group, and
  projects still on the `phoxtail[dev]` alias keep it because that alias now includes
  `studio`. Projects that already moved to the `dev-tools` + dependency-group layout
  must add it themselves — `phoxtail upgrade` advances the lockfile without rewriting
  `pyproject.toml`:

  ```toml
  [dependency-groups]
  dev = [
      "phoxtail[dev-tools]",
      "phoxtail[studio]",
  ]
  ```

  Then run `uv lock`; the Dockerfile syncs with `--frozen` and refuses a lockfile
  that no longer matches. Without the entry the development image fails at
  `playwright install`. Production images are unaffected, and lose a browser stack
  they were never using.
- htmx is no longer bundled with phoxtail. It now comes from `django-htmx`, which
  phoxtail already depends on, via its `{% htmx_script %}` tag — one copy instead of
  two, at 2.0.10 instead of 2.0.8. Any project template that loads htmx with
  `<script src="{% static 'phoxtail_core/js/htmx.min.js' %}">` must switch to
  `{% htmx_script %}`; the static file is gone, and under
  `ManifestStaticFilesStorage` a stale reference raises at render time.
- Every declared dependency floor now names a version phoxtail is tested against,
  replacing inherited minimums that had never been installed — several of which did
  not work. Installing phoxtail alongside an older pinned dependency will now fail to
  resolve rather than fail at import.
- `phoxtail install` no longer decides on its own whether a package belongs in
  `INSTALLED_APPS`. It previously treated any importable top-level module as a Django
  app, so installing something like `httpx` or `redis` registered it and left Django
  importing a non-app at startup. A package now has to carry an `AppConfig`, models,
  or migrations to be considered one — and because no inspection can rule out a
  Django app carrying none of those, the result is offered as the default answer
  rather than acted on. Answer no and nothing is registered; answer yes for a package
  that was not detected and you are asked for the module name. `--app <module>` and
  `--no-app` answer ahead of time, and a non-interactive run acts on the detection
  result without prompting. The module name is read from the installed
  distribution's metadata rather than guessed from the package name, so apps whose
  names differ — `django-taggit` installs `taggit` — are registered instead of
  silently skipped. The stream-population step follows the same answer: declining
  registration skips it instead of running it against an app Django does not know
  about.
- The profile view is borderless: every control — the content panel, the
  account-settings links, the personal-information rows, the Edit button, the avatar
  and the file field — is now a shape defined by its fill against the fill behind it,
  in both colour schemes. The information rows are tiles rather than lines, the two
  columns share one fill, the page heading has lost its panel and the icon beside its
  subtitle, buttons are pills on the core button's metrics, and the row icons are the
  dashboard's widget icon. The stylesheet that dressed it moved with it — see
  *Removed*.
- The annotations shipped under `py.typed` are now verified rather than asserted —
  the package type-checks clean, and CI fails on any error. Two signatures were
  corrected against their callers in the process: `collection_id` on the studio
  client's `create_variant` accepts `None`, and `Provider` subclasses now declare
  their one-argument constructor on the base class.
- The `agent` app's migration `0003` was folded into `0001`: it set a model's
  `verbose_name` and nothing else, so it emitted no SQL. **No action required** — a
  database that already applied it is unchanged, and Django ignores the leftover
  history row.
- `LICENSE` names the copyright holder as a person rather than a trade name.

### Removed

- The dashboard stylesheet `phoxtail_dashboard/css/ui.css` is gone. Only the profile
  view rendered its components, yet every dashboard page linked it. Its rules now
  live in `users/css/profile.css` under a `usr-` prefix, and its two genuinely shared
  rules, `.dash-page` and `.dash-page-inner`, moved into
  `phoxtail_dashboard/css/dashboard.css`. A site using any of these class names must
  supply its own styles or switch to the `usr-` equivalents:

  - Owned by the profile view, now `usr-`-prefixed: `dash-page-header*`,
    `dash-page-content`, `dash-columns*`, `dash-column`, `dash-action-*`,
    `dash-info-*`, `dash-btn*`, `dash-avatar*`, `dash-profile-*`, `dash-container`,
    `dash-section`, `dash-hidden`, `dash-md-flex`, `dash-md-hide`, `dash-mb-6`,
    `dash-mt-4`.
  - Widget cards, dropped outright: `.dash-widgets-grid`, `.dash-widget-card`,
    `.dash-widget-title`, `.dash-widget-link`, `.dash-widget-header`,
    `.dash-widget-list*`, `.dash-widget-cta`, `.dash-widget-empty*`. Widget cards no
    longer carry a statistic or a detail line either, so `.dash-widget__stat`,
    `.dash-widget__meta` and the `stat`/`meta` context keys behind them are gone with
    them.
- The Monaco code editor is gone from the Wagtail admin. The HTML, CSS and JavaScript
  fields on a block variant now use a fixed-height text area instead of an embedded
  editor, which drops a bundled JavaScript loader and a runtime fetch from a
  third-party CDN. No data or schema changes: the fields are unchanged and their
  content is untouched.
- `phoxtail install --url` and `--branch` are gone; `--source` covers both.
  `--url <repo>` becomes `--source git+<repo>`, and `--branch <ref>` becomes an
  `@<ref>` suffix on that locator — `--source git+ssh://git@github.com/your-org/<package>.git@dev`.
  A bare `ssh://` or `git@host:` remote is still understood without the `git+`
  prefix.
- The `.phoxtail-dialog--glass` CSS class is gone. It provided the glass surface for
  centered dialogs, but its only consumer became a right-to-left drawer and switched
  to `.phoxtail-drawer--glass`, leaving nothing using it. Pages styling a centered
  dialog with it will lose the background, border, and shadow; add those to the
  consumer's own class, or reuse `.phoxtail-drawer--glass` if a drawer suits.
- The `apps` field is gone from `phoxtail.toml`, and `phoxtail hatch` no longer
  writes it. Nothing read it, and setting it never had any effect.

### Fixed

- `phoxtail upgrade` now works for any package in the project's dependency graph. It
  matched a name in `pyproject.toml` only when a closing quote or an extras bracket
  followed it, so every pinned dependency — `wagtail>=7.4.2,<8.0` and the like — was
  refused as "not listed in pyproject.toml". Packages are now resolved through
  `uv.lock`, which also covers transitive dependencies a project never declares
  itself. When the lockfile does not move, the command says why and stops instead of
  rebuilding and restarting the stack for an unchanged resolution.
- `phoxtail install` now declares what it installs where you would expect to find it.
  It shared `phoxtail upgrade`'s blind spot for pinned entries and would append a
  second, unconstrained entry for a package already declared with a version
  specifier. It also inserted new dependencies into `dependency-groups.dev` rather
  than `project.dependencies`, so anything installed into a hatched project was
  dropped from the production image by `uv sync --no-dev`. When it cannot find a
  dependencies array to append to, it now stops with an actionable message rather
  than reporting a successful install of a package it never declared; a git source
  installed into a freshly hatched project creates the `[tool.uv.sources]` table
  instead of quietly resolving against PyPI, and where the table already exists the
  source is inserted into it rather than appended to the end of the file, where it
  could land in whichever table came last. A package declared only in the dev
  dependency group no longer counts as installed, since the production image drops
  that group.
- `phoxtail install <package>` no longer fails its pre-flight check for every package
  on PyPI. It asked `uv pip index versions`, a subcommand no longer present as of uv
  0.11, and read the resulting error as "not found on PyPI"; the check now queries
  PyPI's JSON API directly. An unreachable index no longer blocks the install either
  — a package is reported missing only when PyPI says it is.
- `wagtailmedia` now sits above `wagtail.snippets` in `INSTALLED_APPS`, so a project
  starts under wagtailmedia 0.19.0. That release registers the media permission
  policy in its `AppConfig.ready()` while its `wagtail_hooks` module looks the policy
  up at import time, and `wagtail.snippets.ready()` imports every app's hooks. With
  snippets first, the lookup created a fallback policy and the real registration was
  refused with `ImproperlyConfigured`. Hatched projects carry the ordering fix in
  their settings template; existing projects need the app moved by hand.
- Admin menu entries that shared a `menu_order` no longer sort arbitrarily. Font
  Roles and Palette Roles were both 150, and Wagtail 8 orders group members by
  `menu_order` rather than by their position in the group, so the tie surfaced as
  Palette Roles jumping to the middle of the Design menu. The design viewsets are
  renumbered to restore the intended order, and Remotes moves off 601 so it no longer
  ties with API Tokens in the settings menu.
- Modals opened from a page behind a language prefix no longer fail with "Invalid
  content URL". The modal endpoint carries no prefix of its own, so it took the
  language from the browser's cookie; it now reads the language from the content URL
  it was asked to fetch, which also keeps the modal's own strings in the page's
  language.
- `phoxtail server provision` no longer reports a successful bootstrap when
  cloud-init failed. It now asks cloud-init for its status instead of checking for a
  file that is written either way, and the bootstrap ends on a Docker check so a
  failed install is visible.
- `phoxtail server provision` now drops any `known_hosts` entry for a freshly created
  server's IP before connecting. Providers recycle addresses, and a leftover key made
  SSH refuse the connection outright — reported as a timeout, which sent you looking
  at the wrong thing. A failed SSH wait now quotes what SSH actually said.
- `phoxtail server provision` now installs Docker on images that ship `grub-pc` with
  a stored install device that doesn't exist. The failed bootloader upgrade left
  `dpkg` half-configured, and a half-configured `dpkg` fails every later `apt-get`,
  Docker's included. The bootstrap now declines that install rather than attempting
  it, leaving the bootloader as the image shipped it, and acts only when the stored
  device is invalid — so healthy images are untouched.
- `phoxtail server deploy` now checks that the server can actually read the image
  from the registry, rather than assuming a login exists because `ghcr.io` appears in
  `~/.docker/config.json`. An expired token, or one with no access to the package,
  previously reported success and failed later at pull time with `denied`.
- Building phoxtail from source now requires setuptools 77.0.1 or newer, which the
  declared floor previously understated. Nothing changes for anyone installing a
  wheel.


## Earlier versions

Versions before 0.2.0 predate this changelog. Their history is in the commit
log:

- [0.1.0...0.1.1](https://github.com/phoxmor/phoxtail/compare/v0.1.0...v0.1.1)

[0.2.0]: https://github.com/phoxmor/phoxtail/compare/v0.1.1...v0.2.0
