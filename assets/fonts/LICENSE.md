# Bundled fonts

**Readex Pro** — Copyright The Readex Pro Project Authors.
Licensed under the SIL Open Font License 1.1 (OFL-1.1), which permits
redistribution and embedding. No longer drawn on the card, kept as the
fallback face for a field that names no font of its own.

Full text: https://openfontlicense.org

## Card faces

Each account-card field names its own file in
`assets/layouts/account_card.json`:

| File | Used for | Notes |
|---|---|---|
| `YaModernPro.ttf` | real name, Facebook name (Arabic) | must shape via Raqm |
| `GodofThunder.ttf` | username (Latin) | display face |
| `Munro.ttf` | account number (digits) | numeric face |

Confirm each file's license permits embedding and redistribution before
shipping it in the image. Drop the files in this directory under exactly the
names above.

## Power-pass faces

Each power-pass layout in `assets/layouts/power-pass/` draws its one field
(the code) with `Munro-2LYe.ttf`, supplied by the design team alongside the
templates themselves.

## Coin faces

Coin notes have no supplied font, so each layout in `assets/layouts/coins/`
draws its code with a close free equivalent to the original design, pending
the real files:

| File | Used for | Source |
|---|---|---|
| `DSEG7Classic-Bold.ttf` | 500 and 10000 notes (digital/7-segment look) | [DSEG](https://github.com/keshikan/DSEG) by Keshikan, SIL OFL-1.1 |
| `PlayfairDisplay-Bold.ttf` | 1000, 2000, and 5000 notes (serif look) | [Playfair Display](https://github.com/google/fonts/tree/main/ofl/playfairdisplay), SIL OFL-1.1 -- Bold weight instanced from the variable font with `fonttools varLib.instancer` |

Both are OFL-1.1, same as every other bundled face.
