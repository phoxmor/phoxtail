# Linting & Formatting
lint:
	-uv run ruff check --fix phoxtail/
	uv run ruff format phoxtail/

lint-check:
	uv run ruff check phoxtail/
	uv run ruff format --check phoxtail/

# The package ships py.typed, so its annotations are a contract with users.
# A ratchet, not a clean bill of health: the full report always prints, and
# the run fails only if the count climbs above the ceiling. The ceiling is
# scaffolding — it exists so the check can be enforced before the backlog is
# cleared, and it is only ever allowed to go down. The destination is zero,
# at which point this whole block reduces to plain `uv run mypy`.
MYPY_CEILING = 74

typecheck:
	@report=$$(uv run mypy phoxtail/ $(ARGS) 2>&1); status=$$?; \
	echo "$$report"; \
	[ $$status -gt 1 ] && { echo "mypy did not run (exit $$status)"; exit $$status; }; \
	count=$$(echo "$$report" | sed -n 's/^Found \([0-9]*\) error.*/\1/p'); \
	case "$$report" in *"Success: no issues found"*) count=0 ;; esac; \
	if [ -z "$$count" ]; then \
		echo "mypy printed no summary — treating as a run that did not happen"; exit 1; \
	elif [ $$count -gt $(MYPY_CEILING) ]; then \
		echo "mypy: $$count errors, ceiling is $(MYPY_CEILING)"; exit 1; \
	else \
		echo "mypy: $$count errors, at or under the ceiling of $(MYPY_CEILING)"; \
	fi

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
