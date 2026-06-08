"""
relationship_event_builder.py — V5.1 Event Director relationship candidates
=============================================================================
Rule-based event suggestions from history + dynamics. No AI calls.
"""

from __future__ import annotations

import config
from engine.relationship_core import ensure_graph, get_edge, resolve_player_name
from engine.relationship_dynamics import BOND_LABELS, get_dynamics
from engine.relationship_memory import get_edge_events
from engine.relationship_recall import ensure_dynamics_store, ensure_memory_store


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
    dynamics_store: dict | None = None,
) -> list[dict]:
    """
    Return candidate relationship events per NPC.
    Sources: memory history, momentum, bond, conflict, triangles.
    """
    if not config.RELATIONSHIP_ENGINE_ENABLED:
        return []

    store = ensure_memory_store(store)
    dyn_store = ensure_dynamics_store(dynamics_store)
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
        dyn = get_dynamics(dyn_store, player, target)
        edge = get_edge(graph, player, target)
        candidates: list[str] = []
        reason = ""

        recent = events[-5:] if events else []
        support_count = sum(
            1 for e in recent
            if str(e.get("type", "")) in _SUPPORT_TYPES
            and float(e.get("trust_delta", 0) or 0) >= 0
        )
        romance_count = sum(1 for e in recent if str(e.get("type", "")) in _ROMANCE_TYPES)
        conflict_count = sum(1 for e in recent if str(e.get("type", "")) in _CONFLICT_TYPES)

        if dyn.momentum >= 15:
            candidates = ["深夜谈心", "共同冒险", "互赠信物"]
            reason = f"高惯性（Momentum {dyn.momentum:.0f}）"
        elif support_count >= 3:
            candidates = ["深夜谈心", "赠送信物", "表露秘密"]
            reason = f"连续{support_count}次获得{target}支持"
        elif dyn.bond_level >= 3 and dyn.bond_level < 5:
            candidates = ["信任考验", "私密对话", "承诺时刻"]
            reason = f"Bond Level {dyn.bond_level}→{dyn.bond_level + 1}（{BOND_LABELS[dyn.bond_level]}）"
        elif romance_count >= 2 and edge and edge.affection >= 60:
            candidates = ["私下约会", "牵手同行", "互赠定情物"]
            reason = f"与{target}关系持续升温"
        elif dyn.conflict_level >= 2 or conflict_count >= 2:
            candidates = ["当面道歉", "第三方调解", "共同对敌以修复关系"]
            reason = f"与{target}冲突等级 {dyn.conflict_level}"
        elif edge and edge.trust >= 75 and edge.affection >= 55:
            candidates = ["请求协助", "分享情报", "结盟提议"]
            reason = f"与{target}信任稳固"

        if candidates:
            results.append({
                "target": target,
                "reason": reason,
                "candidates": candidates[:4],
            })

    for tri in (dyn_store.get("triangles") or [])[:2]:
        if not isinstance(tri, dict):
            continue
        nodes = tri.get("nodes") or []
        advice = str(tri.get("advice", "")).strip()
        if len(nodes) >= 3 and advice:
            results.append({
                "target": " / ".join(str(n) for n in nodes[:3]),
                "reason": str(tri.get("tension", "三角张力")),
                "candidates": [advice, "三方对峙", "意外撞见"],
            })

    return results[: config.RELATIONSHIP_MEMORY_MAX_CHARACTERS]


def format_event_candidates_for_director(
    store: dict | None,
    graph: dict | None,
    session: dict,
    world_pack: dict,
    dynamics_store: dict | None = None,
) -> str:
    """Format candidates for Event Director prompt injection."""
    items = build_relationship_event_candidates(
        store, graph, session, world_pack, dynamics_store=dynamics_store,
    )
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
