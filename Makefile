# Linting & Formatting
lint:
	-uv run ruff check --fix phoxtail/
	uv run ruff format phoxtail/

lint-check:
	uv run ruff check phoxtail/
	uv run ruff format --check phoxtail/

# The package ships py.typed, so its annotations are a contract with users.
# Any error fails the run; the configuration lives in pyproject.toml so the
# Makefile, an editor and CI all read the same rules.
typecheck:
	uv run mypy phoxtail/ $(ARGS)

# Packaging
# Setuptools caches a file list in the egg-info directory, and a stale one
# serves the old list — which makes a correct packaging fix read as inert.
# Cleaning first costs nothing and removes the trap rather than documenting it.
build:
	rm -rf dist build phoxtail.egg-info
	uv build $(ARGS)

# Migrations
# The autodetector compares models to migration files, so a model edited
# without a matching migration reports here and nowhere else.
check-migrations:
	DJANGO_SETTINGS_MODULE=phoxtail.core.tests.settings \
	uv run python -m django makemigrations --check --dry-run $(ARGS)

# Translations
# Run after changing any sentence a person reads, as makemigrations after a
# model: it gathers every marked sentence into each language's list, keeping
# what is translated and dropping what is gone, then compiles each list with
# phoxtail's corrections to other packages' sentences. It ends by naming what
# is left to translate; translate those in the .po and run it again.
MAKEMESSAGES = --all --no-obsolete \
	--ignore='tests/*' --ignore='*/tests/*' --ignore='cli/*' \
	--ignore='project_template/*' --ignore='*/static/*'

translations:
	cd phoxtail && DJANGO_SETTINGS_MODULE=phoxtail.translations.tests.settings \
	uv run python -m django makemessages $(MAKEMESSAGES)
	uv run python -m phoxtail.translations.compile

# Fails when the run above was forgotten: a sentence new or gone in the code,
# or one left to translate. Gathers in a copy, so it never writes the lists.
translations-check:
	DJANGO_SETTINGS_MODULE=phoxtail.translations.tests.settings \
	uv run python -m phoxtail.translations.verify $(MAKEMESSAGES)

# Testing
test-cli:
	uv run pytest phoxtail/cli/tests/ -p no:django $(ARGS)

test-engine:
	uv run pytest phoxtail/core/tests/ phoxtail/streams/tests/ phoxtail/dashboard/tests/ $(ARGS)

test-tokens:
	DJANGO_SETTINGS_MODULE=phoxtail.tokens.tests.settings uv run pytest phoxtail/tokens/tests/ $(ARGS)

test:
	uv run pytest $(ARGS)

test-cov:
	uv run pytest --cov --cov-report=term-missing $(ARGS)

# Installs every direct dependency at exactly the floor pyproject.toml declares,
# then runs the suite against it — so a floor is a measured claim rather than a
# guess. `lowest-direct` leaves transitive dependencies at their newest, which
# is what a user with an old pinned project actually gets.
#
# UV_PROJECT_ENVIRONMENT redirects the venv: a plain `uv sync` here would
# replace .venv with the floor versions and leave the working environment
# quietly downgraded. It rewrites uv.lock regardless — untracked, but note that
# `uv lock` afterwards re-resolves to current versions rather than restoring
# what the file held before.
#
# Built from scratch each time, and --upgrade is what makes it a check at all.
# uv sync re-resolves only when the existing lock violates pyproject.toml, and
# lowering a floor violates nothing — so without it, the one edit this target
# exists to catch is the one it cannot see. CI has no lockfile and resolves
# regardless, which is how that gap would have survived: green here, real only
# there.
FLOORS_ENV ?= .floors-venv
test-floors:
	rm -rf $(FLOORS_ENV)
	UV_PROJECT_ENVIRONMENT=$(FLOORS_ENV) \
	uv sync --all-extras --resolution lowest-direct --upgrade --python 3.11
	$(FLOORS_ENV)/bin/python -m pytest $(ARGS)
