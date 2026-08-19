# Power Bank Bot

A Telegram bot for a virtual bank game — accounts, balances, transfers, and
rendered card/receipt images.

- **Stack & architectural decisions:** [docs/TECH_STACK.md](docs/TECH_STACK.md)
- **Status:** Phase 1d done — Arabic UI, invite-only access with roles, menu-driven. Render pipeline is next.

## Setup

```bash
uv sync                     # install
cp .env.example .env        # set BOT_TOKEN and SUPER_ADMIN_IDS
make migrate                # create the schema (SQLite by default)
make run                    # start polling
```

## Language

The UI is Arabic. All text lives in `powerbank/bot/views.py` and
`powerbank/bot/keyboards/menu.py` — nothing user-facing is inlined in handlers.

Latin runs (@usernames, IDs, commands) **must** be wrapped with `ltr()` or
`code()` from `powerbank/core/text.py`. Bare Latin inside an Arabic paragraph
reorders visually on the client; tests in `tests/test_views.py` enforce this.

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

Every one of those also has a button in the admin panel — `/start` opens the
menu. Running a command with no arguments starts the same guided flow the
button does, so `/add` and the ➕ button behave identically.

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
