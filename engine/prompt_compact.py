"""
prompt_compact.py — Slim WORLD / STATE / ENGINE payloads for turn prompts
========================================================================
Reduces prompt tokens by omitting duplicate bulk (full world JSON, etc.).
"""

from __future__ import annotations

import json
from typing import Any


def _clip(text: str, limit: int) -> str:
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def compact_world_for_prompt(world_pack: dict) -> str:
    """Text summary of world pack (characters live in CHARACTERS_CONTEXT)."""
    world = world_pack.get("world", {}) or {}
    lines: list[str] = []

    title = world.get("title") or world_pack.get("title")
    if title:
        lines.append(f"标题: {title}")

    for key, label in (
        ("setting", "背景设定"),
        ("genre", "类型"),
        ("tone", "基调"),
        ("era", "时代"),
    ):
        val = world.get(key)
        if val:
            lines.append(f"{label}: {_clip(val, 200)}")

    main_goal = world.get("main_goal")
    if main_goal:
        lines.append(f"主线目标: {_clip(main_goal, 300)}")

    factions = world.get("factions") or []
    if factions:
        lines.append("【势力概要】")
        for fac in factions[:10]:
            if not isinstance(fac, dict):
                continue
            name = fac.get("name", "?")
            desc = _clip(fac.get("description") or fac.get("goal") or "", 100)
            power = fac.get("power") or fac.get("strength")
            extra = f" 实力{power}" if power is not None else ""
            lines.append(f"  - {name}{extra}: {desc}")

    artifacts = world.get("artifacts") or world_pack.get("artifacts") or []
    if artifacts:
        names = [
            a.get("name", "?") if isinstance(a, dict) else str(a)
            for a in artifacts[:12]
        ]
        lines.append(f"关键物品: {', '.join(names)}")

    rules = world.get("rules") or world_pack.get("rules")
    if isinstance(rules, list) and rules:
        lines.append("世界规则: " + "；".join(_clip(str(r), 80) for r in rules[:6]))
    elif isinstance(rules, str) and rules.strip():
        lines.append(f"世界规则: {_clip(rules, 400)}")

    if not lines:
        return _clip(json.dumps(world_pack, ensure_ascii=False), 1500)
    return "\n".join(lines)


def slim_session_characters(characters: dict) -> dict[str, dict]:
    """Keep roster fields needed for continuity; drop long notes."""
    slim: dict[str, dict] = {}
    for key, ch in (characters or {}).items():
        if not isinstance(ch, dict):
            continue
        slim[key] = {
            k: ch[k]
            for k in ("name", "role", "level", "relation", "scene")
            if k in ch and ch[k]
        }
        if ch.get("note"):
            slim[key]["note"] = _clip(str(ch["note"]), 80)
    return slim


def compact_state_for_prompt(state: dict) -> dict[str, Any]:
    """Smaller STATE_JSON: slim characters, compact history entries."""
    out = dict(state)
    out["characters"] = slim_session_characters(state.get("characters", {}))

    history = state.get("history") or []
    compact_history: list[dict] = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        if entry.get("compressed") or not entry.get("story"):
            compact_history.append(entry)
            continue
        item = {
            "turn": entry.get("turn"),
            "scene": entry.get("scene"),
            "status": entry.get("status"),
            "choice": entry.get("choice"),
            "story": _clip(entry.get("story", ""), 800),
        }
        opts = entry.get("options")
        if opts:
            item["options"] = [_clip(str(o), 120) for o in opts[:6]]
        compact_history.append(item)
    out["history"] = compact_history
    return out


def compact_engine_rules(engine_config: dict) -> str:
    """One compact block instead of full engine.yaml JSON."""
    eng = engine_config.get("engine", engine_config) or {}
    sm = eng.get("state_machine", {})
    interaction = eng.get("interaction", {})
    force = eng.get("force_event", {})
    output = eng.get("output", {})

    states = sm.get("states") or ["SETUP", "BUILD", "TENSION", "CLIMAX", "COOLDOWN"]
    state_chain = sm.get("transition_rule") or "→".join(states)
    levels = interaction.get("levels") or {}
    level_str = ", ".join(f"{k}={v}" for k, v in list(levels.items())[:5])

    lines = [
        f"引擎: {eng.get('name', 'Prompt OS')} {eng.get('version', '')}".strip(),
        f"状态机: {state_chain}；同状态最多 {sm.get('max_turns_same_status', 2)} 轮需推进",
        f"互动等级: {level_str or 'L0-L4 每轮维持或提升'}",
        f"强制事件: {'；'.join(force.get('triggers', [])[:3]) or '场景/状态/互动停滞'}",
        f"输出: JSON — story + state + {output.get('fields', ['options'])[-1] if output.get('fields') else 'options'}",
    ]
    return "\n".join(lines)
