"""
style_bible.py — Style Bible v1 deterministic prompt constraint layer
"""

from __future__ import annotations

STYLE_BIBLE_V1: dict[str, list[str]] = {
    "global": [
        "cinematic lighting",
        "high consistency world design",
        "coherent visual identity",
        "illustration-grade detail",
    ],
    "composition": [
        "rule of thirds",
        "strong focal subject",
        "controlled depth of field",
    ],
    "material": [
        "natural material consistency",
        "steel, stone, cloth realism balance",
    ],
    "tone": [
        "subtle dramatic tone",
        "controlled color palette",
    ],
}

ENTITY_STYLE_MAP: dict[str, list[str]] = {
    "character": [
        "clear silhouette design",
        "recognizable outfit structure",
    ],
    "location": [
        "architectural coherence",
        "environmental storytelling",
    ],
    "faction": [
        "symbolic visual identity",
        "banner/emblem consistency",
    ],
    "event": [
        "dynamic composition",
        "emotional lighting alignment",
    ],
}


def _dedupe_preserve_order(tokens: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for token in tokens:
        t = str(token or "").strip()
        if not t:
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def style_tokens_for_entity(entity_type: str) -> list[str]:
    """Collect global + entity-bound style tokens (deterministic)."""
    et = str(entity_type or "").strip().lower()
    tokens: list[str] = []
    for bucket in ("global", "composition", "tone"):
        tokens.extend(STYLE_BIBLE_V1.get(bucket) or [])
    tokens.extend(ENTITY_STYLE_MAP.get(et) or [])
    return _dedupe_preserve_order(tokens)


def apply_style_bible(prompt: str, entity_type: str) -> str:
    """
    Inject world-wide visual constraints before provider call.

    - Does not override identity semantics (tokens prepended only)
    - Does not remove existing prompt content
    """
    base = str(prompt or "").strip()
    style_parts = style_tokens_for_entity(entity_type)
    if not style_parts:
        return base
    if not base:
        return ", ".join(style_parts)
    return ", ".join([*style_parts, base])
