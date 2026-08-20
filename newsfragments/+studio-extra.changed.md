**Breaking for existing projects.** `playwright` and `Pillow` are no longer
installed by default. They moved to a new `studio` extra, which carries the
screenshot tools in `phoxtail.mcp.studio` and nothing else — a base install no
longer pulls a browser stack it may never use.

Newly hatched projects get `phoxtail[studio]` in their `dev` dependency group,
and projects still on the `phoxtail[dev]` alias keep it because that alias now
includes `studio`. Projects that already moved to the `dev-tools` +
dependency-group layout must add it themselves — `phoxtail upgrade` advances the
lockfile without rewriting `pyproject.toml`:

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
