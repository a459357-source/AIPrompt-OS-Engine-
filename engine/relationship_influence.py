"""
relationship_influence.py — V5.1 one-hop relationship propagation
"""

from __future__ import annotations

import logging

import config
from engine.relationship_core import (
    RelationshipEdge,
    apply_metric_delta,
    edge_key,
    get_edge,
)

logger = logging.getLogger(__name__)


def apply_relationship_influence(
    graph: dict,
    dynamics_store: dict,
    turn: int,
    player: str,
    interacted_targets: set[str],
) -> None:
    """
    One-hop propagation only (no recursion).

    - Third parties react when player befriends their rival/enemy.
    - A→B positive + B→C negative ⇒ slight negative spill to player→C.
    """
    if not interacted_targets:
        return

    coeff = config.RELATIONSHIP_INFLUENCE_COEFF
    edges = graph.get("edges") or {}

    _react_rivals_to_befriending(graph, edges, player, turn, interacted_targets, coeff)
    _spill_through_triads(graph, player, turn, interacted_targets, coeff)


def _react_rivals_to_befriending(
    graph: dict,
    edges: dict,
    player: str,
    turn: int,
    interacted_targets: set[str],
    coeff: float,
) -> None:
    for target in interacted_targets:
        pe = get_edge(graph, player, target)
        if not pe or pe.affection < 50:
            continue
        for raw in list(edges.values()):
            if not isinstance(raw, dict):
                continue
            src = str(raw.get("source", "")).strip()
            tgt = str(raw.get("target", "")).strip()
            if tgt != target or src == player:
                continue
            third = RelationshipEdge.from_dict(raw)
            if third.hostility < 40 and third.relation_type not in ("enemy", "rival"):
                continue
            delta_h = 2.0 * coeff * 10
            delta_t = -2.0 * coeff * 10
            apply_metric_delta(graph, src, player, "hostility", delta_h, turn)
            apply_metric_delta(graph, player, src, "trust", delta_t, turn)
            logger.debug("Influence: %s reacts to player↔%s", src, target)


def _spill_through_triads(
    graph: dict,
    player: str,
    turn: int,
    interacted_targets: set[str],
    coeff: float,
) -> None:
    """A likes B, B dislikes C ⇒ player close to A gets slight negative toward C."""
    edges = graph.get("edges") or {}
    parsed: list[RelationshipEdge] = []
    for raw in list(edges.values()):
        if isinstance(raw, dict):
            parsed.append(RelationshipEdge.from_dict(raw))

    for ab in parsed:
        if ab.affection < 55:
            continue
        b, a = ab.target, ab.source
        for bc in parsed:
            if bc.source != b:
                continue
            c = bc.target
            if c in (a, b, player):
                continue
            if bc.hostility < 45 and bc.trust > 40:
                continue
            if a == player and b in interacted_targets:
                _apply_spill(graph, player, c, coeff, turn)
            elif a != player:
                pa = get_edge(graph, player, a)
                if pa and pa.affection >= 50 and a in interacted_targets:
                    _apply_spill(graph, player, c, coeff, turn)


def _apply_spill(graph: dict, player: str, c: str, coeff: float, turn: int) -> None:
    apply_metric_delta(graph, player, c, "trust", -3.0 * coeff * 10, turn)
    apply_metric_delta(graph, player, c, "hostility", 1.5 * coeff * 10, turn)
