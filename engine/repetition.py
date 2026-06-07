"""Detect overly similar story text compared to recent turns."""

from __future__ import annotations


def _char_bigrams(text: str) -> set[str]:
    compact = "".join(text.split())
    if len(compact) < 2:
        return set()
    return {compact[i : i + 2] for i in range(len(compact) - 1)}


def similarity_ratio(a: str, b: str) -> float:
    """Jaccard similarity on character bigrams (ignores whitespace)."""
    sa, sb = _char_bigrams(a), _char_bigrams(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def check_story_repetition(story: str, history: list, level: str) -> tuple[bool, str]:
    """
    Compare *story* with recent history entries.

    Returns (is_repetitive, reason).
    """
    if not history or not story.strip():
        return False, ""

    thresholds = {"strict": 0.35, "standard": 0.55, "loose": 0.75}
    threshold = thresholds.get(level, thresholds["standard"])
    lookback = {"strict": 3, "standard": 2, "loose": 1}.get(level, 2)

    for entry in history[-lookback:]:
        prev = entry.get("story") or entry.get("summary") or ""
        if not prev:
            continue
        ratio = similarity_ratio(story, prev)
        if ratio >= threshold:
            turn = entry.get("turn", "?")
            return True, f"与第 {turn} 轮正文相似度过高 ({ratio:.0%})"
    return False, ""
