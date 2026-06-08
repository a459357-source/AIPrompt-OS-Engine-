"""V5.2 Event Director Engine — Phase A tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import config
from engine.event_director import (
    DirectorPlan,
    build_director_plans,
    build_and_record_director_plan,
    empty_event_history,
    ensure_event_catalog,
    format_director_plan,
    is_on_cooldown,
    load_event_history,
    record_event_history,
    save_event_history,
)
from engine.relationship_core import RelationshipEdge, ensure_graph, set_edge
from engine.relationship_dynamics import empty_dynamics_store, set_dynamics, RelationshipDynamicsState
from engine.relationship_memory import RelationshipMemoryEvent, append_memory_event
from engine.relationship_recall import ensure_memory_store


@pytest.fixture
def catalog():
    return ensure_event_catalog()


@pytest.fixture
def world_pack():
    return {
        "world": {
            "main_goal": "调查灭门案",
            "player": {"name": "主角"},
            "characters": [
                {"name": "主角", "is_main": True, "role": "主角"},
                {"name": "长公主", "role": "贵族"},
            ],
        },
    }


@pytest.fixture
def session(world_pack):
    return {
        "turn": 10,
        "objectives": {
            "main": [{"id": "main_001", "title": "调查灭门案", "progress": 80, "status": "active"}],
            "side": [],
        },
    }


def test_director_plan_dataclass():
    plan = DirectorPlan(
        event_id="midnight_talk",
        category="relationship",
        priority=85,
        reason="trust_over_80",
        participants=["主角", "长公主"],
        tags=["bond", "private"],
    )
    d = plan.to_dict()
    assert d["event_id"] == "midnight_talk"
    assert d["priority"] == 85


def test_event_catalog_exists(catalog):
    events = catalog.get("events") or {}
    for event_id in (
        "midnight_talk", "gift_exchange", "confession", "jealousy",
        "reconciliation", "romance_triangle",
        "clue_found", "breakthrough", "reveal_truth",
        "rebellion", "war", "assassination", "political_pressure",
        "act_transition", "boss_intro", "major_twist",
    ):
        assert event_id in events, f"missing catalog event {event_id}"


def test_relationship_triggers_director(world_pack, session, catalog):
    session = dict(session)
    session["objectives"] = {
        "main": [{"id": "main_001", "title": "调查灭门案", "progress": 10, "status": "active"}],
        "side": [],
    }
    graph = ensure_graph(world_pack, session=session)
    set_edge(graph, RelationshipEdge(source="主角", target="长公主", trust=85, affection=70))
    dyn = empty_dynamics_store()
    set_dynamics(dyn, "主角", "长公主", RelationshipDynamicsState(momentum=22, bond_level=4))
    plot_state = {"main_plot": {"name": "调查灭门案", "progress": 10, "stage": 1}, "last_progress_turn": 9}

    plans = build_director_plans(
        session, world_pack,
        graph=graph,
        relationship_dynamics=dyn,
        relationship_memory=ensure_memory_store(None),
        plot_state=plot_state,
        memory={"characters": {}, "factions": {}},
        catalog=catalog,
        event_history=empty_event_history(),
    )
    ids = {p.event_id for p in plans}
    assert "midnight_talk" in ids or "gift_exchange" in ids


def test_objective_triggers_director(world_pack, session, catalog):
    session = dict(session)
    session["objectives"] = {
        "main": [{"id": "main_001", "title": "调查灭门案", "progress": 80, "status": "active"}],
        "side": [],
    }
    plot_state = {"main_plot": {"name": "调查灭门案", "progress": 80, "stage": 2}, "last_progress_turn": 9}
    plans = build_director_plans(
        session, world_pack,
        plot_state=plot_state,
        memory={"characters": {}, "factions": {}},
        catalog=catalog,
        event_history=empty_event_history(),
    )
    assert any(p.event_id == "reveal_truth" for p in plans)


def test_plot_triggers_director(world_pack, session, catalog):
    plot_state = {
        "main_plot": {"name": "调查灭门案", "progress": 76, "stage": 2},
        "unresolved_hooks": [{"kind": "mystery_event"}] * 5,
        "last_progress_turn": 1,
    }
    plans = build_director_plans(
        session, world_pack,
        plot_state=plot_state,
        catalog=catalog,
        event_history=empty_event_history(),
    )
    ids = {p.event_id for p in plans}
    assert "major_twist" in ids or "boss_intro" in ids or "act_transition" in ids


def test_world_triggers_director(world_pack, session, catalog):
    memory = {
        "factions": {
            "北境军": {
                "type": "military",
                "goals": ["夺取边境"],
                "relation_to_player": "hostile",
                "influence": 90,
            },
            "王庭": {
                "type": "government",
                "goals": ["提高税率"],
                "relation_to_player": "neutral",
                "influence": 80,
            },
        },
        "faction_attitudes": {
            "北境军": {"王庭": {"attitude": 0.1}},
            "王庭": {"北境军": {"attitude": 0.15}},
        },
    }
    plans = build_director_plans(
        session, world_pack,
        memory=memory,
        catalog=catalog,
        event_history=empty_event_history(),
    )
    ids = {p.event_id for p in plans}
    assert ids & {"war", "rebellion", "political_pressure"}


def test_cooldown_and_history(tmp_path, monkeypatch, catalog):
    history_path = tmp_path / "event_history.json"
    monkeypatch.setattr(config, "EVENT_HISTORY_PATH", history_path)

    history = empty_event_history()
    plan = DirectorPlan(
        event_id="confession",
        category="relationship",
        priority=80,
        reason="romance",
        participants=["主角", "长公主"],
        tags=["bond"],
    )
    record_event_history(history, [plan], turn=10, persist=True)
    loaded = load_event_history()
    assert len(loaded["records"]) == 1
    assert is_on_cooldown("confession", loaded, current_turn=15, catalog=catalog)
    assert not is_on_cooldown("confession", loaded, current_turn=31, catalog=catalog)


def test_format_director_plan_budget(catalog):
    plans = [
        DirectorPlan("midnight_talk", "relationship", 95, "trust_over_80", ["主角", "长公主"], ["bond"]),
        DirectorPlan("jealousy", "relationship", 87, "conflict", ["主角", "长公主"], ["conflict"]),
    ]
    text = format_director_plan(plans, catalog)
    assert "深夜谈心" in text
    assert "情敌冲突" in text
    assert len(text) <= config.EVENT_DIRECTOR_PLAN_MAX_CHARS
    est_tokens = int(len(text) * 0.6)
    assert est_tokens <= config.EVENT_DIRECTOR_PLAN_MAX_TOKENS


def test_builder_injects_director_plan(tmp_path, monkeypatch, world_pack, session):
    from engine.builder import build_prompt

    monkeypatch.setattr(config, "EVENT_DIRECTOR_ENABLED", True)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "SESSION_STATE_PATH", tmp_path / "session_state.yaml")
    monkeypatch.setattr(config, "WORLD_PACK_PATH", tmp_path / "world_pack.yaml")
    monkeypatch.setattr(config, "ENGINE_CONFIG_PATH", tmp_path / "engine.yaml")
    monkeypatch.setattr(config, "PROMPT_TEMPLATE_PATH", Path(__file__).resolve().parent / "prompt_template.yaml")
    monkeypatch.setattr(config, "MEMORY_PATH", tmp_path / "memory.json")
    monkeypatch.setattr(config, "STORY_GRAPH_PATH", tmp_path / "story_graph.json")
    monkeypatch.setattr(config, "EVENT_HISTORY_PATH", tmp_path / "event_history.json")
    monkeypatch.setattr(config, "EVENT_CATALOG_PATH", tmp_path / "event_catalog.json")
    monkeypatch.setattr(config, "RELATIONSHIP_GRAPH_PATH", tmp_path / "relationship_graph.json")
    monkeypatch.setattr(config, "RELATIONSHIP_MEMORY_PATH", tmp_path / "relationship_memory.json")
    monkeypatch.setattr(config, "RELATIONSHIP_DYNAMICS_PATH", tmp_path / "relationship_dynamics.json")
    monkeypatch.setattr(config, "PLOT_STATE_PATH", tmp_path / "plot_state.json")
    monkeypatch.setattr(config, "CHAPTER_PATH", tmp_path / "chapter.md")

    import yaml
    from engine import io_utils

    (tmp_path / "session_state.yaml").write_text(
        yaml.dump(session, allow_unicode=True), encoding="utf-8",
    )
    (tmp_path / "world_pack.yaml").write_text(
        yaml.dump(world_pack, allow_unicode=True), encoding="utf-8",
    )
    (tmp_path / "engine.yaml").write_text("rules: []\n", encoding="utf-8")
    io_utils.write_json(tmp_path / "memory.json", {"characters": {}, "factions": {}})
    io_utils.write_json(tmp_path / "story_graph.json", {"nodes": [], "edges": []})
    shutil_catalog = ensure_event_catalog()
    io_utils.write_json(tmp_path / "event_catalog.json", shutil_catalog)

    _, user = build_prompt()
    assert "Director Plan" in user or "事件导演" in user


def test_no_dual_director_implementations():
    root = Path(__file__).resolve().parent / "engine"
    forbidden = ("StoryEventDirector", "AdultEventDirector", "StoryTimeline", "AdultTimeline")
    for py in root.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        for name in forbidden:
            assert name not in text, f"{name} found in {py.name}"


def test_adr001_no_mode_branch_in_event_director():
    path = Path(__file__).resolve().parent / "engine" / "event_director.py"
    text = path.read_text(encoding="utf-8")
    assert "adult_mode" not in text
    assert "experience_mode" not in text
    assert "StoryEventDirector" not in text
    assert "AdultEventDirector" not in text


def test_top3_limit(world_pack, session, catalog):
    graph = ensure_graph(world_pack, session=session)
    set_edge(graph, RelationshipEdge(source="主角", target="长公主", trust=90, affection=80))
    dyn = empty_dynamics_store()
    set_dynamics(dyn, "主角", "长公主", RelationshipDynamicsState(momentum=25, bond_level=5, conflict_level=3))
    mem = ensure_memory_store(None)
    for i in range(3):
        append_memory_event(mem, RelationshipMemoryEvent(
            turn=10 + i, actor="主角", target="长公主", type="conflict", summary="争执",
        ))

    plans = build_director_plans(
        session, world_pack,
        graph=graph,
        relationship_dynamics=dyn,
        relationship_memory=mem,
        catalog=catalog,
        event_history=empty_event_history(),
    )
    assert len(plans) <= config.EVENT_DIRECTOR_MAX_PLANS
