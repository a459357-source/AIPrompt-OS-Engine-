"""
relationship_decay.py — V5.1 relationship decay when inactive
"""

from __future__ import annotations

import logging

import config
from engine.relationship_core import RelationshipEdge, get_edge, set_edge
from engine.relationship_dynamics import get_dynamics, set_dynamics, RelationshipDynamicsState

logger = logging.getLogger(__name__)


def apply_relationship_decay(
    graph: dict,
    dynamics_store: dict,
    turn: int,
    player: str,
    interacted_targets: set[str],
) -> None:
    """
    Edges with no interaction for > RELATIONSHIP_DECAY_INACTIVE_TURNS
    lose small trust/affection each turn.
    """
    threshold = config.RELATIONSHIP_DECAY_INACTIVE_TURNS
    edges = graph.get("edges") or {}

    for key, raw in edges.items():
        if not isinstance(raw, dict) or raw.get("source") != player:
            continue
        target = str(raw.get("target", "")).strip()
        if not target or target in interacted_targets:
            continue

        dyn = get_dynamics(dynamics_store, player, target)
        last = dyn.last_interaction_turn or int(raw.get("last_update_turn", 0) or 0)
        if last <= 0:
            last = turn
        inactive = turn - last
        if inactive <= threshold:
            continue

        edge = RelationshipEdge.from_dict(raw)
        decay = min(2.0, (inactive - threshold) * 0.15)
        edge.trust = _clamp(edge.trust - decay)
        edge.affection = _clamp(edge.affection - decay * 0.8)
        edge.last_update_turn = turn
        set_edge(graph, edge)

        dyn.momentum = max(0.0, dyn.momentum - 3.0)
        set_dynamics(dynamics_store, player, target, dyn)
        logger.debug(
            "Relationship decay: %s→%s inactive=%d trust-%.1f",
            player, target, inactive, decay,
        )


def _clamp(v: float) -> float:
    return round(max(0.0, min(100.0, v)), 1)
