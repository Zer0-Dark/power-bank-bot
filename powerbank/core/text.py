"""Bidirectional text helpers.

Our UI is Arabic (RTL) but is full of Latin runs: @usernames, numeric IDs,
command names, the brand. Left bare, the Unicode bidi algorithm reorders the
punctuation and digits around them -- so `(436677576)` renders with the
parenthesis on the wrong side and `@user — 123` visually scrambles.

The fix is to isolate every Latin run. FSI/PDI wrap a span so its direction is
resolved independently of the surrounding paragraph. This is cheap to apply
consistently and miserable to retrofit, so every Latin fragment goes through
`ltr()` or `code()`.
"""

FSI = "⁨"  # FIRST STRONG ISOLATE -- direction inferred from content
PDI = "⁩"  # POP DIRECTIONAL ISOLATE


def ltr(value: object) -> str:
    """Isolate a Latin/numeric run so it cannot reorder inside Arabic text."""
    return f"{FSI}{value}{PDI}"


def code(value: object) -> str:
    """A monospace span, isolated.

    The isolate marks sit outside the tag: Telegram parses the HTML first, so
    they must not land inside the code span's rendered content.
    """
    return f"{FSI}<code>{value}</code>{PDI}"


def cmd(name: str) -> str:
    """A command token like /add.

    Only the command itself is isolated. Wrapping a mixed Arabic+Latin span
    would force the whole thing LTR and reorder the Arabic inside it, so
    anything else on the line stays outside the isolate.
    """
    return ltr(f"/{name}")
