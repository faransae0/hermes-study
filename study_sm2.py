"""Pure SM-2 spaced-repetition scheduling algorithm.

No I/O, no database coupling — study_state.py's record_review() is the
only caller, and is where this algorithm's output gets persisted.
"""

from __future__ import annotations


def compute_sm2_update(
    ease_factor: float, interval_days: int, repetitions: int, quality: int
) -> tuple[float, int, int]:
    """Apply one SM-2 review update.

    ``quality`` is the standard SM-2 0-5 recall scale (0 = complete
    blackout, 5 = perfect recall). Returns
    ``(new_ease_factor, new_interval_days, new_repetitions)``.
    """
    if quality < 3:
        repetitions = 0
        interval_days = 1
    else:
        if repetitions == 0:
            interval_days = 1
        elif repetitions == 1:
            interval_days = 6
        else:
            interval_days = round(interval_days * ease_factor)
        repetitions += 1

    ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if ease_factor < 1.3:
        ease_factor = 1.3

    return ease_factor, interval_days, repetitions
