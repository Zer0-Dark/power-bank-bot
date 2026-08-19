# Tech Stack — Virtual Bank Bot

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

### 5. Telegram file_id reuse
Once an image is uploaded to Telegram, cache its `file_id`. Re-sending an
unchanged image (e.g. a static coin graphic) should never re-render or re-upload.

---

## Planned layout

```
virtual-bank-bot/
├── bot/
│   ├── __init__.py
│   ├── main.py              # entrypoint, dispatcher setup
│   ├── config.py            # pydantic-settings
│   ├── handlers/            # one router per feature area
│   │   ├── start.py
│   │   ├── balance.py
│   │   └── transfer.py
│   ├── keyboards/
│   ├── middlewares/         # throttling, db session injection, user loading
│   ├── services/            # business logic — no aiogram imports in here
│   │   ├── accounts.py
│   │   └── ledger.py
│   └── render/
│       ├── engine.py        # Pillow helpers: text fitting, layer paste
│       └── cards.py         # render_balance_card, render_receipt, ...
├── assets/
│   ├── templates/           # pre-designed PNGs
│   │   └── balance_card.png
│   ├── layouts/             # JSON coordinate configs
│   │   └── balance_card.json
│   └── fonts/
├── db/
│   ├── models.py
│   └── migrations/          # alembic
├── tests/
├── docs/
│   └── TECH_STACK.md
├── .env.example
├── pyproject.toml
└── Dockerfile
```

**Key boundary:** `services/` contains no aiogram imports. Handlers translate
Telegram updates into service calls. This keeps game logic testable without a bot
running, and leaves the door open for a web dashboard later.

---

## Phase plan

1. **Phase 1 (now)** — skeleton + render pipeline. `/card` command replies with a
   pre-designed image with data drawn onto it. SQLite, minimal user table.
2. **Phase 2** — accounts, ledger, transfers, transaction history.
3. **Phase 3** — game mechanics (earning, shops, interest, whatever the design calls for).
4. **Phase 4** — Postgres, Redis, Docker deploy, admin tooling.
