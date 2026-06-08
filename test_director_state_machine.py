"""V5.2 Director State Machine — Phase B tests."""

from __future__ import annotations

from pathlib import Path

import pytest

import config
from engine.director_runtime import (
    advance_director_after_turn,
    prepare_director_prompt,
    reset_director_state,
)
from engine.director_state import (
    ACTIVE,
    COOLDOWN,
    FAILED,
    PENDING,
    RESOLVED,
    DirectorEventState,
    empty_director_state,
    get_current_event,
    load_director_state,
    save_director_state,
    transition_event,
)
from engine.event_director import DirectorPlan, empty_event_history, ensure_event_catalog


@pytest.fixture
def catalog():
    return ensure_event_catalog()


@pytest.fixture
def world_pack():
    return {
        "world": {
            "main_goal": "调查灭门案",
            "characters": [
                {"name": "主角", "is_main": True},
                {"name": "长公主", "role": "贵族"},
            ],
        },
    }


@pytest.fixture
def session():
    return {
        "turn": 5,
        "objectives": {
            "main": [{"id": "main_001", "title": "调查灭门案", "progress": 10, "status": "active"}],
            "side": [],
        },
    }


@pytest.fixture
def director_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DIRECTOR_STATE_PATH", tmp_path / "director_state.json")
    monkeypatch.setattr(config, "EVENT_HISTORY_PATH", tmp_path / "event_history.json")
    monkeypatch.setattr(config, "EVENT_CATALOG_PATH", tmp_path / "event_catalog.json")
    import shutil
    from config import EVENT_CATALOG_DEFAULT_PATH
    if EVENT_CATALOG_DEFAULT_PATH.exists():
        shutil.copy2(EVENT_CATALOG_DEFAULT_PATH, tmp_path / "event_catalog.json")
    monkeypatch.setattr(config, "EVENT_DIRECTOR_ENABLED", True)
    monkeypatch.setattr(config, "DIRECTOR_STATE_MACHINE_ENABLED", True)
    return tmp_path


def test_director_event_state_constants():
    assert PENDING == "PENDING"
    assert ACTIVE == "ACTIVE"
    assert RESOLVED == "RESOLVED"
    assert FAILED == "FAILED"
    assert COOLDOWN == "COOLDOWN"


def test_director_state_persistence(director_paths):
    inst = DirectorEventState(
        instance_id="abc123",
        event_id="midnight_talk",
        category="relationship",
        state=ACTIVE,
        priority=85,
        reason="trust_over_80",
        participants=["主角", "长公主"],
        started_turn=5,
        last_turn=5,
        turns_active=1,
    )
    state = empty_director_state()
    state["current_event"] = inst.to_dict()
    save_director_state(state)
    loaded = load_director_state()
    current = get_current_event(loaded)
    assert current is not None
    assert current.event_id == "midnight_talk"
    assert current.state == ACTIVE


def test_transition_event_lifecycle():
    inst = DirectorEventState(
        instance_id="x1",
        event_id="confession",
        category="relationship",
        state=ACTIVE,
        priority=80,
        reason="romance",
        turns_active=2,
        started_turn=3,
        last_turn=4,
    )
    resolved = transition_event(inst, RESOLVED, turn=5)
    assert resolved.state == RESOLVED
    cooled = transition_event(resolved, COOLDOWN, turn=5)
    assert cooled.state == COOLDOWN


def test_prepare_promotes_active_event(director_paths, world_pack, session, catalog):
    from engine.relationship_core import RelationshipEdge, ensure_graph, set_edge
    from engine.relationship_dynamics import RelationshipDynamicsState, empty_dynamics_store, set_dynamics

    graph = ensure_graph(world_pack, session=session)
    set_edge(graph, RelationshipEdge(source="主角", target="长公主", trust=85, affection=70))
    dyn = empty_dynamics_store()
    set_dynamics(dyn, "主角", "长公主", RelationshipDynamicsState(momentum=22, bond_level=4))
    plot_state = {"main_plot": {"progress": 10, "stage": 1}, "last_progress_turn": 4}

    text = prepare_director_prompt(
        session,
        world_pack,
        memory={"factions": {}},
        graph=graph,
        relationship_dynamics=dyn,
        plot_state=plot_state,
    )
    assert "ACTIVE" in text
    current = get_current_event(load_director_state())
    assert current is not None
    assert current.state == ACTIVE


def test_advance_resolves_on_story_signal(director_paths, session, catalog):
    inst = DirectorEventState(
        instance_id="r1",
        event_id="midnight_talk",
        category="relationship",
        state=ACTIVE,
        priority=85,
        reason="trust_over_80",
        participants=["主角", "长公主"],
        started_turn=5,
        last_turn=5,
        turns_active=1,
    )
    state = empty_director_state()
    state["current_event"] = inst.to_dict()
    save_director_state(state)

    session = {"turn": 6}
    advance_director_after_turn(
        session,
        "夜色深沉，长公主与主角深夜谈心，彼此敞开心扉，完成了一次真正的对话。",
    )
    loaded = load_director_state()
    assert get_current_event(loaded) is None
    assert loaded["lifecycle"][-1]["state"] == COOLDOWN


def test_advance_fails_on_timeout(director_paths, session):
    inst = DirectorEventState(
        instance_id="f1",
        event_id="gift_exchange",
        category="relationship",
        state=ACTIVE,
        priority=75,
        reason="momentum",
        started_turn=3,
        last_turn=5,
        turns_active=config.DIRECTOR_EVENT_MAX_ACTIVE_TURNS,
    )
    state = empty_director_state()
    state["current_event"] = inst.to_dict()
    save_director_state(state)

    advance_director_after_turn(session, "无关的日常叙事。")
    loaded = load_director_state()
    assert get_current_event(loaded) is None
    assert loaded["lifecycle"][-1]["event_id"] == "gift_exchange"


def test_reset_director_state(director_paths):
    state = empty_director_state()
    state["current_event"] = DirectorEventState(
        instance_id="z",
        event_id="war",
        category="world",
        state=ACTIVE,
        priority=70,
        reason="test",
    ).to_dict()
    save_director_state(state)
    reset_director_state()
    loaded = load_director_state()
    assert get_current_event(loaded) is None
    assert loaded["pending"] == []


def test_no_mode_branch_in_director_modules():
    for name in ("director_state.py", "director_runtime.py"):
        path = Path(__file__).resolve().parent / "engine" / name
        text = path.read_text(encoding="utf-8")
        assert "adult_mode" not in text
        assert "experience_mode" not in text
        assert "StoryEventDirector" not in text
        assert "AdultEventDirector" not in text


def test_prepare_fallback_when_state_machine_disabled(
    director_paths, world_pack, session, monkeypatch,
):
    monkeypatch.setattr(config, "DIRECTOR_STATE_MACHINE_ENABLED", False)
    text = prepare_director_prompt(
        session,
        world_pack,
        memory={"factions": {}},
        plot_state={"main_plot": {"progress": 80, "stage": 2}, "last_progress_turn": 4},
    )
    assert text == "" or "Director Plan" in text or "事件导演" in text
