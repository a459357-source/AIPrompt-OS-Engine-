"""Tests for V5.1 Relationship Dynamics Engine (Phase C)."""

from __future__ import annotations

import pytest

import config
from engine.relationship_core import (
    RelationshipEdge,
    apply_metric_delta,
    init_graph_from_world,
    set_edge,
)
from engine.relationship_decay import apply_relationship_decay
from engine.relationship_dynamics import (
    compute_bond_level,
    compute_conflict_level,
    empty_dynamics_store,
    get_dynamics,
    momentum_multiplier,
    refresh_edge_dynamics,
    set_dynamics,
    RelationshipDynamicsState,
)
from engine.relationship_event_resolver import detect_relationship_triangles
from engine.relationship_influence import apply_relationship_influence
from engine.relationship_update import apply_turn_relationship_updates


@pytest.fixture
def world_pack():
    return {
        "world": {
            "characters": [
                {"name": "主角", "is_main": True},
                {"name": "长公主", "is_main": False},
                {"name": "宰相", "is_main": False},
            ],
        },
        "custom": {
            "characterRelations": {
                "长公主": {"trust": 0.6, "affection": 0.55},
                "宰相": {"trust": 0.3, "hostility": 0.5},
            },
        },
    }


@pytest.fixture
def memory():
    return {
        "characters": {
            "长公主": {"trust": 0.6, "tier": "核心"},
            "宰相": {"trust": 0.3, "tier": "核心"},
        },
    }


def test_bond_and_conflict_levels():
    friendly = RelationshipEdge(
        source="主角", target="长公主",
        trust=65, affection=70, respect=55, hostility=5,
    )
    assert compute_bond_level(friendly) >= 3
    assert compute_conflict_level(friendly) == 0

    hostile = RelationshipEdge(
        source="主角", target="宰相",
        trust=25, hostility=65, respect=30,
    )
    assert compute_conflict_level(hostile) >= 3


def test_momentum_multiplier_scales():
    assert momentum_multiplier(0) == pytest.approx(1.0)
    assert momentum_multiplier(20) > 1.2


def test_momentum_increases_on_interaction():
    store = empty_dynamics_store()
    edge = RelationshipEdge(source="主角", target="长公主", affection=60, trust=60)
    st = refresh_edge_dynamics(store, edge, turn=10, interacted=True, positive_delta=10)
    assert st.momentum > 0
    assert get_dynamics(store, "主角", "长公主").momentum == st.momentum


def test_decay_after_inactivity(world_pack, memory):
    graph = init_graph_from_world(world_pack, memory, {"turn": 1}, persist=False)
    dyn = empty_dynamics_store()
    player = "主角"
    edge = graph["edges"]["主角→长公主"]
    trust_before = edge["trust"]
    set_dynamics(dyn, player, "长公主", RelationshipDynamicsState(last_interaction_turn=1))
    apply_relationship_decay(graph, dyn, turn=25, player=player, interacted_targets=set())
    trust_after = graph["edges"]["主角→长公主"]["trust"]
    assert trust_after < trust_before


def test_influence_rival_reaction(world_pack):
    graph = init_graph_from_world(world_pack, persist=False)
    dyn = empty_dynamics_store()
    player = "主角"
    apply_metric_delta(graph, player, "长公主", "affection", 5, turn=5)
    set_edge(graph, RelationshipEdge(
        source="宰相", target="长公主", hostility=55, trust=30, affection=20,
    ))
    host_before = graph["edges"].get("宰相→主角", {}).get("hostility", 0)
    apply_relationship_influence(graph, dyn, 5, player, {"长公主"})
    host_after = graph["edges"].get("宰相→主角", {}).get("hostility", 0)
    assert host_after >= host_before


def test_triangle_detection(world_pack):
    graph = init_graph_from_world(world_pack, persist=False)
    set_edge(graph, RelationshipEdge(source="宰相", target="长公主", hostility=50, trust=30))
    triangles = detect_relationship_triangles(graph, "主角")
    assert isinstance(triangles, list)


def test_turn_update_applies_dynamics(world_pack, memory, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RELATIONSHIP_GRAPH_PATH", tmp_path / "relationship_graph.json")
    graph = init_graph_from_world(world_pack, memory, {"turn": 50}, persist=False)
    dyn = empty_dynamics_store()
    set_dynamics(dyn, "主角", "长公主", RelationshipDynamicsState(momentum=12, last_interaction_turn=49))
    response = {"story": "长公主与主角并肩作战。"}
    prev = ["支援长公主|长公主好感+10"]
    graph, _mem, dyn_out = apply_turn_relationship_updates(
        response, {"turn": 51}, "A", memory, world_pack,
        prev_options=prev,
        relationship_graph=graph,
        relationship_memory={"version": 1, "edges": {}},
        relationship_dynamics=dyn,
        persist=False,
    )
    st = get_dynamics(dyn_out, "主角", "长公主")
    assert st.momentum >= 12
    assert st.last_interaction_turn == 51
