# CWYD v2 developer convenience targets.
#
# Pillar: Stable Core (developer tooling)
# Phase: 2 / cleanup audit batch 2
#
# This Makefile is intentionally tiny: it wraps `uv` invocations so
# every target works from a clean checkout with no Python on $PATH
# beyond what `uv` provisions (`uv` bootstraps the interpreter via
# `pyproject.toml`'s `requires-python`).
#
# Usage from the `v2/` directory:
#   make typecheck   # Q13: static type check (pyright --strict scoped via pyproject)
#   make test        # full pytest suite
#   make lint        # black + flake8

.PHONY: typecheck test lint

typecheck:
	uv run pyright

test:
	uv run pytest

lint:
	uv run black --check src tests
	uv run flake8 src tests
