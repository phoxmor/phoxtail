# Linting & Formatting
lint:
	-uv run ruff check --fix phoxtail/
	uv run ruff format phoxtail/
	uv run djhtml phoxtail/

lint-check:
	uv run ruff check phoxtail/
	uv run ruff format --check phoxtail/
	uv run djhtml --check phoxtail/

# Testing
test-cli:
	uv run pytest phoxtail/cli/tests/ -p no:django $(ARGS)

test-engine:
	uv run pytest phoxtail/core/tests/ phoxtail/streams/tests/ $(ARGS)

test:
	$(MAKE) test-cli
	$(MAKE) test-engine

test-cov:
	uv run pytest phoxtail/cli/tests/ -p no:django --cov --cov-report=term-missing $(ARGS)
	uv run pytest phoxtail/core/tests/ phoxtail/streams/tests/ --cov --cov-append --cov-report=term-missing $(ARGS)
