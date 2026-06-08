"""
relationship_update.py — V5.1 per-turn relationship graph + memory + dynamics updates.
Runs after apply_turn / memory updater; graph is source of truth.
"""

from __future__ import annotations

import logging

import config
from engine.memory import parse_option_metric_deltas, guess_trust_delta_from_story
from engine.memory_names import resolve_roster_name, is_memory_active_npc
from engine.relationship_core import (
    RELATIONSHIP_EVENT_KINDS,
    apply_metric_delta,
    ensure_graph,
    enqueue_relationship_event,
    infer_relation_type,
    resolve_player_name,
    save_graph,
    set_edge,
    RelationshipEdge,
    _mirror_graph_to_memory,
)
from engine.relationship_dynamics import (
    apply_turn_dynamics,
    empty_dynamics_store,
    get_dynamics,
    momentum_multiplier,
)
from engine.relationship_memory import (
    empty_store,
    record_turn_memories,
    snapshot_player_edges,
)

logger = logging.getLogger(__name__)

_EVENT_KEYWORDS: dict[str, str] = {
    "告白": "告白",
    "背叛": "背叛",
    "结盟": "结盟",
    "婚约": "婚约",
    "决裂": "决裂",
    "和解": "和解",
}


def _resolve_chosen_option(choice: str | None, prev_options: list[str]) -> list[str]:
    if not choice:
        return []
    texts: list[str] = []
    choice_map = {"A": 0, "B": 1, "C": 2, "D": 3}
    if choice.upper() in choice_map and prev_options:
        idx = choice_map[choice.upper()]
        if 0 <= idx < len(prev_options):
            texts.append(prev_options[idx])
    elif prev_options:
        stripped = choice.strip()
        for opt in prev_options:
            action = opt.split("→")[0].split("|")[0].strip()
            if stripped == action or stripped in opt or action in stripped:
                texts.append(opt)
                break
    texts.append(choice)
    return texts


def _detect_relationship_events(
    story: str,
    player: str,
    graph: dict,
    turn: int,
) -> None:
    text = story or ""
    for kw, kind in _EVENT_KEYWORDS.items():
        if kw not in text:
            continue
        for edge_raw in (graph.get("edges") or {}).values():
            if not isinstance(edge_raw, dict):
                continue
            src = str(edge_raw.get("source", "")).strip()
            tgt = str(edge_raw.get("target", "")).strip()
            if src != player and tgt != player:
                continue
            other = tgt if src == player else src
            if other and other in text:
                enqueue_relationship_event(
                    graph,
                    title=f"{other}：{kw}",
                    source=player,
                    target=other,
                    kind=kind,
                    turn=turn,
                )
                logger.info("Relationship event detected: %s %s→%s", kind, player, other)


def _large_delta_event(
    edge: RelationshipEdge,
    metric: str,
    delta_100: float,
    player: str,
    turn: int,
    graph: dict,
) -> None:
    if abs(delta_100) < 12:
        return
    if metric in ("affection", "attraction") and delta_100 > 0:
        kind = "告白" if edge.affection >= 65 else "结盟"
    elif metric == "hostility" and delta_100 > 0:
        kind = "决裂"
    elif metric == "trust" and delta_100 > 15:
        kind = "结盟"
    else:
        return
    if kind in RELATIONSHIP_EVENT_KINDS:
        enqueue_relationship_event(
            graph,
            title=f"{edge.target}：关系变化（{metric}{delta_100:+.0f}）",
            source=player,
            target=edge.target,
            kind=kind,
            turn=turn,
        )


def _active_npc_targets(memory: dict, player: str) -> set[str]:
    targets: set[str] = set()
    for name in memory.get("characters", {}):
        if name != player and is_memory_active_npc(name, memory):
            targets.add(name)
    return targets


def _apply_delta_with_momentum(
    graph: dict,
    dynamics_store: dict,
    player: str,
    target: str,
    metric: str,
    delta: float,
    turn: int,
    positive_deltas: dict[str, float],
) -> RelationshipEdge | None:
    dyn = get_dynamics(dynamics_store, player, target)
    scaled = float(delta)
    d100 = scaled * 100.0 if abs(scaled) <= 1.0 else scaled
    if d100 > 0 and metric in ("trust", "affection", "respect", "attraction"):
        d100 *= momentum_multiplier(dyn.momentum)
        scaled = d100 / 100.0 if abs(float(delta)) <= 1.0 else d100
    edge = apply_metric_delta(graph, player, target, metric, scaled, turn)
    if edge and d100 > 0 and metric in ("trust", "affection"):
        positive_deltas[target] = positive_deltas.get(target, 0.0) + d100
    return edge


def _reinfer_player_edges(graph: dict, player: str) -> None:
    for raw in list((graph.get("edges") or {}).values()):
        if isinstance(raw, dict) and raw.get("source") == player:
            edge = RelationshipEdge.from_dict(raw)
            edge.relation_type = infer_relation_type(edge)
            set_edge(graph, edge)


def apply_turn_relationship_updates(
    response: dict,
    state: dict,
    choice: str | None,
    memory: dict,
    world_pack: dict,
    *,
    prev_options: list[str] | None = None,
    relationship_graph: dict | None = None,
    relationship_memory: dict | None = None,
    relationship_dynamics: dict | None = None,
    persist: bool = True,
) -> tuple[dict, dict, dict]:
    """Update graph, memory, and dynamics from turn inputs."""
    mem_store = relationship_memory if isinstance(relationship_memory, dict) else empty_store()
    dyn_store = relationship_dynamics if isinstance(relationship_dynamics, dict) else empty_dynamics_store()

    if not config.RELATIONSHIP_ENGINE_ENABLED:
        from engine.relationship_core import load_graph
        return load_graph(), mem_store, dyn_store

    turn = int(state.get("turn", 0) or 0)
    story = response.get("story", "") or ""
    player = resolve_player_name(world_pack, state)
    graph = relationship_graph if relationship_graph is not None else ensure_graph(
        world_pack, memory, state, persist=False,
    )
    prev_options = prev_options or []

    targets = _active_npc_targets(memory, player)
    snapshots = snapshot_player_edges(graph, player, targets)
    interacted: set[str] = set()
    positive_deltas: dict[str, float] = {}

    if choice:
        for opt_text in _resolve_chosen_option(choice, prev_options):
            for char_name, metric, delta in parse_option_metric_deltas([opt_text]):
                resolved = resolve_roster_name(char_name, memory, world_pack, state)
                if not resolved or resolved == player:
                    continue
                if not is_memory_active_npc(resolved, memory):
                    continue
                targets.add(resolved)
                interacted.add(resolved)
                if resolved not in snapshots:
                    snapshots[resolved] = snapshot_player_edges(
                        graph, player, {resolved},
                    )[resolved]
                edge = _apply_delta_with_momentum(
                    graph, dyn_store, player, resolved, metric, float(delta),
                    turn, positive_deltas,
                )
                if edge:
                    d100 = float(delta) * 100.0 if abs(float(delta)) <= 1.0 else float(delta)
                    _large_delta_event(edge, metric, d100, player, turn, graph)

    for char_name, delta, _flag in guess_trust_delta_from_story(story):
        if char_name == "__all_present__":
            for name in list(memory.get("characters", {}).keys()):
                if name in story and name != player:
                    targets.add(name)
                    interacted.add(name)
                    _apply_delta_with_momentum(
                        graph, dyn_store, player, name, "trust", delta * 100,
                        turn, positive_deltas,
                    )
        elif char_name != player and is_memory_active_npc(char_name, memory):
            targets.add(char_name)
            interacted.add(char_name)
            _apply_delta_with_momentum(
                graph, dyn_store, player, char_name, "trust", delta * 100,
                turn, positive_deltas,
            )

    for name in memory.get("characters", {}):
        if name == player or name not in story or player not in story:
            continue
        if is_memory_active_npc(name, memory):
            targets.add(name)
            interacted.add(name)
            _apply_delta_with_momentum(
                graph, dyn_store, player, name, "affection", 1.0,
                turn, positive_deltas,
            )

    _detect_relationship_events(story, player, graph, turn)
    _reinfer_player_edges(graph, player)

    record_turn_memories(
        mem_store,
        turn=turn,
        player=player,
        snapshots=snapshots,
        graph=graph,
        story=story,
    )

    apply_turn_dynamics(
        graph,
        dyn_store,
        mem_store,
        turn=turn,
        player=player,
        interacted_targets=interacted,
        turn_positive_deltas=positive_deltas,
    )
    _reinfer_player_edges(graph, player)

    _mirror_graph_to_memory(graph, player, memory, persist=False)
    if persist:
        save_graph(graph, persist=True)
    return graph, mem_store, dyn_store


def sync_session_objectives(state: dict, graph: dict, world_pack: dict) -> dict:
    from engine.relationship_core import sync_objectives_from_graph
    return sync_objectives_from_graph(state, graph, world_pack)
