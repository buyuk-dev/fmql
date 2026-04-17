.PHONY: help format lint test cov

PKG_PATHS := packages/fmql/src packages/fmql/tests \
             packages/fmql-semantic/src packages/fmql-semantic/tests

help:
	@echo "Targets:"
	@echo "  format  - run black across all packages"
	@echo "  lint    - run ruff and black --check across all packages"
	@echo "  test    - run pytest for every package"
	@echo "  cov     - run pytest with coverage (fmql: fails under 84%)"

format:
	uv run black $(PKG_PATHS)

lint:
	uv run ruff check $(PKG_PATHS)
	uv run black --check $(PKG_PATHS)

test:
	cd packages/fmql && uv run pytest
	cd packages/fmql-semantic && uv run pytest

cov:
	cd packages/fmql && uv run pytest \
		--cov=fmql --cov-report=term-missing --cov-report=xml \
		--cov-fail-under=84
