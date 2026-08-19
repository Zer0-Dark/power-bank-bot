# Power Bank Bot

A Telegram bot for a virtual bank game — accounts, balances, transfers, and
rendered card/receipt images.

- **Stack & architectural decisions:** [docs/TECH_STACK.md](docs/TECH_STACK.md)
- **Status:** Phase 1a done — bot skeleton runs; render pipeline is next.

## Setup

```bash
uv sync                     # install
cp .env.example .env        # then put your @BotFather token in BOT_TOKEN
make migrate                # create the schema (SQLite by default)
make run                    # start polling
```

## Commands

| | |
|---|---|
| `make run` | start the bot |
| `make test` | run tests |
| `make lint` / `make fmt` | ruff check / format |
| `make migrate` | apply migrations |
| `make revision m="..."` | autogenerate a migration |

## Layout

Dependencies point one direction only:

```
core/      config, logging, exceptions     (depends on nothing)
db/        models, session                 (-> core)
services/  business logic, no aiogram      (-> db, core)
render/    Pillow image generation         (-> core)
bot/       telegram handlers, middlewares  (-> all of the above)
```

Handlers receive `session` and `user` as kwargs from middleware and never call
`commit()` themselves — the session commits on clean return, rolls back on
exception.
