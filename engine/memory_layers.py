"""
memory_layers.py — Hot context, chapter summaries, long-term memory (V2)
=========================================================================
Three-layer memory for prompt injection without full history bloat.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import config
from engine import io_utils
from engine.context_compress import estimate_text_tokens, summarize_turn_line
from engine.memory import (
    get_artifact_context_for_prompt,
    get_context_for_prompt,
    get_faction_attitude_context,
    get_faction_context_for_prompt,
    build_character_tier_context,
)
from engine.events import get_event_context
from engine.world_driver import get_world_state_context

logger = logging.getLogger(__name__)

CHARS_TO_TOKENS = 0.6


def _clip(text: str, limit: int) -> str:
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def load_chapter_summaries() -> list[dict]:
    path = config.CHAPTER_SUMMARIES_PATH
    if not path.exists():
        return []
    try:
        data = io_utils.read_json(path, use_cache=True)
        items = data.get("summaries", data if isinstance(data, list) else [])
        return items if isinstance(items, list) else []
    except Exception:
        return []


def save_chapter_summaries(summaries: list[dict]) -> None:
    io_utils.write_json(
        config.CHAPTER_SUMMARIES_PATH,
        {"summaries": summaries[-50:]},
    )


def build_hot_context(session_state: dict, memory: dict | None = None) -> str:
    """
    Last N turns full story + current scene/task/active characters.
    Max HOT_CONTEXT_MAX_TOKENS; overflow compresses oldest hot turn to summary line.
    """
    history: list = session_state.get("history", [])
    max_turns = config.HOT_CONTEXT_TURNS
    hot = history[-max_turns:] if history else []

    lines: list[str] = []
    scene = session_state.get("scene", "")
    status = session_state.get("status", "SETUP")
    chapter = session_state.get("chapter", 1)
    turn = session_state.get("turn", 0)

    lines.append(f"【当前状态】第{chapter}章 T{turn} | 场景:{scene} | 状态:{status}")

    if session_state.get("force_event_pending"):
        lines.append("⚠️ 强制事件待触发")

    chars = session_state.get("characters", {})
    if chars:
        active = [
            f"{k}({v.get('level', 'L0')})"
            for k, v in chars.items()
            if isinstance(v, dict)
        ]
        lines.append(f"【出场角色】{', '.join(active[:12])}")

    goal = ""
    try:
        wp = io_utils.read_yaml(config.WORLD_PACK_PATH)
        goal = (wp.get("world", {}) or {}).get("main_goal", "")
    except Exception:
        pass
    if goal:
        lines.append(f"【当前任务/主线】{_clip(goal, 200)}")

    lines.append("【最近回合正文】")
    entries: list[dict] = []
    for entry in hot:
        if not isinstance(entry, dict):
            continue
        entries.append({
            "turn": entry.get("turn"),
            "scene": entry.get("scene"),
            "status": entry.get("status"),
            "choice": entry.get("choice"),
            "story": entry.get("story") or entry.get("summary", ""),
        })

    text = json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
    budget = config.HOT_CONTEXT_MAX_TOKENS
    tokens = estimate_text_tokens(text)

    while tokens > budget and len(entries) > 1:
        oldest = entries.pop(0)
        summary_line = summarize_turn_line(oldest, max_chars=120)
        lines.append(f"  (压缩) {summary_line}")
        payload = json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
        tokens = estimate_text_tokens(payload) + estimate_text_tokens("\n".join(lines))

    for entry in entries:
        t = entry.get("turn", "?")
        sc = entry.get("scene", "?")
        ch = entry.get("choice", "-")
        story = str(entry.get("story", ""))
        lines.append(f"--- T{t} [{sc}] 选:{ch} ---")
        lines.append(story)

    return "\n".join(lines)


def _legacy_context_block(memory: dict, session_state: dict) -> str:
    """Pre-router memory sections (used for token baseline comparison)."""
    parts: list[str] = []
    mem_ctx = get_context_for_prompt(memory)
    if mem_ctx:
        parts.append(mem_ctx)

    faction = get_faction_attitude_context(memory)
    if faction:
        parts.append(faction)

    turn = session_state.get("turn", 0)
    artifact = get_artifact_context_for_prompt(memory)
    if artifact:
        parts.append(artifact)

    event = get_event_context(memory)
    if event:
        parts.append(event)

    world_state = get_world_state_context(memory, turn)
    if world_state:
        parts.append(world_state)

    faction_scope = get_faction_context_for_prompt(memory)
    if faction_scope:
        parts.append(faction_scope)

    return "\n".join(p for p in parts if p.strip())


def build_long_term_memory(
    memory: dict,
    session_state: dict,
    *,
    max_chars: int | None = None,
    world_pack: dict | None = None,
) -> str:
    """Structured world/character state — no story bodies or full history."""
    limit = max_chars or config.LONG_TERM_MEMORY_MAX_CHARS
    parts: list[str] = []

    tier = build_character_tier_context(memory)
    if tier:
        parts.append(tier)

    if config.CONTEXT_ROUTER_ENABLED:
        rel_system = memory.get("relationship_system", {})
        if rel_system:
            stages = rel_system.get("stages", [])
            if stages:
                parts.append(f"【关系阶段系统】{' → '.join(stages)}")

        if world_pack is None:
            try:
                world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
            except Exception:
                world_pack = {}
        from engine.context_router import route_context_for_prompt

        baseline_chars = len(_legacy_context_block(memory, session_state))
        routed = route_context_for_prompt(
            memory,
            session_state,
            world_pack,
            baseline_chars=baseline_chars,
        )
        if routed:
            parts.append(routed)
    else:
        mem_ctx = get_context_for_prompt(memory)
        if mem_ctx:
            parts.append(mem_ctx)

        faction = get_faction_attitude_context(memory)
        if faction:
            parts.append(faction)

        turn = session_state.get("turn", 0)
        artifact = get_artifact_context_for_prompt(memory)
        if artifact:
            parts.append(artifact)

        event = get_event_context(memory)
        if event:
            parts.append(event)

        world_state = get_world_state_context(memory, turn)
        if world_state:
            parts.append(world_state)

        faction_scope = get_faction_context_for_prompt(memory)
        if faction_scope:
            parts.append(faction_scope)

    block = "\n".join(p for p in parts if p.strip())
    return _clip(block, limit)


def build_recent_summaries(count: int = 2) -> str:
    summaries = load_chapter_summaries()
    if not summaries:
        return "（暂无章节摘要）"

    recent = summaries[-count:]
    lines = ["【章节摘要 — 最近 {} 章】".format(len(recent))]
    for item in recent:
        cid = item.get("chapter_id", "?")
        summary = item.get("summary", "")
        lines.append(f"第{cid}章: {_clip(summary, 400)}")
        events = item.get("important_events") or []
        if events:
            lines.append("  关键事件: " + "；".join(_clip(str(e), 80) for e in events[:5]))
        rel = item.get("relationship_changes") or []
        if rel:
            lines.append("  关系变化: " + "；".join(_clip(str(r), 60) for r in rel[:4]))
    return "\n".join(lines)


def maybe_update_chapter_summary(
    session_state: dict,
    memory: dict,
) -> dict | None:
    """Rule-based chapter summary every CHAPTER_SUMMARY_INTERVAL turns."""
    turn = int(session_state.get("turn", 0))
    if turn <= 0 or turn % config.CHAPTER_SUMMARY_INTERVAL != 0:
        return None

    history: list = session_state.get("history", [])
    chunk = history[-config.CHAPTER_SUMMARY_INTERVAL :]
    if not chunk:
        return None

    chapter_id = session_state.get("chapter", 1)
    scenes = [e.get("scene", "") for e in chunk if isinstance(e, dict)]
    choices = [e.get("choice", "") for e in chunk if isinstance(e, dict)]
    summaries = [str(e.get("summary") or e.get("story", ""))[:120] for e in chunk if isinstance(e, dict)]

    entry = {
        "chapter_id": chapter_id,
        "turn_end": turn,
        "summary": " → ".join(
            f"T{e.get('turn', '?')}:{_clip(str(e.get('summary') or e.get('story', '')), 80)}"
            for e in chunk
            if isinstance(e, dict)
        )[:600],
        "important_events": [
            f"场景 {s}" for s in dict.fromkeys(scenes) if s
        ][:5],
        "relationship_changes": _relationship_deltas(memory, chunk),
        "faction_changes": _faction_deltas(memory),
        "world_changes": [f"玩家选择: {c}" for c in choices if c][:5],
    }

    all_summaries = load_chapter_summaries()
    all_summaries.append(entry)
    save_chapter_summaries(all_summaries)
    logger.info("📚 章节摘要已写入 turn=%d chapter=%d", turn, chapter_id)
    return entry


def _relationship_deltas(memory: dict, chunk: list) -> list[str]:
    out: list[str] = []
    chars = memory.get("characters", {})
    for name, data in list(chars.items())[:8]:
        if not isinstance(data, dict):
            continue
        trust = data.get("trust")
        rel = data.get("relationship")
        if trust is not None or rel:
            out.append(f"{name}: trust={trust} rel={rel}")
    if not out and chunk:
        out.append(f"本段共 {len(chunk)} 轮互动")
    return out[:6]


def _faction_deltas(memory: dict) -> list[str]:
    factions = memory.get("factions", {})
    out: list[str] = []
    for name, data in list(factions.items())[:6]:
        if isinstance(data, dict):
            rep = data.get("reputation")
            if rep is not None:
                out.append(f"{name} 声望={rep}")
    return out


def build_world_summary_from_pack(world_pack: dict) -> dict:
    """Persist compact world metadata at story creation."""
    world = world_pack.get("world", {}) or {}
    factions = world.get("factions") or []
    regions: list[str] = []
    for fac in factions[:10]:
        if isinstance(fac, dict):
            for t in fac.get("controlledTerritories") or fac.get("territories") or []:
                if t and str(t) not in regions:
                    regions.append(str(t))

    return {
        "title": world.get("title") or world_pack.get("title", ""),
        "era": world.get("era", ""),
        "setting": _clip(world.get("setting", ""), 300),
        "main_goal": _clip(world.get("main_goal", ""), 200),
        "factions": [
            {
                "name": f.get("name", "?"),
                "power": f.get("power") or f.get("strength"),
                "description": _clip(f.get("description") or f.get("goal") or "", 100),
            }
            for f in factions[:10]
            if isinstance(f, dict)
        ],
        "regions": regions[:12],
    }


def load_world_summary_text(
    session_state: dict | None = None,
    memory: dict | None = None,
    world_pack: dict | None = None,
) -> str:
    path = config.WORLD_SUMMARY_PATH
    if path.exists():
        try:
            data = io_utils.read_json(path, use_cache=True)
            lines = [f"世界: {data.get('title', '?')}"]
            if data.get("era"):
                lines.append(f"时代: {data['era']}")
            if data.get("setting"):
                lines.append(f"背景: {_clip(data['setting'], 200)}")
            if data.get("main_goal"):
                lines.append(f"主线: {_clip(data['main_goal'], 150)}")
            factions = data.get("factions") or []
            if factions:
                if config.CONTEXT_ROUTER_ENABLED:
                    if session_state is None:
                        try:
                            session_state = io_utils.read_yaml(config.SESSION_STATE_PATH)
                        except Exception:
                            session_state = {}
                    if memory is None:
                        try:
                            from engine.memory import load_memory

                            memory = load_memory()
                        except Exception:
                            memory = {}
                    if world_pack is None:
                        try:
                            world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
                        except Exception:
                            world_pack = {}
                    from engine.context_router import route_world_summary_factions

                    regions = list(data.get("regions") or [])[:12]
                    routed = route_world_summary_factions(
                        factions[:8],
                        session_state,
                        memory,
                        world_pack,
                        regions=regions,
                    )
                    factions = routed if routed else factions[: config.MAX_WORLD_FACTION_ITEMS]
                lines.append("【主要势力】")
                for f in factions:
                    lines.append(
                        f"  - {f.get('name', '?')}: {_clip(f.get('description', ''), 80)}"
                    )
            regions = data.get("regions") or []
            if regions:
                lines.append(f"重要地区: {', '.join(regions[:8])}")
            return "\n".join(lines)
        except Exception:
            pass
    return ""
