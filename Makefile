.PHONY: install test lint format typecheck build clean all

install:
	uv sync --extra dev

test:
	uv run pytest

lint:
	uv run ruff check src tests

format:
	uv run ruff format src tests

typecheck:
	uv run mypy

build:
	uv build

clean:
	rm -rf dist/ .coverage coverage.xml .pytest_cache .mypy_cache .ruff_cache

all: lint typecheck test
