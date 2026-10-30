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

## [0.4.0] — 2026-10-30

This release fixes a leak: images built by phoxtail 0.2.0 and 0.3.0 (and by
installs from the git repository since 2026-06-10) carry the project's
production `.env` once the project has been deployed with
`phoxtail server deploy`
([GHSA-52f8-g7r4-m363](https://github.com/phoxmor/phoxtail/security/advisories/GHSA-52f8-g7r4-m363)).
It also names database backups after the site and environment they hold, and
lets `phoxtail db backup` back up a server.

Upgrading from 0.3.0 — read these first:

- **Every deployed project must act** (see Security): regenerate
  `.dockerignore`, release, change the credentials in `.env`, and delete the
  old images. Until `.dockerignore` is regenerated, `phoxtail docker push` and
  `phoxtail docker release` refuse the project's image.
- **`phoxtail db backup`, `db pull`, `db push` and `db restore` stop without
  `DJANGO_ENV`** in the `.env` next to the database they touch, and their files
  have new names.

### Security

- Production images no longer carry the project's secrets
  ([GHSA-52f8-g7r4-m363](https://github.com/phoxmor/phoxtail/security/advisories/GHSA-52f8-g7r4-m363)).
  The generated Dockerfile copies the project folder into the image, and the
  generated `.dockerignore` excluded `.env` only at the project root, while
  `phoxtail server deploy` keeps the production `.env` (with `SECRET_KEY` and
  the database password) in `.phoxtail/deploy/`. Anyone able to pull an image
  built after a project's first `server deploy` could read those files, and
  other files the project folder held but git does not, such as uploads under
  `.phoxtail/` and hidden files at the root. The `.dockerignore` template now
  excludes `.env` files at any depth,
  `.phoxtail/`, every hidden file or folder at the project root and database
  dumps (`*.sql`), as well as Python caches, `node_modules` and editor files at
  any depth, so bytecode compiled on the developer's machine stays out too.
  `phoxtail docker push` and `phoxtail docker release` now refuse to push an
  image with a `.env`, `.env.*`, `.phoxtail` or `.sql` file under `/app`.

  Existing projects:

  1. Upgrade to phoxtail 0.4.0 first: the refusal runs in the CLI that
     pushes.
  2. Run `phoxtail docker create dockerignore --force`, then re-apply any
     edits of your own.
  3. Run `phoxtail docker release`, then `phoxtail server deploy <ip>`.
  4. Change the credentials the `.env` holds, in both copies (on the server
     and in `.phoxtail/deploy/`), then run `phoxtail server deploy <ip>`
     again:
     - the email password first, since it works from anywhere: create a new
       one with your provider, deploy it, check that mail is sent, then
       revoke the old one;
     - `SECRET_KEY`. Everyone is logged out, and links already emailed stop
       working. Do not keep the old key in `SECRET_KEY_FALLBACKS`;
     - any key you added yourself;
     - the database password only if its port was ever reachable from
       outside the server (the generated compose file publishes none).
       Change it in the database first, then in `.env`, or the site cannot
       connect.
  5. Delete the old image versions from your registry, keeping the one the
     server now runs.

### Added

- `phoxtail db backup <ip>` backs up a server's database: it dumps it into the
  server's `db-backups/`, keeps it there, and copies it into the local
  `db-backups/`. Without an IP it backs up the local database as before.

### Changed

- `phoxtail db backup` now names its files `<project-slug>_<DJANGO_ENV>_<UTC
  time>.sql`, for example `mysite_production_2026-10-28_10-19-28.sql`, so a
  backup says which site and which environment it holds even after it is
  copied elsewhere. The environment is read from the `.env` next to the
  database that is dumped, and the command stops with an error if
  `DJANGO_ENV` is missing. A failed dump leaves no file behind. Existing
  backups keep their names and `db restore` still accepts them.
- The copy that `db pull`, `db restore` and `db push` take of a database
  before replacing it is now named `<project-slug>_<DJANGO_ENV>_before-<step>.sql`
  (for example `mysite_production_before-push.sql`) instead of
  `pre_<step>_safety.sql`, so it says which site and environment it holds.
  Each step still keeps one copy, overwritten by its next run, and the copy
  is written whole or not at all. The commands stop before changing anything
  if `DJANGO_ENV` is missing from the `.env` next to the database they
  replace. `db restore` refuses its own `before-restore` copy, since taking
  the copy first would overwrite it. Old `pre_*_safety.sql` files are no
  longer written and can be deleted.
- A hatched project now commits its `uv.lock`: the template's `.gitignore` no
  longer ignores it, so the exact version of every installed package is in the
  project's history and each upgrade shows as a diff. An existing project picks
  this up by removing the `uv.lock` line from its own `.gitignore`.

### Fixed

- The MCP server and API token checks no longer fail in production images that
  carry no `.phoxtail` folder, such as those built with the new `.dockerignore`.
  Importing the MCP server tried to create `.phoxtail/mcp/uploads` under `/app`,
  which the app user cannot write there, and every API token check imports it.
  The screenshot tools now still return the image when they cannot also save a
  copy under `.phoxtail/vision/`.
- `phoxtail server ssl` now replaces an outdated certificate-renewal cron line
  instead of keeping it: it shows the server's line next to the current one and
  asks before replacing it, leaving every other cron entry as it is. On a
  server set up before 0.3.0, running `phoxtail server ssl <ip>` is now how the
  `--no-deps` renewal line arrives; no `crontab -e` edit is needed.
- `phoxtail db pull`, `db push` and the other server commands now read a piped
  answer: the ssh call that checks the server's identity used to swallow it,
  so `echo y | phoxtail db push <ip>` aborted at the prompt.

## [0.3.0] — 2026-10-26

This release puts a permission on every door: each API endpoint and MCP tool now
names the Django permission its act needs, tokens are held to their scopes, and
the site becomes an OAuth 2.1 authorization server so outside clients can act
for a person with their consent. It also brings a shared component layer
(surfaces, buttons, fields, drawers, list pages), Greek, and the authentication
pages on django-allauth's own templates.

Upgrading from 0.2.0 — read these first:

- **An endpoint that declares no `auth=` now refuses everyone** (see Security).
  Annotate each of your own endpoints with `guarded(...)`, `scoped(...)` or
  `authenticated()`.
- **Every list the API serves answers `{"items": [...], "total": N}`** one page at
  a time, and several API paths moved (`/api/content/v1/` is now `/api/cms/v1/`).
  Update clients and run `collectstatic`.
- **Tokens issued with `"*"` stop working** wherever a scope is checked; re-issue
  them as unrestricted or with the scopes they need.
- **`request.auth` is an `AuthorizationContext`**, not a `User`.
- **An app declares its API and MCP tools one way only**, by convention; the
  `api_version_router` attribute, the `phoxtail.mcp_modules` entry point,
  `[mcp] extra_modules` and `page_schema_contributors` are gone.
- **Field templates moved** to `phoxtail_core/forms/fields/`, several fields were
  folded into `input`, `choices` and `select`, and the `fw-` classes are now
  `phx-`.
- **Deployed sites:** regenerate the Dockerfile (uv 0.13.5) and the production
  compose (pinned nginx and certbot), and replace the certificate-renewal cron
  line (see Fixed).

### Added

- The site is now an OAuth 2.1 authorization server (django-oauth-toolkit, in the
  `engine` extra), declared as a surface of `phoxtail.tokens`: the RFC 8414
  discovery document at `/.well-known/oauth-authorization-server` and the
  endpoints under `/o/`. A hatched project picks it up on upgrade with nothing
  edited — the dependency, the URL mount and the `OAUTH2_PROVIDER` defaults
  arrive through the app protocol, and `migrate` runs on every start as it
  already does. Its `issuer` is the exact name the MCP server advertises.

  - **Outside clients ask for bundles**, never permission codenames: one
    `<app>:read` / `<app>:write` pair per phoxtail app, derived from the
    codenames the app's endpoints and tools already name (write includes read),
    so a renamed model changes no issued credential's meaning. The discovery
    document and the MCP server's protected-resource document list every
    bundle; a request for anything else — the library's placeholder `read`, a
    codename, or nothing at all — is refused as `invalid_scope`. The consent
    screen is phoxtail's: it names the client by the host of its metadata URL
    when it has one, names the host the browser will be sent to, says so when
    that is this device, and lists what the client would be able to do.
    Approval takes the requested set whole.
  - **A client the site has never met can introduce itself**, granting nothing
    either way: by document — its `client_id` is an `https` URL the site fetches
    through the library's SSRF-hardened fetcher, and the consent screen names
    that host; grant types the server does not offer are narrowed away, as
    RFC 7591 allows — or anonymously at `/o/register/` (RFC 7591, with RFC 7592
    read-back). Both create a public client that still sends every person to
    the consent screen. An operator who wants only listed hosts to register by
    document sets the library's allowlist class and hosts in settings.
  - **Public clients and loopback callbacks.** The discovery document lists
    `none` among the token-endpoint authentication methods (a phone app or a CLI
    proves itself with PKCE), a client listening on `http://localhost:<any
    port>` matches one that registered another loopback port (RFC 8252), and
    every authorization response carries `iss` (RFC 9207).
  - **Every RFC 9700 gate the library defines is decided.** The implicit grant,
    the password grant and plain PKCE challenges are refused; a key in the query
    string is refused; replay protection, exact redirect matching and required
    PKCE are deploy-check errors. A plaintext redirect scheme stays allowed only
    because a CLI's callback is `http://localhost`: an `http` redirect to any
    other host is refused whatever a client registered. A test fails if a
    future library release adds a gate nobody has decided.
  - **Tokens live short and are stored hashed**: an hour for access, a week for
    refresh (renewed on every use), and a replayed refresh token revokes
    everything descended from its grant. There is no grace window for a retried
    refresh. `manage.py sweeptokens` removes dead token rows of both families
    after 90 days (`--retention-days`); nothing schedules it yet.
  - System checks `E004`–`E007` fail startup if a project's own settings
    displace any of this: the scope backend or validator, the resource check,
    either registration door, or the kept redirect gate.
- The API reads a key the authorization server issued after a person's consent,
  so a client holding one can act within the bundles approved and the person's
  own permissions. One `Authorization: Bearer` header is routed by the key's
  shape (phoxtail's own keys carry the `phxt_` prefix), and either kind is read
  into one credential. Bundles are valid on phoxtail's own keys too —
  `cms:read` beside a codename in the admin or the CLI. A key issued for the MCP
  server (`resource=`) is honoured at the API behind it, compared canonically, so
  a key for another host is refused.
- The MCP server is reachable from the internet, at `https://mcp.<domain>/mcp`
  in production and `http://mcp.<slug>.localhost/mcp` locally. Its `401` points
  at its protected-resource metadata (RFC 9728), which names the site as the
  authorization server, so a remote client finds where to authenticate from the
  MCP URL alone. The `mcp` service joins the production compose;
  `phoxtail nginx create production` writes a server block that passes requests
  through exactly as sent; `phoxtail ssl obtain` and `phoxtail server ssl` add the name to the
  site's certificate (`--expand`). `/o/register/` and `/o/authorize/` are
  rate-limited per client address at the edge (ten a minute, burst twenty).
  `phoxtail env create production` lists `web` in `ALLOWED_HOSTS`. An
  already-deployed project needs `web` added to `ALLOWED_HOSTS` by hand, the DNS
  record for `mcp.<domain>`, a regenerated `nginx.conf`, the certificate
  obtained again, and both containers restarted.
- Token scopes are enforced. An endpoint names the codename of its act once with
  `auth=guarded("wagtailcore.publish_page")`, which asks both halves: whether
  the person holds the permission, and whether their credential covers it.
  `scoped(...)` asks only the credential, and `authenticated()` admits any
  caller whatever their credential's ceiling, for an endpoint that genuinely
  asks for no permission (an anonymous caller still gets 401). A narrowed
  credential and a missing permission are refused with different messages.
  Whether the person may act is still also decided where it already was —
  Wagtail resolves publishing per page subtree, and that check is unchanged.
- A token's scopes are validated when it is issued: a scope names a real Django
  permission or a bundle, and a typo is refused with the correct spelling. The
  API token create form offers an **Unrestricted** checkbox.
- MCP tools are held to the same rule: `phoxtail.mcp.authorization.scoped()`
  names a tool's codename, and a tool its caller's credential does not cover is
  left out of that caller's catalogue. Over HTTP the MCP server introspects the
  bearer at `GET /api/whoami/` before anything runs and answers a request with
  no credential `401` with the standard challenge; a local (stdio) session is
  offered only the tools its stored token covers. `phoxtail_whoami` reports who a
  local session acts as and which tools were withheld, with the permission each
  would need.
- `GET /api/whoami/` reports the identity and ceiling of the credential making
  the request — email, user uuid, superuser flag, whether the token is
  unrestricted, its scopes and bundles, and its expiry. Every credential can
  reach it, so a caller can discover its own limits.
- Phoxtail speaks Greek. The dashboard, the authentication pages, the profile,
  the admin's snippets and settings, and the page bar and chatbot follow the
  active language, with one Greek catalogue; text the bar's and chatbot's scripts
  build in the browser is still English. Every password field reads
  "Συνθηματικό", the Wagtail admin's included, and Django's password rules read in
  better Greek.

  Translations live in a new app, `phoxtail.translations`, which `wire_apps`
  installs first; a project that lists its apps itself must put it above every
  app with translations of its own (allauth, Wagtail, Django's), or
  `phoxtail_translations.W001` names the apps in the way. It also holds
  phoxtail's wording for sentences allauth and Django write
  (`packages/allauth/el.po`). `make translations` gathers and compiles both.

  Model fields and models carry translatable labels. Each app gains a
  `*_translatable_labels` migration that changes no table; a package with its
  own models on `UUIDMixin` or `TimestampMixin` sees a pending migration of the
  same kind until it generates one.
- `{% languages %}` (in `phoxtail_core_tags`) lists the languages a page can be
  read in, each with that page's address, and
  `phoxtail_core/language_menu.html` draws them as a menu; both are empty on a
  site that serves one language.
- One surface model for every page: the page or drawer is the ground
  (`phx-ground`: grey, near-black in dark mode, `--phx-ground-background`), what
  stands on it rises (`phx-card`, white with a light shadow, with
  `--clickable`, `--flush`, `__title`, `__text` and `__icon`), an edge-to-edge
  bar takes a card's colour with `phx-raised`, and what floats above
  everything is a `phx-popover`. Each box hands the controls it holds their fill
  and shadow (`--phx-control-background`, `--phx-control-shadow`), so a button
  is white and lifted on the page and a quiet tint inside a card. An admin view
  opts in with `{% block bodyclass %}phx-ground{% endblock %}`. Drawers read
  core values for their motion, edge shadow and scrim (`--phx-drawer-*`,
  `--phx-scrim-*`), and `--phx-floating-shadow` / `-up` shade a bar floating
  over the page.
- `.phx-button` is the one button: `--primary`, `--secondary`, `--danger`,
  `--full`, and sizes `--xsmall`, `--small` and `--large` around the default. A
  button marked `aria-current` wears the brand colour; a disabled one fades to
  0.38. Buttons and small controls are 44px tall from one variable,
  `--phx-size-small`, with 18px icons (`--phx-size-small-icon`).
- Indicators that show a state and never act: `phx-badge` (a count),
  `phx-tag` (a status in a word; `--small`, `--overlay`) and `phx-notice` (a
  status in a sentence). Tags and notices take a tone — `--success`,
  `--warning`, `--destructive` or `--info` — from the colour family of that
  name.
- Core draws a list page: `components/lists.css` (the page column, the card
  grid, the empty state, filters), `{% paginator %}` (First, Previous, five page
  numbers, Next and Last, keeping its width), and
  `phoxtail_core/page_header.html`, the one header every page extends (icon,
  title, subtitle, controls, a row below). The API Tokens, Remotes and Streams
  sync admin pages use them.
- `phoxtail_core/modal_drawer.html` gives the core modals a ready drawer at
  either level: a content view fills its title, body and actions, sets its width
  and where it sits (`side`: right, left or center), and how it closes
  (`dismiss="button"` for a secret shown once). `closeModal(element)` closes the
  modal holding that element, at whichever level, and
  `phoxtail.core.htmx.replace_modal()` answers with a modal in place of the one
  the request came from.
- An action announces what it changed under the model's own name, and what shows
  that model redraws itself: `phoxtail.core.htmx.change_event()`,
  `changed(Model, message)` (204, the change, `closeModal`, a toast) and
  `{% changed_event 'app_label.Model' %}`.
- A template draws a form field with `{% field "input" form.email %}` (from
  `phoxtail_core_tags`), or with `{% field form.email %}` to let the widget pick
  its template, and a view with
  `phoxtail.core.fields.render_field("input", form["email"])`; both use Django's
  own field rendering. Options are passed by name; a misspelled form field, an
  option the field does not take or a template name with a folder fails with an
  error, and `manage.py check` reports a bad `{% field %}` call with its file and
  line before its page is drawn. `{% widget field class="…" %}` draws a control
  with phoxtail's attributes on top; any `hx_*` option becomes an `hx-*`
  attribute when the control makes a request.
- New fields: `search` (a list's search bar, with a clear button and a result
  count), `date_stepper` (`‹ date ›` for a page showing one day or week),
  `week_stepper` (a week's seven days on one row, with arrows, a calendar and
  Today), `copy=True` on an input (a button that copies its value), the
  `choices` field's `phx-choices--1col`, and the `filled`/`small` look of
  `segmented_control` and `single_select_search` for toolbars.
- A page loads everything phoxtail's shared styles and scripts need with
  `{% include "phoxtail_core/stylesheets.html" %}` and
  `{% include "phoxtail_core/scripts.html" %}`; the first also applies the site's
  colours and fonts.
- `phoxtail.core.clocks` asks questions in each place's own clock time:
  `localize(value, zone)` reads a datetime given for a place and refuses one its
  clocks skip or show twice (the API answers 422 naming the offset to send);
  `on_local_clocks(zone_path, zones, condition)` asks a condition of each row in
  its own zone; and `filter_on_local_clocks(queryset, zone_path, zones,
  **lookups)` filters with bounds read on each row's clocks, which Django's
  `__date` and `Trunc` (one zone per query) cannot say.
- `phoxtail.core.dates.display_date` writes a date for people in the page's
  language ("Mon, Oct 5, 2026"), beside `iso_date` for machines. A datetime
  counts as its date, so turn it to the zone it should be read in first.
- `phoxtail.core.paging.every_item(fetch, **filters)` reads a whole paged list
  and raises `ListChanged` if the list moves while it reads; it needs no Django.
- `phoxtail.api.schema_names.clashing_schemas(api)` lists schema names two apps
  use for different shapes, which the OpenAPI document would otherwise silently
  merge.
- `phoxtail.core.testing` is a supported module: Django settings configured the
  way a hatched project is, wired through `wire_apps()`, with phoxtail's apps
  first, for packages that add an app to phoxtail and need a test environment.
  A package that appends its own app to `INSTALLED_APPS` after importing it
  calls `wire_apps(globals())` once more.
- `phoxtail net up`, `net down` and `net detach` take a slug to act on one
  attached project from anywhere.
- `translate`, `done_all`, `person_off`, `first_page` and `last_page` join the
  bundled Material Symbols.

### Changed

- **Breaking:** every list the API serves answers one page at a time, as
  `{"items": [...], "total": N}` instead of naming the list after the resource
  (`{"users": [...]}`, `{"pages": [...]}`, `{"palettes": [...]}`,
  `{"variants": [...]}`, `{"menus": [...]}`, `{"providers": [...]}` and so on).
  Pass `limit` (default 50, at most 500) and `offset` to read on; `total` counts
  every match, and the matching MCP tools take the same two arguments. Lists
  that used to arrive whole (collections, locales, sites, site-setting
  assignments, block categories) now arrive 50 at a time, and a search returns
  matches in the list's own order rather than ranked by relevance. Timestamps
  use one API-wide format (`2026-08-12T06:10:00.446Z`). `PUT
  /blocks/{id}/categories/` answers with the resulting list itself. `phoxtail
  studio dump` and `load`, the admin sync screens and `phoxtail content list`
  read every page, and stop with a message if a list changes while it is read or
  a remote runs a phoxtail from before lists were paged. Apps build their API on `phoxtail.api.pagination.Router`,
  which pages every list it serves.
- **Breaking:** API paths moved to the app that owns the data. Everything under
  `/api/content/v1/` is now `/api/cms/v1/`, beside `/api/cms/v1/site-settings/`;
  images, documents, video and audio are at `/api/media/v1/`; internal links are
  at `/api/core/v1/internal-links/`. Update any client calling the old paths and
  run `collectstatic` so the shipped JS follows. The MCP tools and the
  `phoxtail content` CLI keep their names.
- **Breaking:** API endpoints receive an `AuthorizationContext` as
  `request.auth` instead of a `User`: `request.auth.user` is the person,
  `request.auth.token` the credential (`None` for a browser session).
  Predicates passed to `Authorize` receive the context, and
  `phoxtail.tokens.auth.authenticate()` returns the `AccessToken` rather than
  its user.
- **Breaking:** access tokens say whether they are unrestricted. A token carries
  scopes or is marked `unrestricted`, and issuing one requires choosing. The
  `"*"` wildcard is gone, because installing an app silently widened every token
  already in circulation. Tokens issued with `"*"` are not converted: they are
  refused wherever a scope is checked, until re-issued.
- **Breaking:** an app declares its HTTP API and MCP tools one way only, by
  convention: subclass `PhoxtailAppConfig` and ship `api/` declaring `versions`
  (and `page_schemas`) and `mcp/`. The `api_version_router` attribute, the
  `phoxtail.mcp_modules` entry-point group, `[mcp] extra_modules` in
  `phoxtail.toml` and `PhoxtailAppConfig.page_schema_contributors` are gone.
  Every phoxtail app now declares its own this way; the `operationId` values in
  the OpenAPI schema change with the module paths. The agent app's
  `providers`, `artifacts` and `settings` endpoints no longer disappear when
  the `chatbot` extra is missing. A new project's own app subclasses
  `PhoxtailAppConfig`, so it can grow a surface the same way.
- The users and genders endpoints ask for the Django permission each act needs
  (`phoxtail_users.view_user` and its siblings) instead of a superuser account,
  so a person granted exactly that permission, through a group or directly, can
  be given exactly that much. Superusers are unaffected. Every endpoint's refusal
  names the permission missing, and the MCP tools name the same codenames as
  their endpoints, so a token narrowed to less than an act is not offered the
  tool that performs it.
- The MCP server is built on `fastmcp` and speaks the stateless MCP protocol
  (2026-07-28), so it can be restarted or replicated without dropping clients.
  `mcp>=1.29,<2` is replaced by `fastmcp-slim[server]`. The variant-editing
  session tools, which write files to the server's own disk, are offered only
  over a local connection.
- API requests made with an access token are answered in English unless they
  send `Accept-Language`; a logged-in browser still follows the language the
  person chose.
- The authentication pages — login, signup, password reset, login codes, email
  verification, reauthentication, sign out, email addresses, change and set
  password — are django-allauth's own pages drawn with phoxtail's look, so they
  follow allauth's behaviour and wording as it is upgraded. The private-page
  login, the page password prompt and the consent page share the same frame. The
  card sits in the middle of the page with the site's logo top left and, on a
  multilingual site, a language menu top right; the pages use the site's
  favicon (light and dark) and fonts; the orbs and grid behind the card are gone.
  Signup asks for the person first, then how to reach them, then the password,
  and the extra buttons phoxtail used to add are gone, as allauth draws none. A
  site that overrides one of allauth's `account/` templates keeps its copy.
- phoxtail needs django-allauth 65.20.1 or later, for allauth's fixes since
  65.18: rate limits that hold under concurrent requests, safer redirects when
  `ALLOWED_HOSTS` allows every host, and a cancelled login by code that no longer
  carries over. Relock with `uv lock --upgrade-package django-allauth`.
- The engine extra declares python-dateutil (2.8.2 or later, below 4), which
  `phoxtail.users` uses to count ages; installed versions do not change.
- Field templates moved from `phoxtail_core/forms/widgets/` to
  `phoxtail_core/forms/fields/`, and the `htmx/` copies are gone: the fields take
  `hx_get`, `hx_target`, `hx_swap`, `hx_trigger`, `hx_include` and `hx_vals`
  themselves. A template that includes the old paths switches to
  `{% field "select" form.status … %}`, a view to `render_field(…)`. The field
  stylesheet moved to `phoxtail_core/css/forms/fields.css`, and the field
  classes are renamed from `fw-` to `phx-` (`phx-field`, `phx-field__box`,
  `phx-toggle__track`, `phx-choice`, `--phx-field-gap`, …).
- Every field lets Django draw its control: `input`, `select`, `textarea`,
  `checkbox`, `toggle`, `phone` and `single_select_search` carry what the form
  declares (type, `required`, `maxlength`, `autocomplete`, …), screen readers hear
  each field's help text and errors, and a field template refuses a widget it
  cannot draw instead of drawing a broken field. A decimal in a language that
  writes it with a comma (Greek, German) now appears in its box, `maxlength`
  stops typing at the limit, and a password is never written back into the page.
  The `phone` field keeps its country and number on one row, its countries in
  the page's language and in dictionary order. `SingleSelectSearchField`
  declares `HiddenInput`, and its script lives once in `js/fields.js`, as do the
  password toggle and the picker buttons: a page drawing such a field includes
  `phoxtail_core/scripts.html`. A disabled field is drawn filled at full
  contrast instead of faded. Choice rows are 48px tall, and a toggle's row
  highlights on hover like a checkbox's. A search matches the start of a word,
  as the Streams Sync remote picker now does too.
- Country names come from the same source as the phone prefixes, in the page's
  language, everywhere a country is shown. Some English names change ("United
  States", "Trinidad & Tobago"); stored codes do not.
- The dashboard's navigation is one system with its pages. On a computer the
  sidebar is a floating card and the top bar is gone: the site's own pages sit
  behind a Website row and the language behind a row of its own. On a phone the
  menu opens as a drawer, the top bar floats in from the screen's edges with
  rounded corners, the dock marks the page you are on in the brand colour, both
  take a card's colour, and their ☰ and language buttons look like the dock's
  items. The top bar's site menu template
  (`phoxtail_dashboard/navigation/menu.html`) and its `dash-menu` classes are
  removed. The dashboard home's cards are core's clickable cards, and the profile
  page is a bento of four cards with an Edit drawer. A custom widget template that
  copied the old card markup moves to core's card classes (`dash-widget__*` and
  the profile's `usr-*` classes are gone), and a project overriding the profile's
  `user_info.html` or `index.html` moves its buttons into `user_info.html`. The
  content pane draws a slim, theme-aware scrollbar.
- `DashboardModule.remove_nav_item()` takes the item's `url_name` instead of its
  translated label.
- Drawers are solid instead of glass, parted from the page by their shadow. The
  API Tokens, Remotes and Streams Sync admin pages use core's list page, cards,
  search, paginator and drawers; a token is shown once in a dialog only its own
  buttons close. Their own stylesheets are gone, and empty lists show their title
  and text without an icon.
- Messages (toasts) are popovers with the modals' round close button, and their
  classes are renamed from `auth-toast*` to `phx-toast*`. A toast no longer
  closes the open modal; send the `closeModal` client event beside it to close
  the modal an action came from. Each core modal is named for assistive
  technology by its first heading. The modal close button and other round
  buttons are 44px.
- Every bundled icon is a Material Symbol; the block editor's field blocks and
  the dashboard menu editor use them too.
- A freshly hatched project's homepage stands on phoxtail's surfaces, with the
  wordmark at the size the authentication pages give a logo, and its phoenix
  respects reduced motion.
- Generated production compose files pin `nginx:1.31` and
  `certbot/certbot:v5.8.0` instead of taking the newest, so a deploy cannot move a
  site to a new release line unasked; fixes within nginx 1.31 still arrive. A
  deployed project regenerates its compose file with
  `phoxtail docker create compose production --registry --output .phoxtail/deploy/docker-compose.prod.yaml --force`
  and deploys again.
- `phoxtail server deploy` shows the difference and asks before replacing a
  server's `docker-compose.yaml` that differs from the local one. `.env` and
  `nginx.conf` are still uploaded only when the server has none.
- `phoxtail docker release` prints the commit each upgraded package moves to
  when it refreshes the lockfile, so its output says which commits go into the
  image.
- `phoxtail net peers` is a group: `net peers list` and `net peers get <slug>`.
  Scripts calling `net peers --json` say `net peers list --json`.
- The local swarm's router moves from Traefik 3.1 to 3.7.

### Removed

- Fields folded into others: `date`, `datetime`, `time`, `number` and
  `password` are drawn by `input`; `checkbox_multiple` and `radio_select` by
  `choices`; `choice_dropdown` by `select`; `null_boolean_select` by `select`
  with `phoxtail.core.fields.BooleanFilterSelect`; `segmented_control_choices`
  by `segmented_control`. Replace `{% field "<old>" … %}` with the new name. The
  `label_slice_index`, `label_off`, `label_on` and `locked` options are gone: the
  form field's choices (for weekdays, Django's `WEEKDAYS_ABBR`) and `disabled`
  say it. A `segmented_control` with no value ticks no segment, so give it an
  initial value.
- The `multi_select_chips` field, `MultiSelectChipsField` and
  `MultiSelectChipsSearchView`, which nothing drew.
- `single_select_search` no longer takes `is_active` (use `disabled=True`),
  `selected_item`, `available_items` or `widget_id`, and
  `SingleSelectSearchView` no longer takes `widget_id`: both read them from the
  form field.
- The `add_class` template filter (use `{% widget field class="…" %}`) and the
  dashboard's `dashboard_languages` tag (use `{% languages %}`).
- The `allauth/components/logo.html` and `submit_button.html` templates: the
  frame draws the logo, and `{% element button %}` draws a `phx-button`.
- The old admin paginator template and the `.phoxtail-btn` and
  `.phoxtail-danger-section` rules in `modal.css`.

### Fixed

- Certificate renewal no longer depends on the registry. Renewal started certbot
  with nginx and web, and web's `pull_policy: always` made it pull the site
  image first, so once the server's registry token expired, renewal failed
  silently and certificates lapsed. Certbot now runs with `--no-deps`. The cron
  line is installed only once, so on each existing server replace the
  `# phoxtail-ssl-<project>` line in `crontab -e` with:

      0 3 1,15 * * cd $HOME/<project> && docker compose run --rm -T --no-deps certbot renew -q && docker compose exec -T nginx nginx -s reload  # phoxtail-ssl-<project>
- File URLs the API hands out — images, documents, videos, audio, thumbnails and
  font files — are built on `WAGTAILADMIN_BASE_URL` instead of the hostname the
  caller used, so the MCP server no longer relays URLs pointing at its own
  container. `phoxtail net attach` writes `DOMAIN=<slug>.localhost`; a project
  already attached needs the line added to `.env` or a fresh `attach`.
- Confirming your password on the "Confirm Access" page no longer always fails
  for a user with a username, and a deactivated user sees "Account Inactive"
  instead of a wrong-password error. `phoxtail.users` adds allauth's
  authentication backend; a project that sets its own `AUTHENTICATION_BACKENDS`
  should add `allauth.account.auth_backends.AuthenticationBackend`.
- The phoxtail bar appears for anyone who can use something in it, not only
  superusers; granting `phoxtail_agent.access_chatbot` now shows the chat button.
- The chatbot acts as the person chatting: each turn mints a short-lived token
  owned by that person, revoked when the turn ends, so every tool call is
  attributed to them and the tool list is theirs. Its endpoints answer 503
  naming the `chatbot` extra when it is not installed.
- The phone number on the profile edit form can be saved again, and the profile
  drawer stays open when a save fails.
- Fetching an SVG image no longer answers 500.
- Deleting a collection asks Wagtail what is inside it, so the API refuses
  exactly what the admin refuses, including other apps' contents and
  grandchildren.
- Asking for a block's context with reference variants no longer fails, and a
  blank required field on a variant collection, block or block category is
  refused with 422 naming it; `phoxtail studio load` reports such a file as a
  warning and carries on.
- The API documentation shows each schema once: page-body blocks are
  `BodyBlock*` and streams collections `VariantCollection*`, and the two ways in
  (Bearer token, session cookie) are listed once each.
- `phoxtail.users` brings `sorl.thumbnail` into `INSTALLED_APPS` when settings
  are wired.
- The CLI starts several times faster: heavy imports load only in the commands
  that use them.
- Pages say which language they are in (`<html lang>`), and the dashboard's
  labels, its "Log in" button and "Last Name" are translated in every language
  Wagtail translates them into.
- On an iPhone or iPad, a date or time field's calendar or clock button opens
  the picker.
- Typing in a `single_select_search` field no longer fails with a
  `FilterFieldError` when the form narrows the field's choices. A model searched
  this way declares `index.FilterField("id")` in its `search_fields`, and
  `manage.py check` names any that does not.
- The seven-column choice grid switches on its own width, so its labels are not
  cut in a narrow drawer.
- The password toggle and a message's close button are announced properly to
  screen readers.

### Security

- An API endpoint that declares no `auth=`, under a router that declares none,
  now refuses every caller: 401 for anonymous, 403 for everyone else. Before, it
  admitted any logged-in user and any unrestricted token, so an app whose
  endpoints were not annotated let any logged-in user read and change its data.
  Such endpoints stop answering until they declare `auth=guarded(...)`,
  `scoped(...)` or `authenticated()`. `/api/ping/` admits any valid credential.
- Endpoints that asked for nothing beyond being logged in now ask for the
  permission their act needs, so any account could no longer:
  - read every page as its latest draft, including unpublished edits
    (`/api/cms/v1/pages/`), or photograph one through the screenshot views;
    reads narrow to the pages the caller holds a Wagtail grant on, and others
    answer 404;
  - list, download, move or delete every image, document, video and audio file
    (`/api/media/v1/`); permissions are asked per collection, as Wagtail's admin
    asks;
  - rewrite every block and variant, or push and pull them across projects
    (`/api/streams/v1/`);
  - rewrite the palettes and fonts every page renders with (`/api/design/v1/`),
    or a site's branding, font and palette settings, now asked per site;
  - add an inference provider or repoint a site's default model
    (`/api/agent/v1/`);
  - read or change a site's menu, or rename or delete an internal link;
  - list every site and locale (`view_site`, `view_locale`);
  - read a block's field schema and every reference variant's code through
    `POST /api/streams/v1/context/` (now `view_block` and `view_blockvariant`).

  The studio tools that reach past their app name what they reach
  (`phoxtail_studio_render_block` and `phoxtail_studio_screenshot_page` name
  `access_chatbot`), so they are not offered to tokens narrowed to something
  else.

  Collection endpoints now admit the people Wagtail permits per branch, which
  `has_perm` never saw. The menu, media and collection pickers require an
  operator instead of chat access.
- A font's name or fallback list, or a font or palette role's identifier, could
  close the `<style>` element every page carries and run a script for every
  visitor, the authentication pages included. Each value is escaped as the CSS
  is built, and the admin, the API and the MCP tools refuse values that are not
  font names or identifiers.
- Generated Dockerfiles install packages with uv 0.13.5, which no longer trusts
  the distrusted emSign certificate authority
  ([GHSA-hq85-5cpj-mr62](https://github.com/astral-sh/uv/security/advisories/GHSA-hq85-5cpj-mr62)).
  An existing project regenerates its Dockerfile with
  `phoxtail docker create dockerfile --force`, which overwrites local edits, so
  diff it against a copy first.

## [0.2.0] — 2026-09-07

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

[0.4.0]: https://github.com/phoxmor/phoxtail/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/phoxmor/phoxtail/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/phoxmor/phoxtail/compare/v0.1.1...v0.2.0
