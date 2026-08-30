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
