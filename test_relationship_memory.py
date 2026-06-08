"""Tests for V5.1 Relationship Memory (Phase B)."""

from __future__ import annotations

import pytest

import config
from engine.relationship_core import init_graph_from_world
from engine.relationship_memory import (
    RELATION_EVENT_TYPES,
    RelationshipMemoryEvent,
    append_memory_event,
    empty_store,
    record_edge_memory,
    should_record_memory,
    memory_edge_key,
)
from engine.relationship_update import apply_turn_relationship_updates
from engine.relationship_recall import (
    build_prompt_context,
    format_brain_memory,
    format_objective_memory,
)
from engine.relationship_event_builder import build_relationship_event_candidates
from engine.relationship_core import read_api_for_plot


@pytest.fixture
def world_pack():
    return {
        "world": {
            "characters": [
                {"name": "主角", "is_main": True},
                {"name": "长公主", "is_main": False},
            ],
        },
        "custom": {
            "characterRelations": {
                "长公主": {"trust": 0.5, "affection": 0.5},
            },
        },
    }


@pytest.fixture
def memory():
    return {"characters": {"长公主": {"trust": 0.5, "tier": "核心"}}}


def test_memory_event_types_fixed():
    assert "romance" in RELATION_EVENT_TYPES
    assert "betrayal" in RELATION_EVENT_TYPES
    assert "custom_ai_type" not in RELATION_EVENT_TYPES


def test_should_record_on_delta_threshold():
    deltas = {"affection": 8.0}
    assert should_record_memory(deltas, "neutral", "neutral") is True
    assert should_record_memory({"affection": 2.0}, "neutral", "neutral") is False


def test_should_record_on_type_change():
    assert should_record_memory({}, "friend", "lover") is True


def test_record_edge_memory_romance_summary():
    store = empty_store()
    before = {
        "relation_type": "friend",
        "trust": 50, "affection": 50, "respect": 50, "hostility": 0,
    }
    after = {
        "relation_type": "friend",
        "trust": 52, "affection": 65, "respect": 50, "hostility": 0,
    }
    evt = record_edge_memory(
        store, turn=12, actor="主角", target="长公主",
        before=before, after=after,
    )
    assert evt is not None
    assert evt.type == "romance"
    key = memory_edge_key("主角", "长公主")
    assert len(store["edges"][key]) == 1


def test_apply_turn_writes_memory(world_pack, memory, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RELATIONSHIP_GRAPH_PATH", tmp_path / "relationship_graph.json")
    graph = init_graph_from_world(world_pack, memory, {"turn": 1}, persist=False)
    mem_store = empty_store()
    response = {"story": "主角公开维护长公主，朝堂震动。"}
    state = {"turn": 2}
    prev_options = ["公开维护|长公主信任+12"]
    graph, mem_store = apply_turn_relationship_updates(
        response, state, "A", memory, world_pack,
        prev_options=prev_options,
        relationship_graph=graph,
        relationship_memory=mem_store,
        persist=False,
    )
    events = mem_store["edges"].get("主角->长公主", [])
    assert len(events) >= 1
    assert events[-1]["turn"] == 2


def test_brain_recall_includes_events(world_pack, memory):
    store = empty_store()
    append_memory_event(store, RelationshipMemoryEvent(
        turn=47, actor="主角", target="长公主",
        type="support", summary="公开维护长公主",
        trust_delta=12,
    ))
    text = format_brain_memory({"长公主"}, store, "主角")
    assert "公开维护长公主" in text
    assert "T47" in text


def test_objective_recall(world_pack):
    store = empty_store()
    append_memory_event(store, RelationshipMemoryEvent(
        turn=33, actor="主角", target="长公主",
        type="cooperation", summary="共同调查刺客",
    ))
    graph = init_graph_from_world(world_pack, persist=False)
    session = {
        "turn": 40,
        "objectives": {
            "main": [{"id": "m1", "title": "获得长公主信任", "status": "active", "progress": 50}],
            "side": [],
        },
    }
    text = format_objective_memory(session, store, graph, world_pack)
    assert "共同调查刺客" in text
    assert "获得长公主信任" in text


def test_event_candidates_after_support_streak(world_pack):
    store = empty_store()
    for turn in (10, 12, 14):
        append_memory_event(store, RelationshipMemoryEvent(
            turn=turn, actor="主角", target="长公主",
            type="support", summary=f"第{turn}回合支持",
            trust_delta=6,
        ))
    graph = init_graph_from_world(world_pack, persist=False)
    session = {"turn": 15}
    candidates = build_relationship_event_candidates(store, graph, session, world_pack)
    assert candidates
    assert candidates[0]["target"] == "长公主"
    assert "深夜谈心" in candidates[0]["candidates"]


def test_prompt_context_respects_char_limit(world_pack, memory):
    store = empty_store()
    for i in range(20):
        append_memory_event(store, RelationshipMemoryEvent(
            turn=i, actor="主角", target="长公主",
            type="support", summary=f"事件{i}：" + "x" * 40,
        ))
    graph = init_graph_from_world(world_pack, memory, {"turn": 20}, persist=False)
    session = {"turn": 20}
    text = build_prompt_context(store, graph, session, world_pack, names={"长公主"})
    assert len(text) <= config.RELATIONSHIP_MEMORY_MAX_CHARS


def test_read_api_for_plot_conflict(world_pack):
    store = empty_store()
    append_memory_event(store, RelationshipMemoryEvent(
        turn=55, actor="主角", target="长公主",
        type="argument", summary="发生争执",
        trust_delta=-15,
    ))
    graph = init_graph_from_world(world_pack, persist=False)
    session = {"turn": 56}
    text = read_api_for_plot(session, world_pack, memory_store=store)
    assert "长公主" in text
    assert "修复" in text or "争执" in text
