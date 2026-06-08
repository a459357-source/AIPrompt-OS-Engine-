"""
relationship_event_builder.py — V5.1 Event Director relationship candidates
=============================================================================
Rule-based event suggestions from relationship history. No AI calls.
"""

from __future__ import annotations

import config
from engine.relationship_core import ensure_graph, get_edge, resolve_player_name
from engine.relationship_memory import get_edge_events
from engine.relationship_recall import ensure_memory_store


_SUPPORT_TYPES = frozenset({
    "support", "protect", "rescue", "cooperation",
})

_ROMANCE_TYPES = frozenset({
    "romance", "confession", "gift",
})

_CONFLICT_TYPES = frozenset({
    "argument", "conflict", "betrayal",
})


def build_relationship_event_candidates(
    store: dict | None,
    graph: dict | None,
    session: dict,
    world_pack: dict,
) -> list[dict]:
    """
    Return candidate relationship events per NPC.

    Each item: {target, reason, candidates: [str, ...]}
    """
    if not config.RELATIONSHIP_ENGINE_ENABLED:
        return []

    store = ensure_memory_store(store)
    graph = graph or ensure_graph(world_pack, session=session)
    player = resolve_player_name(world_pack, session)
    results: list[dict] = []

    seen_targets: set[str] = set()
    for key in (store.get("edges") or {}):
        parts = key.split("->", 1)
        if len(parts) != 2 or parts[0] != player:
            continue
        target = parts[1].strip()
        if not target or target in seen_targets:
            continue
        seen_targets.add(target)

        events = get_edge_events(store, player, target)
        if not events:
            continue

        recent = events[-5:]
        support_count = sum(
            1 for e in recent
            if str(e.get("type", "")) in _SUPPORT_TYPES
            and float(e.get("trust_delta", 0) or 0) >= 0
        )
        romance_count = sum(1 for e in recent if str(e.get("type", "")) in _ROMANCE_TYPES)
        conflict_count = sum(1 for e in recent if str(e.get("type", "")) in _CONFLICT_TYPES)

        edge = get_edge(graph, player, target)
        candidates: list[str] = []
        reason = ""

        if support_count >= 3:
            candidates = ["深夜谈心", "赠送信物", "表露秘密"]
            reason = f"连续{support_count}次获得{target}支持"
        elif romance_count >= 2 and edge and edge.affection >= 60:
            candidates = ["私下约会", "牵手同行", "互赠定情物"]
            reason = f"与{target}关系持续升温"
        elif conflict_count >= 2:
            candidates = ["当面道歉", "第三方调解", "共同对敌以修复关系"]
            reason = f"与{target}近期多次冲突"
        elif edge and edge.trust >= 75 and edge.affection >= 55:
            candidates = ["请求协助", "分享情报", "结盟提议"]
            reason = f"与{target}信任稳固"

        if candidates:
            results.append({
                "target": target,
                "reason": reason,
                "candidates": candidates[:4],
            })

    return results[: config.RELATIONSHIP_MEMORY_MAX_CHARACTERS]


def format_event_candidates_for_director(
    store: dict | None,
    graph: dict | None,
    session: dict,
    world_pack: dict,
) -> str:
    """Format candidates for Event Director prompt injection."""
    items = build_relationship_event_candidates(store, graph, session, world_pack)
    if not items:
        return ""

    lines = ["【关系事件候选 — Event Director 参考（非强制）】"]
    for item in items[:3]:
        target = item.get("target", "")
        reason = item.get("reason", "")
        cands = item.get("candidates") or []
        if cands:
            lines.append(
                f"- {target}（{reason}）→ 候选: {' / '.join(cands)}"
            )
    return "\n".join(lines)
