# Contributing to Phoxtail

Thanks for considering it. Phoxtail is early — before 1.0 the surface still moves,
so an issue describing what you want to change is usually a better first step than
a large pull request.

## Getting set up

```bash
git clone https://github.com/phoxmor/phoxtail.git
cd phoxtail
uv sync --all-extras
```

`uv sync` creates `.venv`, installs Phoxtail into it in editable mode, and
resolves every optional dependency group — the same command CI runs. Prefix
commands with `uv run`, or activate the environment with
`source .venv/bin/activate`.

Python 3.11 or newer. Working on the engine, the dashboard or the chatbot also
needs PostgreSQL and Docker.

To *use* the CLI rather than work on it, install it as a tool instead — it lands
on your `PATH` in its own isolated environment:

```bash
uv tool install phoxtail
```

## Linting and tests

```bash
make lint          # ruff check --fix, then ruff format
make lint-check    # the same, without writing — what CI runs
make test          # the full suite
make test-cli      # the CLI suite alone
make test-engine   # core, streams and dashboard
```

CI runs two more checks, both available locally:

```bash
make typecheck         # mypy; fails only if the error count grows
make check-migrations  # fails if a model has no matching migration
```

Run `make lint` and the suite covering what you touched before opening a pull
request. Anything that changes behaviour needs a test; anything that changes a
model needs a migration.

## Commits

Conventional commits, matching the existing log:

```
fix(dashboard): keep the sidebar collapsed across reloads
feat(cli): add --dry-run to phoxtail db restore
docs: describe the hatch wizard steps
```

Common scopes are the package a change lives in — `cli`, `core`, `engine`,
`dashboard`, `agent`, `streams`, `mcp`. Write the subject as what the change
does, in the present tense, without a trailing period.

## Sign your commits — the DCO

Phoxtail uses the [Developer Certificate of Origin](DCO): a short statement that
you wrote the code you are submitting, or otherwise have the right to submit it
under this project's licence. There is nothing to sign and no account to create.
You certify it by adding a `Signed-off-by` line to each commit:

```bash
git commit -s -m "fix(cli): resolve the config path relative to the project root"
```

`-s` appends the line for you, using your configured `user.name` and
`user.email`:

```
Signed-off-by: Your Name <you@example.com>
```

Use a real name and an address you can be reached at. A bot checks every commit
in a pull request and will tell you if one is missing; `git rebase --signoff main`
fixes a branch retroactively.

You keep the copyright in what you contribute. It is licensed to everyone under
the BSD 3-Clause terms in [LICENSE](LICENSE), the same as the rest of Phoxtail.

## Pull requests

Branch from `main`, keep the change focused, and describe what problem it solves
rather than what files it touches. Green CI — lint and tests — is required to
merge.

## Code of conduct

Participation is covered by the [Contributor Covenant](CODE_OF_CONDUCT.md),
unmodified. Report unacceptable behaviour to **conduct@phoxtail.com** — that
address is read by the maintainers and is separate from security reports.

## Reporting a security issue

Do not open a public issue. See [SECURITY.md](SECURITY.md).

## Questions

[community.phoxtail.com](https://community.phoxtail.com/) for discussion,
[GitHub issues](https://github.com/phoxmor/phoxtail/issues) for bugs and feature
requests.
