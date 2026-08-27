# Contributing to know-your-bible

## Setup

This project uses [Poetry](https://python-poetry.org/) with an in-project
virtualenv (Python >=3.12, <4.0).

```bash
poetry install
cp env.example .env   # then fill in OAuth creds and SESSION_SECRET_KEY
```

## Development server

```bash
poetry run uvicorn app.main:app --port 5669
```

The SQLite database is created automatically at `data/app.db` on startup
(WAL mode). Override the location with `DATABASE_URL` in `.env`.

## Pre-commit

Install both hook sets:

```bash
poetry run pre-commit install
poetry run pre-commit install --hook-type commit-msg
```

Run against all files:

```bash
poetry run pre-commit run --all-files
```

Hooks: trailing-whitespace/end-of-file fixers, ruff (lint + format), black,
and mypy.

## Testing

```bash
poetry run pytest -v
```

Tests use an in-memory SQLite database via `sqlite+aiosqlite:///:memory:`.
Markers:

- `asyncio`: async coroutine tests (auto mode via pytest-asyncio)
- `integration`: live integration tests

## Optional dependency group

Scraper scripts under `data/` need extra packages not required at runtime:

```bash
poetry install --with scraping
```

## Conventions

- Formatting: black + ruff-format, line length 79
- Linting: ruff (`B,D,E,ERA,F,I,N,PL,RUF,W`), numpy docstring convention
- Type checking: mypy targeting Python 3.12
- Commits: conventional commits (commitizen)
