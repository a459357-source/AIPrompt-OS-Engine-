"""
prompt_canonical.py — V6 canonical prompt normalization for stable hashing
"""

from __future__ import annotations

import re

# Lightweight synonym unification (extend only via explicit ADR)
_SYNONYMS = {
    "beautiful": "beautiful",
    "pretty": "beautiful",
    "girl": "female",
    "woman": "female",
    "boy": "male",
    "man": "male",
    "anime": "anime",
    "manga": "anime",
}


def normalize_prompt(text: str) -> str:
    """
    Canonicalize prompt text so equivalent descriptions share one hash.

    - trim / lowercase
    - split comma-separated tokens
    - deduplicate
    - unify synonyms
    - sort tokens
    """
    raw = str(text or "").strip().lower()
    if not raw:
        return ""

    parts = re.split(r"[,;|]+", raw)
    tokens: list[str] = []
    seen: set[str] = set()

    for part in parts:
        token = re.sub(r"\s+", " ", part.strip())
        if not token:
            continue
        for word in token.split():
            w = _SYNONYMS.get(word, word)
            if w and w not in seen:
                seen.add(w)
                tokens.append(w)

    if not tokens:
        tokens = [raw]
    tokens.sort()
    return ", ".join(tokens)
