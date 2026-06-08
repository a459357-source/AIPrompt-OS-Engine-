"""
relationship_event_resolver.py — V5.1 auto-resolve dynamics events + triangles
"""

from __future__ import annotations

import logging

from engine.relationship_core import RelationshipEdge, edge_key, get_edge
from engine.relationship_dynamics import (
    BOND_LABELS,
    compute_bond_level,
    get_dynamics,
)
from engine.relationship_memory import RelationshipMemoryEvent, append_memory_event

logger = logging.getLogger(__name__)

_BOND_SUMMARIES = {
    1: "双方关系进入认识阶段",
    2: "双方关系进入熟悉阶段",
    3: "双方关系进入信任阶段",
    4: "双方关系进入亲密阶段",
    5: "双方关系进入羁绊阶段",
}


def resolve_dynamics_events(
    graph: dict,
    dynamics_store: dict,
    memory_store: dict,
    *,
    turn: int,
    player: str,
) -> list[RelationshipMemoryEvent]:
    """Auto-write memory events on bond level upgrades."""
    recorded: list[RelationshipMemoryEvent] = []
    for key, raw in (dynamics_store.get("edges") or {}).items():
        if "->" not in key or not key.startswith(f"{player}->"):
            continue
        target = key.split("->", 1)[1].strip()
        dyn = get_dynamics(dynamics_store, player, target)
        if dyn.bond_level <= dyn.prev_bond_level:
            continue
        summary = _BOND_SUMMARIES.get(
            dyn.bond_level,
            f"关系羁绊升至{BOND_LABELS[min(dyn.bond_level, 5)]}",
        )
        evt = RelationshipMemoryEvent(
            turn=turn,
            actor=player,
            target=target,
            type="romance" if dyn.bond_level >= 4 else "support",
            summary=summary,
            affection_delta=max(0.0, (dyn.bond_level - dyn.prev_bond_level) * 5),
        )
        append_memory_event(memory_store, evt)
        recorded.append(evt)
        logger.info("Bond upgrade event: %s→%s level %d", player, target, dyn.bond_level)
    return recorded


def detect_relationship_triangles(graph: dict, player: str) -> list[dict]:
    """
    Detect tension triangles among player and NPCs.
    Returns list of {nodes, pattern, tension, advice}.
    """
    edges = graph.get("edges") or {}
    nodes: set[str] = {player}
    adj: dict[str, list[RelationshipEdge]] = {}

    for raw in edges.values():
        if not isinstance(raw, dict):
            continue
        e = RelationshipEdge.from_dict(raw)
        if not e.source or not e.target:
            continue
        nodes.add(e.source)
        nodes.add(e.target)
        adj.setdefault(e.source, []).append(e)

    node_list = sorted(nodes - {player})[:8]
    triangles: list[dict] = []

    for i, a in enumerate(node_list):
        for b in node_list[i + 1:]:
            for c in node_list:
                if c in (a, b):
                    continue
                tension = _triangle_tension(adj, player, a, b, c)
                if tension:
                    triangles.append(tension)

    return triangles[:5]


def _triangle_tension(
    adj: dict[str, list[RelationshipEdge]],
    player: str,
    a: str,
    b: str,
    c: str,
) -> dict | None:
    def _find(src: str, tgt: str) -> RelationshipEdge | None:
        for e in adj.get(src, []):
            if e.target == tgt:
                return e
        return None

    pa = _find(player, a)
    pb = _find(player, b)
    ab = _find(a, b)
    bc = _find(b, c)
    ac = _find(a, c)

    if pa and ab and pb:
        if pa.affection >= 55 and ab.hostility >= 40 and pb.hostility >= 35:
            return {
                "nodes": [player, a, b],
                "pattern": "support_rival",
                "tension": "主角亲近一方引发另一方敌意",
                "advice": "安排冲突或调解剧情",
            }

    if pa and bc and _find(player, c):
        pc = _find(player, c)
        if pa.affection >= 50 and bc.hostility >= 45 and pc and pc.trust >= 50:
            return {
                "nodes": [player, a, c],
                "pattern": "ally_enemy_spill",
                "tension": f"{a}与{b}对立牵连{player}与{c}",
                "advice": "安排三方张力场景",
            }

    ea = _find(a, b)
    eb = _find(b, c)
    ec = _find(c, a)
    if ea and eb and ec:
        likes = sum(1 for e in (ea, eb, ec) if e.affection >= 60)
        if likes >= 2:
            return {
                "nodes": [a, b, c],
                "pattern": "romance_triangle",
                "tension": "情感三角关系",
                "advice": "可安排抉择或误会节拍",
            }

    return None


def build_relationship_tension_context(dynamics_store: dict) -> str:
    """Plot Director triangle / tension block."""
    triangles = dynamics_store.get("triangles") or []
    if not triangles:
        return ""

    lines = ["【关系三角张力】"]
    for t in triangles[:3]:
        if not isinstance(t, dict):
            continue
        nodes = t.get("nodes") or []
        advice = str(t.get("advice", "")).strip()
        tension = str(t.get("tension", "")).strip()
        if nodes:
            lines.append(f"  {' / '.join(nodes)}: {tension}；建议: {advice}")
    return "\n".join(lines) if len(lines) > 1 else ""
