"""Character key/name registry — init labels, dedupe, merge by name."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

RELATIONSHIP_TYPE_LABELS: dict[str, str] = {
    "lover": "恋人",
    "enemy": "敌人",
    "friend": "朋友",
    "family": "家人",
    "teacher": "师徒",
    "rival": "对手",
    "ally": "盟友",
}


def character_display_name(char: dict | None, key: str = "") -> str:
    if not isinstance(char, dict):
        return str(key or "").strip()
    return str(char.get("name") or key or "").strip()


def preferred_character_key(keys: list[str]) -> str:
    """Prefer stable letter keys (A/B/C) over AI-added name keys."""
    letter_keys = sorted(k for k in keys if len(k) == 1 and k.isalpha())
    if letter_keys:
        return letter_keys[0]
    return keys[-1]


def initial_relation_label(
    name: str,
    *,
    is_main: bool,
    relationship: list | None = None,
    char_relations: dict | None = None,
    fallback: str = "陌生",
) -> str:
    """Build session relation label from NewStory matrix / world relationship."""
    if is_main:
        return "主角"

    rel_entry = {}
    if isinstance(char_relations, dict):
        rel_entry = char_relations.get(name) or {}
    if isinstance(rel_entry, dict):
        tags = [str(t).strip() for t in (rel_entry.get("tags") or []) if str(t).strip()]
        if tags:
            return "、".join(tags)
        rtype = str(rel_entry.get("relationshipType") or "").strip()
        if rtype in RELATIONSHIP_TYPE_LABELS:
            return RELATIONSHIP_TYPE_LABELS[rtype]

    parts: list[str] = []
    for item in relationship or []:
        text = str(item).strip()
        if text:
            parts.append(text)
    if parts:
        return "、".join(parts)

    return fallback


def merge_character_fields(existing: dict, incoming: dict, *, level_idx_fn) -> dict:
    """Merge two character dicts; interaction level never decreases."""
    old_level = existing.get("level", "L0")
    new_level = incoming.get("level", old_level)
    old_idx = level_idx_fn(old_level)
    new_idx = level_idx_fn(new_level)
    if new_idx < old_idx:
        new_level = old_level
    return {**existing, **incoming, "level": new_level}


def dedupe_characters_by_name(chars: dict) -> dict[str, dict]:
    """Keep one entry per display name; later keys win (most recent update)."""
    if not isinstance(chars, dict):
        return {}
    latest: dict[str, tuple[str, dict]] = {}
    for key, sc in chars.items():
        if not isinstance(sc, dict):
            continue
        name = character_display_name(sc, key)
        if not name:
            continue
        latest[name] = (str(key), sc)
    return {key: char for key, char in latest.values()}


def canonicalize_characters_by_name(chars: dict, *, level_idx_fn) -> dict[str, dict]:
    """Merge duplicate names into one key; remove redundant entries."""
    if not isinstance(chars, dict) or not chars:
        return {}

    buckets: dict[str, list[str]] = {}
    for key, sc in chars.items():
        if not isinstance(sc, dict):
            continue
        name = character_display_name(sc, key)
        if not name:
            continue
        buckets.setdefault(name, []).append(str(key))

    out = dict(chars)
    for name, keys in buckets.items():
        if len(keys) <= 1:
            continue
        keeper = preferred_character_key(keys)
        merged: dict = {}
        for k in keys:
            if k not in out or not isinstance(out.get(k), dict):
                continue
            merged = merge_character_fields(merged, out[k], level_idx_fn=level_idx_fn) if merged else dict(out[k])
        for k in keys:
            if k != keeper and k in out:
                del out[k]
        out[keeper] = merged
        logger.info("合并同名角色 %s：保留 key=%s，移除 %s", name, keeper, [k for k in keys if k != keeper])

    return out


def merge_proposed_characters(
    old_chars: dict,
    new_chars: dict,
    *,
    level_idx_fn,
) -> dict[str, dict]:
    """Apply AI character updates; merge by key then by display name."""
    merged: dict[str, dict] = {}

    for key, old_char in (old_chars or {}).items():
        if not isinstance(old_char, dict):
            continue
        new_char = (new_chars or {}).get(key, old_char)
        if not isinstance(new_char, dict):
            new_char = old_char
        merged[key] = merge_character_fields(old_char, new_char, level_idx_fn=level_idx_fn)

    name_index: dict[str, str] = {}
    for key, ch in merged.items():
        name = character_display_name(ch, key)
        if name:
            name_index[name] = key

    for key, new_char in (new_chars or {}).items():
        if key in merged or not isinstance(new_char, dict):
            continue
        name = character_display_name(new_char, key)
        if name and name in name_index:
            existing_key = name_index[name]
            merged[existing_key] = merge_character_fields(
                merged[existing_key], new_char, level_idx_fn=level_idx_fn,
            )
            logger.info("AI 以 key=%s 重复注册已有角色 %s，已合并至 key=%s", key, name, existing_key)
            continue
        merged[key] = dict(new_char)
        if name:
            name_index[name] = key

    return canonicalize_characters_by_name(merged, level_idx_fn=level_idx_fn)
