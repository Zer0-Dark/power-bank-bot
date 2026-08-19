# Power Bank Bot

A Telegram bot for a virtual bank game — accounts, balances, transfers, and
rendered card/receipt images.

- **Stack & architectural decisions:** [docs/TECH_STACK.md](docs/TECH_STACK.md)
- **Status:** Phase 1b done — invite-only access with roles. Render pipeline is next.

## Setup

```bash
uv sync                     # install
cp .env.example .env        # set BOT_TOKEN and SUPER_ADMIN_IDS
make migrate                # create the schema (SQLite by default)
make run                    # start polling
```

## Access

The bot is invite-only. Nobody can use it unless an admin added them.

| Role | Can grant | Can revoke |
|---|---|---|
| super_admin | user, admin | admin, user |
| admin | user, admin | admin, user (never self) |
| user | — | — |

Super admins come from `SUPER_ADMIN_IDS` in `.env` and are seeded at every
startup — the bot itself cannot create one, since nobody can remove one.

Admin commands: `/add <id|@user> [user|admin]`, `/remove <id|@user>`,
`/members`, `/who <id|@user>`, `/attempts`.

Everyone who messages the bot is recorded even without access, so `/who` and
`/add @username` work once the person has said hello — and `/attempts` shows who
has been knocking.

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
