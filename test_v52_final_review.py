"""V5.2 Final Review — save consistency and ADR audit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import config
from engine.director_runtime import reset_director_state
from engine.director_state import ACTIVE, DirectorEventState, get_current_event, load_director_state, save_director_state
from engine.save_manager import load as load_save, save as save_slot


@pytest.fixture
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "SAVES_DIR", tmp_path / "saves")
    monkeypatch.setattr(config, "SESSION_STATE_PATH", tmp_path / "session_state.yaml")
    monkeypatch.setattr(config, "MEMORY_PATH", tmp_path / "memory.json")
    monkeypatch.setattr(config, "STORY_GRAPH_PATH", tmp_path / "story_graph.json")
    monkeypatch.setattr(config, "DIRECTOR_STATE_PATH", tmp_path / "director_state.json")
    monkeypatch.setattr(config, "EVENT_HISTORY_PATH", tmp_path / "event_history.json")
    monkeypatch.setattr(config, "EVENT_CATALOG_PATH", tmp_path / "event_catalog.json")
    monkeypatch.setattr(config, "RELATIONSHIP_GRAPH_PATH", tmp_path / "relationship_graph.json")
    monkeypatch.setattr(config, "RELATIONSHIP_MEMORY_PATH", tmp_path / "relationship_memory.json")
    monkeypatch.setattr(config, "RELATIONSHIP_DYNAMICS_PATH", tmp_path / "relationship_dynamics.json")
    monkeypatch.setattr(config, "PLOT_STATE_PATH", tmp_path / "plot_state.json")
    monkeypatch.setattr(config, "CANDIDATE_NPCS_PATH", tmp_path / "candidate_npcs.json")
    monkeypatch.setattr(config, "CHAPTER_PATH", tmp_path / "chapter.md")
    monkeypatch.setattr(config, "WORLD_PACK_PATH", tmp_path / "world_pack.yaml")
    import shutil
    from config import EVENT_CATALOG_DEFAULT_PATH
    if EVENT_CATALOG_DEFAULT_PATH.exists():
        shutil.copy2(EVENT_CATALOG_DEFAULT_PATH, tmp_path / "event_catalog.json")
    return tmp_path


def _write_minimal_runtime(tmp_path: Path) -> None:
    import yaml
    from engine import io_utils

    (tmp_path / "session_state.yaml").write_text(
        yaml.dump({"turn": 12, "status": "BUILD", "scene": "测试", "characters": {}}, allow_unicode=True),
        encoding="utf-8",
    )
    (tmp_path / "world_pack.yaml").write_text(
        yaml.dump({"world": {"characters": [{"name": "主角", "is_main": True}]}}, allow_unicode=True),
        encoding="utf-8",
    )
    io_utils.write_json(tmp_path / "memory.json", {"characters": {}, "factions": {}})
    io_utils.write_json(tmp_path / "story_graph.json", {"nodes": [], "edges": []})
    io_utils.write_json(tmp_path / "relationship_graph.json", {"version": 1, "nodes": {}, "edges": {}, "events": [], "pending_events": []})
    io_utils.write_json(tmp_path / "relationship_memory.json", {"version": 1, "edges": {}})
    io_utils.write_json(tmp_path / "relationship_dynamics.json", {"version": 1, "edges": {}, "triangles": []})
    io_utils.write_json(tmp_path / "plot_state.json", {"main_plot": {"progress": 40, "stage": 1, "name": "主线"}, "unresolved_hooks": []})
    io_utils.write_json(tmp_path / "candidate_npcs.json", {})


def test_save_load_director_state_roundtrip(isolated_data):
    _write_minimal_runtime(isolated_data)
    inst = DirectorEventState(
        instance_id="save1",
        event_id="midnight_talk",
        category="relationship",
        state=ACTIVE,
        priority=85,
        reason="trust_over_80",
        participants=["主角", "长公主"],
        started_turn=10,
        last_turn=11,
        turns_active=2,
    )
    save_director_state({"version": 2, "current_event": inst.to_dict(), "pending": [], "lifecycle": []})

    result = save_slot("slot1")
    assert result is not None

    reset_director_state()
    assert get_current_event(load_director_state()) is None

    loaded = load_save("slot1")
    assert loaded is not None
    current = get_current_event(load_director_state())
    assert current is not None
    assert current.event_id == "midnight_talk"
    assert current.state == ACTIVE


def test_reset_clears_director_state(isolated_data):
    _write_minimal_runtime(isolated_data)
    inst = DirectorEventState(
        instance_id="r1",
        event_id="war",
        category="world",
        state=ACTIVE,
        priority=70,
        reason="test",
    )
    save_director_state({"version": 2, "current_event": inst.to_dict(), "pending": [], "lifecycle": [{"event_id": "war", "state": "COOLDOWN", "last_turn": 5}]})
    reset_director_state()
    state = load_director_state()
    assert get_current_event(state) is None
    assert state["lifecycle"] == []


def test_adr001_no_dual_director_stack():
    engine = Path(__file__).resolve().parent / "engine"
    forbidden = (
        "StoryEventDirector", "AdultEventDirector", "StoryDirector", "AdultDirector",
        "StoryTimeline", "AdultTimeline",
    )
    targets = (
        "event_director.py", "director_state.py", "director_runtime.py",
    )
    for name in targets:
        text = (engine / name).read_text(encoding="utf-8")
        for bad in forbidden:
            assert bad not in text, f"{bad} in {name}"
        assert "adult_mode" not in text
        assert "experience_mode" not in text
