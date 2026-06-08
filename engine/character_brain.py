"""
character_brain.py — V3.3 Character Brain
==========================================
Personality core (desire/fear/taboo/secret/values) for on-scene characters.
Injected into prompt as {{CHARACTER_BRAIN}}; filtered by hybrid roster rules.
"""

from __future__ import annotations

import config
from engine.context_router import RouterInputs, build_router_inputs, is_recent_character

_FIELD_CLIP = 80
_ALWAYS_TIERS = frozenset({"主角", "核心"})


def normalize_personality(raw: dict | None) -> dict:
    """Return a normalized personality dict with stable keys."""
    raw = raw if isinstance(raw, dict) else {}
    values = raw.get("values", [])
    if isinstance(values, str):
        values = [v.strip() for v in values.split("/") if v.strip()]
    elif not isinstance(values, list):
        values = []
    else:
        values = [str(v).strip() for v in values if str(v).strip()]
    return {
        "desire": str(raw.get("desire", "") or "").strip(),
        "fear": str(raw.get("fear", "") or "").strip(),
        "taboo": str(raw.get("taboo", "") or "").strip(),
        "secret": str(raw.get("secret", "") or "").strip(),
        "values": values,
    }


def _clip(text: str, limit: int = _FIELD_CLIP) -> str:
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def personality_has_content(personality: dict) -> bool:
    p = normalize_personality(personality)
    return bool(p["desire"] or p["fear"] or p["taboo"] or p["secret"] or p["values"])


def seed_personality_from_world(ch: dict) -> dict:
    """Map world_pack character fields to personality core."""
    ch = ch if isinstance(ch, dict) else {}
    tags = ch.get("personality_tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split("/") if t.strip()]
    elif not isinstance(tags, list):
        tags = []
    existing = normalize_personality(ch.get("personality"))
    return normalize_personality({
        "desire": existing["desire"] or str(ch.get("goal", "") or "").strip(),
        "fear": existing["fear"],
        "taboo": existing["taboo"],
        "secret": existing["secret"] or str(ch.get("secret", "") or "").strip(),
        "values": existing["values"] or [str(t).strip() for t in tags if str(t).strip()],
    })


def _world_char_by_name(world_pack: dict) -> dict[str, dict]:
    world = world_pack.get("world", world_pack) if world_pack else {}
    out: dict[str, dict] = {}
    for ch in world.get("characters", []) or []:
        if isinstance(ch, dict):
            name = str(ch.get("name", "")).strip()
            if name:
                out[name] = ch
    return out


def ensure_personalities(memory: dict, world_pack: dict) -> None:
    """Backfill missing personality blocks from world_pack (in-place)."""
    mem_chars = memory.setdefault("characters", {})
    world_chars = _world_char_by_name(world_pack)
    for name, entry in mem_chars.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("personality") and personality_has_content(entry["personality"]):
            continue
        world_ch = world_chars.get(name, {})
        entry["personality"] = seed_personality_from_world(world_ch)


def _is_main_character(name: str, world_pack: dict) -> bool:
    ch = _world_char_by_name(world_pack).get(name, {})
    return bool(ch.get("is_main"))


def _session_roster_names(session_state: dict) -> set[str]:
    names: set[str] = set()
    for ch in (session_state.get("characters") or {}).values():
        if isinstance(ch, dict):
            n = str(ch.get("name", "")).strip()
            if n:
                names.add(n)
    return names


def resolve_brain_character_names(
    session_state: dict,
    memory: dict,
    world_pack: dict,
    *,
    router_inputs: RouterInputs | None = None,
) -> set[str]:
    """
    Hybrid filter: main + 核心 tier always; others only if recently on-scene.
    Early game (turn <= 1): all roster names with non-empty personality.
    """
    inputs = router_inputs or build_router_inputs(session_state, memory, world_pack)
    mem_chars = memory.get("characters", {}) or {}
    roster = _session_roster_names(session_state)
    selected: set[str] = set()

    if inputs.current_turn <= 1:
        for name in roster:
            entry = mem_chars.get(name, {})
            if isinstance(entry, dict) and personality_has_content(entry.get("personality")):
                selected.add(name)
        if selected:
            return selected

    for name in roster:
        entry = mem_chars.get(name, {})
        if not isinstance(entry, dict):
            continue
        tier = str(entry.get("tier", "") or "").strip()
        if _is_main_character(name, world_pack) or tier in _ALWAYS_TIERS:
            selected.add(name)
            continue
        last_turn = int(entry.get("last_appearance_turn", 0) or 0)
        if is_recent_character(name, last_turn, inputs):
            selected.add(name)

    return selected


def build_character_brain_context(
    names: set[str],
    memory: dict,
    world_pack: dict,
    session_state: dict | None = None,
) -> str:
    """Format personality blocks for prompt injection."""
    if not names:
        return ""

    mem_chars = memory.get("characters", {}) or {}
    world_chars = _world_char_by_name(world_pack)
    lines = [
        "【角色人格核心 — 行为决策参考】",
        "参考规则：关系数值与人格核心共同决定行为；高好感不等于无条件顺从；触犯 taboo 时角色应拒绝或强烈反弹。",
    ]
    rendered = 0

    for name in sorted(names):
        entry = mem_chars.get(name, {})
        if not isinstance(entry, dict):
            continue
        personality = normalize_personality(entry.get("personality"))
        if not personality_has_content(personality):
            personality = seed_personality_from_world(world_chars.get(name, {}))
        if not personality_has_content(personality):
            continue

        block = [f"  {name}:"]
        if personality["desire"]:
            block.append(f"    欲望: {_clip(personality['desire'])}")
        if personality["fear"]:
            block.append(f"    恐惧: {_clip(personality['fear'])}")
        if personality["taboo"]:
            block.append(f"    禁忌: {_clip(personality['taboo'])}")
        if personality["secret"]:
            block.append(f"    秘密: {_clip(personality['secret'])}")
        if personality["values"]:
            block.append(f"    价值观: {' / '.join(_clip(v, 40) for v in personality['values'][:8])}")
        if len(block) > 1:
            lines.extend(block)
            rendered += 1

    if rendered == 0:
        brain_text = ""
    else:
        brain_text = "\n".join(lines)

    if config.CHARACTER_BRAIN_ENABLED and config.RELATIONSHIP_ENGINE_ENABLED:
        from engine.relationship_core import read_api_for_brain

        from engine.relationship_recall import ensure_memory_store
        mem_store = ensure_memory_store(None)
        rel_block = read_api_for_brain(
            names, world_pack, session_state, memory_store=mem_store,
        )
        if rel_block:
            if brain_text:
                return brain_text + "\n" + rel_block
            return rel_block

    return brain_text


def sync_personality_to_world_pack(world_pack: dict, name: str, personality: dict) -> None:
    """Write personality back to world_pack character entry (in-place)."""
    world = world_pack.setdefault("world", {})
    chars = world.setdefault("characters", [])
    norm = normalize_personality(personality)
    for ch in chars:
        if isinstance(ch, dict) and str(ch.get("name", "")).strip() == name:
            ch["personality"] = norm
            return
