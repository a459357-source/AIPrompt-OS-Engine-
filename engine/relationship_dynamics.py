"""
relationship_dynamics.py — V5.1 Relationship Dynamics Engine (Phase C)
======================================================================
Momentum, bond/conflict levels, volatility; per-edge dynamics state.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any

import config
from engine import io_utils
from engine.relationship_core import (
    RelationshipEdge,
    apply_metric_delta,
    edge_key,
    get_edge,
    set_edge,
)

logger = logging.getLogger(__name__)

BOND_LABELS = ("陌生", "认识", "熟悉", "信任", "亲密", "羁绊")
CONFLICT_LABELS = ("无", "摩擦", "对立", "敌视", "仇恨", "死敌")


@dataclass
class RelationshipDynamicsState:
    last_interaction_turn: int = 0
    momentum: float = 0.0
    volatility: float = 0.2
    bond_level: int = 0
    conflict_level: int = 0
    prev_bond_level: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict | None) -> RelationshipDynamicsState:
        raw = raw if isinstance(raw, dict) else {}
        return cls(
            last_interaction_turn=int(raw.get("last_interaction_turn", 0) or 0),
            momentum=_f(raw.get("momentum", 0)),
            volatility=_f(raw.get("volatility", 0.2), 0.2),
            bond_level=int(raw.get("bond_level", 0) or 0),
            conflict_level=int(raw.get("conflict_level", 0) or 0),
            prev_bond_level=int(raw.get("prev_bond_level", 0) or 0),
        )


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return default


def dynamics_edge_key(actor: str, target: str) -> str:
    return f"{actor.strip()}->{target.strip()}"


def empty_dynamics_store() -> dict:
    return {"version": 1, "edges": {}, "triangles": []}


def load_dynamics_store() -> dict:
    try:
        data = io_utils.read_json(config.RELATIONSHIP_DYNAMICS_PATH)
        if isinstance(data, dict) and "edges" in data:
            return data
    except Exception:
        pass
    return empty_dynamics_store()


def get_dynamics(store: dict, actor: str, target: str) -> RelationshipDynamicsState:
    raw = (store.get("edges") or {}).get(dynamics_edge_key(actor, target))
    return RelationshipDynamicsState.from_dict(raw)


def set_dynamics(store: dict, actor: str, target: str, state: RelationshipDynamicsState) -> None:
    store.setdefault("edges", {})[dynamics_edge_key(actor, target)] = state.to_dict()


def compute_bond_level(edge: RelationshipEdge) -> int:
    """Derive bond 0–5 from six metrics (fixed vocabulary)."""
    t, a, r, d = edge.trust, edge.affection, edge.respect, edge.dependence
    h = edge.hostility
    if h >= 55:
        return max(0, 1)
    if a >= 75 and t >= 70 and d >= 40:
        return 5
    if a >= 65 and t >= 55:
        return 4
    if t >= 60 and h < 30:
        return 3
    if (t + a) / 2 >= 45:
        return 2
    if max(t, a) >= 35:
        return 1
    return 0


def compute_conflict_level(edge: RelationshipEdge) -> int:
    """Derive conflict 0–5 from hostility / trust / respect."""
    h, t, r = edge.hostility, edge.trust, edge.respect
    if h >= 75 or (h >= 55 and t < 25):
        return 5
    if h >= 60:
        return 4
    if h >= 45 or (h >= 35 and t < 40):
        return 3
    if h >= 30 or (h >= 20 and r < 35):
        return 2
    if h >= 15 or t < 30:
        return 1
    return 0


def momentum_multiplier(momentum: float) -> float:
    """Scale positive deltas when momentum is high."""
    m = max(0.0, min(momentum, config.RELATIONSHIP_MOMENTUM_CAP))
    return 1.0 + m * 0.015


def update_volatility(state: RelationshipDynamicsState, delta_mag: float) -> None:
    state.volatility = round(
        max(0.1, min(0.9, state.volatility * 0.85 + delta_mag * 0.02)),
        2,
    )


def refresh_edge_dynamics(
    store: dict,
    edge: RelationshipEdge,
    turn: int,
    *,
    interacted: bool,
    positive_delta: float = 0.0,
) -> RelationshipDynamicsState:
    """Update dynamics state for one edge after turn processing."""
    state = get_dynamics(store, edge.source, edge.target)
    state.prev_bond_level = state.bond_level
    state.bond_level = compute_bond_level(edge)
    state.conflict_level = compute_conflict_level(edge)

    if interacted:
        state.last_interaction_turn = turn
        if positive_delta > 0:
            gain = min(8.0, positive_delta * 0.6)
            state.momentum = min(
                config.RELATIONSHIP_MOMENTUM_CAP,
                state.momentum + gain,
            )
        update_volatility(state, abs(positive_delta))
    else:
        state.momentum = max(0.0, state.momentum - 2.0)

    set_dynamics(store, edge.source, edge.target, state)
    return state


def bond_progress_to_next(edge: RelationshipEdge, bond: int) -> int:
    """0–100 progress toward next bond level."""
    if bond >= 5:
        return 100
    thresholds = [
        (35, "max_metric"),
        (45, "avg_ta"),
        (60, "trust"),
        (65, "affection"),
        (75, "bond5"),
    ]
    t, a = edge.trust, edge.affection
    if bond == 0:
        cur, need = max(t, a), 35
    elif bond == 1:
        cur, need = (t + a) / 2, 45
    elif bond == 2:
        cur, need = t, 60
    elif bond == 3:
        cur, need = a, 65
    else:
        cur = min(t, a, edge.dependence * 1.5)
        need = 70
    return int(max(0, min(100, cur / need * 100)))


def trend_label(state: RelationshipDynamicsState) -> str:
    if state.momentum >= 15:
        return "持续升温"
    if state.momentum >= 8:
        return "稳步改善"
    if state.conflict_level >= 3:
        return "紧张对立"
    if state.conflict_level >= 1:
        return "存在摩擦"
    if state.momentum <= 2 and state.bond_level >= 2:
        return "趋于平稳"
    return "冷淡"


def ensure_dynamics_for_graph(store: dict, graph: dict, player: str) -> None:
    """Seed dynamics entries for existing player→NPC edges."""
    for key, raw in (graph.get("edges") or {}).items():
        if not isinstance(raw, dict) or raw.get("source") != player:
            continue
        target = str(raw.get("target", "")).strip()
        if not target:
            continue
        dk = dynamics_edge_key(player, target)
        if dk not in (store.get("edges") or {}):
            edge = RelationshipEdge.from_dict(raw)
            st = RelationshipDynamicsState(
                last_interaction_turn=int(raw.get("last_update_turn", 0) or 0),
                bond_level=compute_bond_level(edge),
                conflict_level=compute_conflict_level(edge),
            )
            set_dynamics(store, player, target, st)


def apply_turn_dynamics(
    graph: dict,
    dynamics_store: dict,
    memory_store: dict,
    *,
    turn: int,
    player: str,
    interacted_targets: set[str],
    turn_positive_deltas: dict[str, float],
) -> dict:
    """
    Orchestrate per-turn dynamics refresh (momentum/bond/conflict).
    Decay and influence run in sibling modules before/after.
    """
    from engine.relationship_decay import apply_relationship_decay
    from engine.relationship_influence import apply_relationship_influence
    from engine.relationship_event_resolver import (
        detect_relationship_triangles,
        resolve_dynamics_events,
    )

    ensure_dynamics_for_graph(dynamics_store, graph, player)

    for target in interacted_targets:
        edge = get_edge(graph, player, target)
        if not edge:
            continue
        pos = turn_positive_deltas.get(target, 0.0)
        refresh_edge_dynamics(
            dynamics_store, edge, turn,
            interacted=True, positive_delta=pos,
        )

    apply_relationship_decay(graph, dynamics_store, turn, player, interacted_targets)
    apply_relationship_influence(
        graph, dynamics_store, turn, player, interacted_targets,
    )

    for key, raw in list((graph.get("edges") or {}).items()):
        if not isinstance(raw, dict) or raw.get("source") != player:
            continue
        target = str(raw.get("target", "")).strip()
        if target in interacted_targets:
            continue
        edge = RelationshipEdge.from_dict(raw)
        refresh_edge_dynamics(dynamics_store, edge, turn, interacted=False)

    triangles = detect_relationship_triangles(graph, player)
    dynamics_store["triangles"] = triangles

    resolve_dynamics_events(
        graph, dynamics_store, memory_store, turn=turn, player=player,
    )

    return dynamics_store
