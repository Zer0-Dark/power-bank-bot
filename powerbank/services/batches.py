"""Batch-size validation shared by every mint-N-at-once flow (power-pass, coins, store cards)."""

from powerbank.core.exceptions import UserFacingError

MIN_BATCH = 1
MAX_BATCH = 100


def clean_batch_count(raw: str) -> int:
    """Validate a typed batch size. Raises on anything outside [1, 100]."""
    text = " ".join((raw or "").split())
    if not text.isdigit():
        raise UserFacingError("العدد يجب أن يكون رقماً صحيحاً.")
    count = int(text)
    if not (MIN_BATCH <= count <= MAX_BATCH):
        raise UserFacingError(f"العدد يجب أن يكون بين {MIN_BATCH} و {MAX_BATCH}.")
    return count
