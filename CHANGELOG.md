# Changelog

All notable changes to Phoxtail are recorded here, in the format of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Phoxtail is pre-1.0 and follows [Semantic Versioning](https://semver.org/) with
one caveat: **minor releases may contain breaking changes** until 1.0. Pin a
version you have tested.

Migrations carry their own pre-1.0 clause: the history may be rebased, in which
case upgrading means re-hatching or rebuilding the database rather than
migrating into it. Any release that does so says so here.

## [Unreleased]

### Added

- `DCO` — contributions are certified under the Developer Certificate of Origin.
- `CONTRIBUTING.md` — setup, linting, tests, commit conventions and sign-off.
- `SECURITY.md` — how to report a vulnerability privately.
- This changelog.

### Changed

- **Breaking for existing projects.** `playwright` and `Pillow` are no longer
  installed by default. They moved to a new `studio` extra, which carries the
  screenshot tools in `phoxtail.mcp.studio` and nothing else — a base install
  no longer pulls a browser stack it may never use.

  Newly hatched projects get `phoxtail[studio]` in their `dev` dependency
  group, and projects still on the `phoxtail[dev]` alias keep it because that
  alias now includes `studio`. Projects that already moved to the
  `dev-tools` + dependency-group layout must add it themselves —
  `phoxtail upgrade` advances the lockfile without rewriting `pyproject.toml`:

  ```toml
  [dependency-groups]
  dev = [
      "phoxtail[dev-tools]",
      "phoxtail[studio]",
  ]
  ```

  Then run `uv lock`; the Dockerfile syncs with `--frozen` and refuses a
  lockfile that no longer matches. Without the entry the development image
  fails at `playwright install`. Production images are unaffected, and lose a
  browser stack they were never using.
- One migration was folded away as a no-op. **No action required**: it set no
  SQL, so a database that already applied it is unchanged and the leftover
  history row is ignored.
- `LICENSE` names the copyright holder as a person rather than a trade name.
- The README's contributing link points at `CONTRIBUTING.md` instead of a
  documentation page that does not exist.

## Earlier versions

Versions 0.1.0 through 0.1.2 predate this changelog and were never published to
PyPI. Their history is in the commit log:

- [0.1.1...main](https://github.com/phoxmor/phoxtail/compare/v0.1.1...main)
- [0.1.0...0.1.1](https://github.com/phoxmor/phoxtail/compare/v0.1.0...v0.1.1)

[Unreleased]: https://github.com/phoxmor/phoxtail/compare/v0.1.1...main
