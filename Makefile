.PHONY: help format lint test cov

help:
	@echo "Targets:"
	@echo "  format  - run black on src/ and tests/"
	@echo "  lint    - run ruff and black --check"
	@echo "  test    - run pytest"
	@echo "  cov     - run pytest with coverage (fails under 84%)"

format:
	uv run black src tests

lint:
	uv run ruff check src tests
	uv run black --check src tests

test:
	uv run pytest

cov:
	uv run pytest --cov=fmq --cov-report=term-missing --cov-report=xml --cov-fail-under=84
