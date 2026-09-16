# Agent notes

## StatesGroup names must be unique across the whole bot, not just per file

aiogram derives an FSM state's identity string from the `StatesGroup` class
name alone (e.g. `NewCoinBatch.count` -> `"NewCoinBatch:count"`) — it does
NOT include the module path. Two different handler files that each declare
their own `class NewBatch(StatesGroup): ...` produce the *same* state string,
so a message typed while a user is in one flow can get routed into a
same-named state handler in a completely different file, reading FSM data
keys that were never set there.

This actually happened: `handlers/coins.py` and `handlers/power_pass.py` both
had `class NewBatch(StatesGroup)`. An admin issuing a coin would hit
`power_pass.got_count`, which read `data["card_type"]` (a key only the
power-pass flow sets) and crashed with `KeyError: 'card_type'`, because
`power_pass.router` is registered before `coins.router` in
`handlers/__init__.py`.

When adding a new card/coin/pass type or a new issuing flow with its own
`StatesGroup`:

- Give the `StatesGroup` class a name that's unique across the whole
  `handlers/` package, prefixed with the domain, e.g. `NewCoinBatch`,
  `NewPowerPassBatch`, `NewCard` — never a generic name like `NewBatch` or
  `Flow` that another handler file might reuse.
- If you're not sure, grep for the class name first:
  `grep -rn "class .*StatesGroup" powerbank/bot/handlers/`
