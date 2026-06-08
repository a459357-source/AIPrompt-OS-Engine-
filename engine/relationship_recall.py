"""
relationship_recall.py — V5.1 Relationship Memory recall APIs
===============================================================
Read-only surfaces for Brain, Objective, Plot Director, and Prompt injection.
"""

from __future__ import annotations

import config
from engine.relationship_core import (
    ensure_graph,
    get_edge,
    relationship_progress_for_objective,
    resolve_player_name,
)
from engine.relationship_memory import (
    get_edge_events,
    load_relationship_memory_store,
    memory_edge_key,
)


def _recent_for_edge(
    store: dict,
    actor: str,
    target: str,
    limit: int | None = None,
) -> list[dict]:
    limit = limit or config.RELATIONSHIP_MEMORY_MAX_EVENTS_PER_EDGE
    events = get_edge_events(store, actor, target)
    return events[-limit:] if events else []


def format_brain_memory(
    names: set[str],
    store: dict,
    player: str,
) -> str:
    """Recent relationship events for Character Brain."""
    if not names or not store.get("edges"):
        return ""

    lines = ["【关系记忆 — 最近事件】"]
    count = 0
    for name in sorted(names):
        if name == player:
            continue
        events = _recent_for_edge(store, player, name)
        if not events:
            continue
        lines.append(f"  {name}:")
        for e in events:
            lines.append(f"    T{e.get('turn', '?')}: {e.get('summary', '')}")
        count += 1

    return "\n".join(lines) if count else ""


def format_objective_memory(
    session: dict,
    store: dict,
    graph: dict,
    world_pack: dict,
) -> str:
    """Relationship context for active objectives."""
    objectives = session.get("objectives") or {}
    player = resolve_player_name(world_pack, session)
    lines: list[str] = []

    for scope in ("main", "side"):
        for item in objectives.get(scope) or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("status", "")).lower() != "active":
                continue
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            npc = _npc_in_title(title, world_pack)
            if not npc:
                continue
            edge = get_edge(graph, player, npc)
            prog = relationship_progress_for_objective(title, graph, player, world_pack)
            current = int(prog) if prog is not None else 0
            events = _recent_for_edge(store, player, npc, limit=2)
            block = [f"  目标「{title}」", f"    当前关系值: {current}"]
            if edge:
                block.append(
                    f"    状态: 信任{edge.trust:.0f} 好感{edge.affection:.0f} "
                    f"({edge.relation_type})"
                )
            if events:
                block.append("    最近事件:")
                for e in events:
                    block.append(f"      T{e.get('turn', '?')}: {e.get('summary', '')}")
            lines.extend(block)

    if not lines:
        return ""
    return "【关系目标记忆】\n" + "\n".join(lines)


def read_api_for_plot(
    store: dict,
    graph: dict,
    session: dict,
    world_pack: dict,
) -> str:
    """Relationship tension hints for Plot Director (read-only)."""
    player = resolve_player_name(world_pack, session)
    edges_data = store.get("edges") or {}
    if not edges_data:
        return ""

    tensions: list[str] = []
    checked = 0
    for key, events in edges_data.items():
        if checked >= config.RELATIONSHIP_MEMORY_MAX_CHARACTERS:
            break
        if not isinstance(events, list) or not events:
            continue
        parts = key.split("->", 1)
        if len(parts) != 2 or parts[0] != player:
            continue
        target = parts[1].strip()
        recent = [e for e in events[-3:] if isinstance(e, dict)]
        if not recent:
            continue

        last = recent[-1]
        etype = str(last.get("type", ""))
        summary = str(last.get("summary", "")).strip()
        trust_drop = sum(
            float(e.get("trust_delta", 0) or 0)
            for e in recent
            if float(e.get("trust_delta", 0) or 0) < 0
        )
        host_rise = sum(
            float(e.get("hostility_delta", 0) or 0)
            for e in recent
            if float(e.get("hostility_delta", 0) or 0) > 0
        )

        if etype in ("argument", "conflict", "betrayal") or trust_drop <= -10 or host_rise >= 10:
            advice = "安排修复或缓和事件"
            if etype == "betrayal":
                advice = "安排对质或重建信任事件"
            tensions.append(
                f"  {target}: 最近{summary or etype}；"
                f"信任变化{int(trust_drop)}；建议: {advice}"
            )
            checked += 1
        elif etype in ("romance", "confession") and len(recent) >= 2:
            tensions.append(
                f"  {target}: 关系持续升温；建议: 可推进亲密或承诺节拍"
            )
            checked += 1

    if not tensions:
        return ""
    return "【关系张力 — 记忆驱动】\n" + "\n".join(tensions[:5])


def build_prompt_context(
    store: dict,
    graph: dict,
    session: dict,
    world_pack: dict,
    *,
    names: set[str] | None = None,
) -> str:
    """
    RELATIONSHIP_MEMORY_CONTEXT for prompt injection.
    Limits: max_events_per_edge=3, max_characters=5, max_chars=800.
    """
    player = resolve_player_name(world_pack, session)
    if names is None:
        from engine.character_brain import resolve_brain_character_names
        from engine.memory import load_memory

        memory = load_memory()
        names = resolve_brain_character_names(session, memory, world_pack)

    lines = ["【关系记忆 — 最近事件】"]
    char_count = 0
    for name in sorted(names or []):
        if name == player or char_count >= config.RELATIONSHIP_MEMORY_MAX_CHARACTERS:
            continue
        events = _recent_for_edge(store, player, name)
        if not events:
            continue
        lines.append(f"{name}:")
        for e in events:
            lines.append(f"  T{e.get('turn', '?')}: {e.get('summary', '')}")
        char_count += 1

    if len(lines) <= 1:
        return ""

    text = "\n".join(lines)
    max_chars = config.RELATIONSHIP_MEMORY_MAX_CHARS
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."
    return text


def _npc_in_title(title: str, world_pack: dict) -> str | None:
    world = world_pack.get("world", world_pack) if world_pack else {}
    for ch in world.get("characters") or []:
        if not isinstance(ch, dict) or ch.get("is_main"):
            continue
        name = str(ch.get("name", "")).strip()
        if name and name in title:
            return name
    return None


def ensure_memory_store(store: dict | None = None) -> dict:
    if isinstance(store, dict) and "edges" in store:
        return store
    return load_relationship_memory_store()
