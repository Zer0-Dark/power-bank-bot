.PHONY: install run lint fmt test migrate revision

install:
	uv sync

run:
	uv run python -m powerbank

lint:
	uv run ruff check .

fmt:
	uv run ruff format . && uv run ruff check --fix .

test:
	uv run pytest

migrate:
	uv run alembic upgrade head

# make revision m="add accounts table"
revision:
	uv run alembic revision --autogenerate -m "$(m)"
