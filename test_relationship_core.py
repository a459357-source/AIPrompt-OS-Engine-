"""Tests for V5.1 Relationship Core (Phase A)."""

from __future__ import annotations

import json

import pytest

import config
from engine.relationship_core import (
    RelationshipEdge,
    apply_metric_delta,
    edge_key,
    infer_relation_type,
    init_graph_from_world,
    relationship_progress_for_objective,
    sync_objectives_from_graph,
    build_relationship_context_for_brain,
)
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
                "长公主": {
                    "trust": 0.8,
                    "affection": 0.75,
                    "respect": 0.6,
                    "relationshipType": "ally",
                },
                "宰相": {
                    "trust": 0.2,
                    "hostility": 0.7,
                    "relationshipType": "enemy",
                },
            },
        },
    }


@pytest.fixture
def memory():
    return {
        "characters": {
            "长公主": {"trust": 0.5, "tier": "核心"},
            "宰相": {"trust": 0.3, "tier": "核心"},
        },
    }


def test_infer_relation_type_lover_and_enemy():
    lover = RelationshipEdge(
        source="主角", target="长公主",
        affection=75, attraction=65, trust=60,
    )
    assert infer_relation_type(lover) == "lover"

    enemy = RelationshipEdge(
        source="主角", target="宰相",
        hostility=65, trust=30,
    )
    assert infer_relation_type(enemy) == "enemy"


def test_init_graph_creates_directed_edges(world_pack, memory, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RELATIONSHIP_GRAPH_PATH", tmp_path / "relationship_graph.json")
    graph = init_graph_from_world(world_pack, memory, {"turn": 0}, persist=True)

    assert "长公主" in graph["nodes"]
    fwd = graph["edges"][edge_key("主角", "长公主")]
    assert fwd["trust"] == pytest.approx(80.0)
    assert fwd["affection"] == pytest.approx(75.0)
    rev_key = edge_key("长公主", "主角")
    assert rev_key in graph["edges"]
    assert graph["edges"][rev_key]["affection"] < fwd["affection"]


def test_apply_metric_delta_asymmetric(world_pack):
    graph = {"version": 1, "nodes": {}, "edges": {}, "events": [], "pending_events": []}
    apply_metric_delta(graph, "主角", "长公主", "affection", 0.05, turn=1)
    edge = graph["edges"][edge_key("主角", "长公主")]
    assert edge["affection"] == pytest.approx(55.0)


def test_relationship_progress_for_objective(world_pack, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RELATIONSHIP_GRAPH_PATH", tmp_path / "relationship_graph.json")
    graph = init_graph_from_world(world_pack, persist=False)
    prog = relationship_progress_for_objective("获得长公主信任", graph, "主角", world_pack)
    assert prog is not None
    assert prog >= 70


def test_sync_objectives_from_graph(world_pack):
    graph = init_graph_from_world(world_pack, persist=False)
    session = {
        "turn": 5,
        "objectives": {
            "main": [{"id": "m1", "title": "获得长公主支持", "status": "active", "progress": 0}],
            "side": [],
        },
    }
    updated = sync_objectives_from_graph(session, graph, world_pack)
    main = updated["objectives"]["main"][0]
    assert main["progress"] > 0


def test_apply_turn_relationship_updates_from_choice(world_pack, memory, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RELATIONSHIP_GRAPH_PATH", tmp_path / "relationship_graph.json")
    graph = init_graph_from_world(world_pack, memory, {"turn": 1}, persist=False)
    response = {"story": "长公主向主角微笑，两人关系更近了一步。"}
    state = {"turn": 2}
    prev_options = ["与长公主深谈|长公主好感+5"]
    graph, _mem, _dyn = apply_turn_relationship_updates(
        response, state, "A", memory, world_pack,
        prev_options=prev_options,
        relationship_graph=graph,
        persist=False,
    )
    edge = graph["edges"][edge_key("主角", "长公主")]
    assert edge["affection"] > 75.0


def test_brain_context_includes_graph(world_pack):
    graph = init_graph_from_world(world_pack, persist=False)
    text = build_relationship_context_for_brain(
        {"长公主"}, graph, "主角", world_pack,
    )
    assert "关系图谱" in text
    assert "长公主" in text


def test_relationship_event_on_keyword(world_pack, memory, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RELATIONSHIP_GRAPH_PATH", tmp_path / "relationship_graph.json")
    graph = init_graph_from_world(world_pack, memory, {"turn": 3}, persist=False)
    response = {"story": "长公主向主角告白，场面一度尴尬。"}
    graph, _mem, _dyn = apply_turn_relationship_updates(
        response, {"turn": 4}, None, memory, world_pack,
        relationship_graph=graph,
        persist=False,
    )
    events = graph.get("events") or []
    assert any("告白" in str(e.get("kind", "")) for e in events)
