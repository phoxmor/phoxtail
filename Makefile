# Linting & Formatting
lint:
	-uv run ruff check --fix phoxtail/
	uv run ruff format phoxtail/

lint-check:
	uv run ruff check phoxtail/
	uv run ruff format --check phoxtail/

# Testing
test-cli:
	uv run pytest phoxtail/cli/tests/ -p no:django $(ARGS)

test-engine:
	uv run pytest phoxtail/core/tests/ phoxtail/streams/tests/ phoxtail/dashboard/tests/ $(ARGS)

test-booking:
	uv run pytest phoxtail/booking/core/tests/ phoxtail/booking/events/tests/ phoxtail/booking/subscriptions/tests/ phoxtail/booking/reservations/tests/ $(ARGS)

test-tokens:
	DJANGO_SETTINGS_MODULE=phoxtail.tokens.tests.settings uv run pytest phoxtail/tokens/tests/ $(ARGS)

test:
	uv run pytest $(ARGS)

test-cov:
	uv run pytest --cov --cov-report=term-missing $(ARGS)
