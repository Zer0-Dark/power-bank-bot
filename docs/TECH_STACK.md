# Tech Stack — Power Bank Bot

**Status:** decided, 2026-08-19
**Language:** Python 3.12+

---

## Why Python

The core novelty of this bot is rendering data onto pre-designed images (balance
cards, coin graphics, receipts). That work is the part we will iterate on most,
so we pick the ecosystem where iteration is cheapest.

- **Pillow** draws text and pastes layers in a few lines, synchronously, with no
  system dependencies beyond a font file.
- Node's `sharp` has no real text API (text = generating SVG strings and
  compositing them), and `node-canvas` needs native Cairo builds that break on
  deploy.

Telegram library quality is a wash between the two ecosystems, so it does not
factor into the decision.

---

## Stack

| Layer | Choice | Notes |
|---|---|---|
| Bot framework | **aiogram 3.x** | async, router-based, built-in FSM for multi-step flows (transfers, registration) |
| Image rendering | **Pillow (PIL)** | template PNG + text layers |
| Arabic text | **arabic-reshaper** + **python-bidi** | only if we render Arabic names/labels |
| ORM | **SQLAlchemy 2.0** (async, asyncpg driver) | typed models, async session |
| Database | **SQLite** → **PostgreSQL** | SQLite for local dev; Postgres before real users |
| Migrations | **Alembic** | set up from commit one, not later |
| Cache / rate limit | **Redis** | optional at first; add when render caching or throttling is needed |
| Config | **pydantic-settings** | `.env` → typed settings object |
| Dep management | **uv** | fast, lockfile, single tool |
| Lint / format | **ruff** | lint + format in one |
| Tests | **pytest** + **pytest-asyncio** | |
| Deploy | **Docker** + long polling | switch to webhooks only if scale demands it |

### Alternatives considered
- `python-telegram-bot` — solid, but aiogram's router/FSM model scales better once
  the command surface grows.
- `Node + grammY + sharp` — see "Why Python" above.
- `Django` — too heavy; we need no admin site or HTTP layer yet.

### Why not MongoDB (checked 2026-08-19)

The target VPS already runs MongoDB, so reusing it was the obvious way to avoid a
second database. We checked whether it could carry the money side:

```
mongosh --quiet --eval "try { rs.status().ok } catch(e) { print('standalone') }"
→ standalone
```

MongoDB only supports multi-document ACID transactions on a **replica set**. A
standalone `mongod` has none. Every transfer touches two accounts plus a ledger
row, so transactions are non-negotiable.

Converting it to a single-node replica set would work and takes ~10 minutes. But
that is the *immediate* blocker, not the main argument — even a clean Mongo replica
set would leave the point below unaddressed.

The deciding factor: money invariants are enforced by Postgres itself, versus code
we write and maintain by hand in Mongo. Specifically, Postgres gives us
the invariants we would otherwise hand-roll:

- `CHECK (balance >= 0)` — the DB refuses to overdraw regardless of Python bugs
- foreign keys — no ledger rows pointing at accounts that do not exist
- `SUM(amount)` reconciliation of cached balances against the ledger, in one query
- Alembic — versioned, reviewable schema changes

Cost is roughly 50MB idle RAM on a 4GB VPS. Acceptable.

**Rejected:** splitting storage (Mongo for game data, Postgres for money). Two
backup stories, two pools, and no transaction can span both. Not worth it at this
size.

---

## Architectural rules (decided up front)

### 1. Money is integers, always
Balances stored as `BIGINT` in the **smallest unit** (1 coin = 100 units).
Never `float`, never `Decimal` in the DB column. Format for display only at the
render layer. Retrofitting this after users hold balances is extremely painful.

### 2. Ledger, not a mutable balance
Do **not** store `users.balance` as the source of truth and mutate it.

- `transactions` table is append-only: `(id, from_account, to_account, amount,
  type, ref, created_at)`.
- Balance is derived, then cached (`accounts.cached_balance` + a recompute job).
- Every transfer is one DB transaction writing paired ledger rows.

This gives us auditability the first time someone claims the bot ate their coins,
and makes transfers atomic by construction.

### 3. Image rendering is blocking — isolate it
Pillow is CPU-bound and will stall the event loop. Every render call goes through
`asyncio.to_thread(...)`. Renders return `BytesIO`, never a temp file on disk.

### 4. Templates are data, not code
One render function per template:

```python
def render_balance_card(username: str, balance: int, avatar: Image | None) -> BytesIO
```

Coordinates, font sizes, and colors live in a JSON config beside the template
asset — **not** hardcoded in the function. We will move that text twenty times.

### 5. Access is invite-only, enforced by middleware

The bot is closed. A person may use it only if an admin put them in the
database.

**Roles** (`core/roles.py`): `none` < `user` < `admin` < `super_admin`.

- `none` means "seen but not a member". Every sender is recorded regardless of
  access -- that is what lets an admin search someone by @username later, and
  gives a record of who tried to get in (`denied_attempts`, `last_denied_at`).
- **Super admins come from `SUPER_ADMIN_IDS` only.** The bot cannot mint one,
  because nobody can remove one -- a mistaken promotion would be permanent.
  Seeding only ever promotes; dropping an id from the env never demotes, so a
  config typo cannot strip access.

**Permission matrix** -- pure predicates in `core/roles.py`, tested exhaustively:

| Actor | Can grant | Can revoke |
|---|---|---|
| super_admin | user, admin | admin, user |
| admin | user, admin | admin, user (never self) |
| user | — | — |

Nobody can revoke a super admin, and nobody can revoke themselves (for the last
admin that would be unrecoverable).

The gate is `AccessMiddleware`, registered last so it sees a resolved user.
Handlers therefore never check access themselves. Admin handlers are filtered by
`IsStaff` *and* re-checked in the service layer, so a filter mistake alone
cannot escalate rights.

### 6. One screen, two entry points

Every feature is reachable by button *and* by command. Both render through
`bot/views.py`, so the two cannot drift apart as features are added, and
`bot/screens.py` hides the difference between "send a new message" (command)
and "edit the one on screen" (button).

- **Callback payloads are typed** (`bot/callbacks.py`). They come from the
  client and are capped at 64 bytes, so they are parsed into models rather than
  split by hand -- a malformed payload fails the filter instead of reaching a
  handler. Destructive actions carry their target *in the payload*, so a stale
  button cannot act on a newer target.
- **Callback queries are gated too.** `router.callback_query.filter(IsStaff)`
  sits alongside the message filter; a button is as much an entry point as a
  command. Non-members get an answered toast rather than silence, which would
  hang their client.
- **Router order is load-bearing.** `menu` is registered before `admin` because
  admin flows wait on free text, and a state handler would otherwise swallow
  /start and strand the user mid-flow. Asserted in tests.
- **The native "/" menu is role-scoped** (`bot/commands.py`): admin commands are
  published only to the chats of people holding the role, and re-synced the
  moment a role changes rather than at the next restart.

### 7. Arabic only, with bidi isolation

The UI is Arabic. There is no translation layer: text lives behind
`bot/views.py`, so adding a second language later is a mechanical change to one
module rather than a hunt through handlers. Building i18n machinery to serve one
language would be maintenance for a hypothetical.

**The real hazard is bidi mixing, not translation.** Arabic screens are full of
Latin runs -- @usernames, numeric IDs, command names, the brand. Left bare, the
Unicode bidi algorithm reorders the punctuation and digits around them, so
`(436677576)` renders with the parenthesis on the wrong side. It looks broken
only on a real client, never in a terminal, which makes it expensive to catch
late.

So every Latin run goes through `core/text.py`:

- `ltr(x)` — wrap in FSI/PDI so the run's direction resolves independently
- `code(x)` — a monospace span with the isolates *outside* the tag
- `cmd(name)` — isolates only the command token

**Never isolate a mixed run.** FSI infers direction from the first strong
character, so wrapping Arabic+Latin together forces the whole span LTR and
reorders the Arabic inside it. Anything but a pure Latin/numeric run stays
outside the isolate.

Tests enforce this: isolates are balanced on every screen, IDs and handles are
actually isolated, and no isolate contains Arabic.

Ruff's RUF001/2/3 (ambiguous unicode) are disabled project-wide -- they assume
an ASCII codebase and fire on correct Arabic.

**Rendered images are a separate problem.** Pillow does not shape Arabic;
letters come out disconnected and reversed. That needs `arabic-reshaper` +
`python-bidi` at the render layer, unrelated to message text.

### 8. Card rendering

The account card draws four values onto pre-designed artwork: real name,
Facebook name, bank number, username. The bank number is typed by the member,
validated for digits and uniqueness -- not auto-issued.

**Coordinates were measured, not eyeballed.** Diffing `example_empty.png`
against `example_filled.png` gives the exact centre of every value the designer
placed. They live in `assets/layouts/account_card.json` so nudging a label never
touches Python.

**Arabic shaping needs HarfBuzz, not presentation forms.** There are two ways to
render Arabic with Pillow:

- `arabic-reshaper` + `python-bidi` map text to Unicode Presentation Forms
  (U+FE70-FEFF). This only works with fonts that still carry those codepoints.
  Readex Pro carries **none** of them, so this path renders pure tofu. We tried
  it first and it silently produced broken cards.
- Pillow's RAQM layout engine drives the font's OpenType tables via HarfBuzz,
  and handles bidi for mixed Arabic/Latin values. This is what we use, with raw
  logical text.

**Raqm is NOT in Pillow's binary wheel.** `features.check("raqm")` is False on a
clean `pip install pillow`. Pillow loads the system library at runtime, so the
Dockerfile installs `libraqm0`. `require_shaping()` runs at startup and refuses
to boot without it -- rendering tofu is worse than failing.

**One font covers every script.** Values mix Arabic names, a Latin username and
digits. Readex Pro Bold (OFL, bundled in `assets/fonts/`) covers all three, so
there is no font-fallback machinery. Droid Arabic Kufi looks closer to the
artwork but has no Latin glyphs at all.

**Text never overflows.** `fit_text` shrinks toward `min_font_size`, then
truncates with an ellipsis. The renderer stays inside its box whatever it is
handed.

**Performance.** `optimize=True` cost 3.5s of CPU per render to save 1% of file
size -- removed. Text is drawn at full 3080px resolution and downscaled to
`output_width` afterwards, so glyph edges stay smooth. A card renders in ~0.4s,
off the event loop via `asyncio.to_thread`.

### 9. Telegram file_id reuse
Once an image is uploaded to Telegram, cache its `file_id`. Re-sending an
unchanged image (e.g. a static coin graphic) should never re-render or re-upload.

---

## Layout

Everything lives under one `powerbank/` package. Dependencies point one
direction only — an inner layer never imports an outer one:

```
core/      config, logging, exceptions     (depends on nothing)
db/        models, session                 (-> core)
services/  business logic, no aiogram      (-> db, core)
render/    Pillow image generation         (-> core)
bot/       telegram handlers, middlewares  (-> all of the above)
```

```
power-bank-bot/
├── powerbank/
│   ├── __main__.py           # entrypoint: python -m powerbank
│   ├── core/
│   │   ├── config.py         # pydantic-settings, cached get_settings()
│   │   ├── logging.py
│   │   ├── roles.py          # Role enum + permission predicates (no I/O)
│   │   ├── text.py           # bidi isolation helpers (ltr/code/cmd)
│   │   └── exceptions.py     # PowerBankError + user-safe messages
│   ├── db/
│   │   ├── base.py           # DeclarativeBase, naming convention, mixins
│   │   ├── session.py        # engine, sessionmaker, session_scope()
│   │   └── models/
│   │       └── user.py
│   ├── services/             # NO aiogram imports here
│   │   ├── users.py          # contact log, lookup by id/@username
│   │   └── access.py         # grant/revoke, super-admin seeding
│   ├── render/
│   │   ├── engine.py         # shaping, fitting, layout JSON
│   │   └── cards.py          # render_card, off-thread
│   └── bot/
│       ├── factory.py        # the single wiring point
│       ├── filters.py        # HasRole / IsStaff / IsSuperAdmin
│       ├── callbacks.py      # typed callback payloads
│       ├── views.py          # screen text, shared by buttons and commands
│       ├── screens.py        # send-vs-edit, so handlers need not care
│       ├── commands.py       # role-scoped native "/" menu
│       ├── handlers/         # one router per feature area
│       │   ├── __init__.py   # build_router(), registration order
│       │   ├── menu.py       # /start /help + navigation
│       │   ├── admin.py      # add/remove/members/who/attempts + FSM flows
│       │   └── errors.py
│       ├── middlewares/
│       │   ├── database.py   # session per update, commit/rollback
│       │   ├── user.py       # resolves + logs sender (grants nothing)
│       │   └── access.py     # the gate: non-members stop here
│       └── keyboards/
│           └── menu.py       # inline keyboards, role-aware
├── assets/{templates,layouts,fonts}/
├── migrations/               # alembic
├── tests/
├── docker-compose.yml        # postgres + bot
├── Makefile                  # install / run / lint / test / migrate
└── pyproject.toml            # uv
```

**Key boundary:** `services/` contains no aiogram imports. Handlers translate
Telegram updates into service calls, and services raise domain exceptions that
the error router turns into user-facing text. Game logic stays testable without
a bot running, and a web dashboard remains possible later.

**Middleware contract:** handlers receive `session` and `user` as kwargs and
never call `commit()` — `session_scope` commits on clean return, rolls back on
exception. Registration order is significant: user lookup needs the session.

---

## Phase plan

1. **Phase 1a (done)** — skeleton: config, logging, DB session, user model +
   service, middleware chain, `/start`, error handling, Alembic, Docker, tests.
2. **Phase 1b (done)** — roles and invite-only access: three ranks, env-seeded
   super admins, admin commands, access gate, attempt tracking.
3. **Phase 1c (done)** — interactive UI: inline-button menus, guided FSM flows,
   role-scoped native command menu, shared view layer.
4. **Phase 1d (done)** — Arabic UI throughout, with bidi isolation for Latin runs.
5. **Phase 1e (done)** — account cards: four typed values rendered onto the
   template, guided entry flow, unique bank numbers.
6. **Phase 2 (next)** — accounts, ledger, transfers, transaction history.
7. **Phase 3** — game mechanics (earning, shops, interest, whatever the design calls for).
8. **Phase 4** — Postgres, Redis, Docker deploy, admin tooling.
