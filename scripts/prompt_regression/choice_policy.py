"""Deterministic option selection for regression runs."""
from __future__ import annotations

import random

from engine.memory import parse_option_metric_deltas

_REL_METRICS = frozenset({
    "trust", "affection", "respect", "dependence", "hostility", "attraction",
})


def pick_choice(seed: int, turn: int, options: list[str], *, prefer_relationship: bool = False) -> str:
    """
    Return choice letter A–Z for the given turn.

    Uses fixed RNG(seed + turn). When prefer_relationship is True (D/E categories),
    ranks options by parsed relationship delta magnitude before applying RNG tie-break.
    """
    if not options:
        return "A"

    rng = random.Random(seed + turn)

    if prefer_relationship:
        scored: list[tuple[int, int]] = []
        for idx, opt in enumerate(options):
            deltas = parse_option_metric_deltas([opt])
            magnitude = sum(abs(d) for _, m, d in deltas if m in _REL_METRICS)
            scored.append((magnitude, idx))
        max_mag = max(s[0] for s in scored)
        candidates = [idx for mag, idx in scored if mag == max_mag]
        idx = rng.choice(candidates)
    else:
        idx = rng.randint(0, len(options) - 1)

    return chr(ord("A") + idx)
