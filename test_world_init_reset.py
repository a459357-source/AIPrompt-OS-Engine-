"""Tests for world_init / reset plot_state and objectives boundary consistency."""
import json

import pytest

import config
from engine import io_utils
from engine.objective_system import ensure_objectives, sync_main_objective_progress
from engine.plot_director import load_plot_state, save_plot_state


@pytest.fixture
def runtime_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "SESSION_STATE_PATH", tmp_path / "session_state.yaml")
    monkeypatch.setattr(config, "MEMORY_PATH", tmp_path / "memory.json")
    monkeypatch.setattr(config, "STORY_GRAPH_PATH", tmp_path / "story_graph.json")
    monkeypatch.setattr(config, "PLOT_STATE_PATH", tmp_path / "plot_state.json")
    monkeypatch.setattr(config, "WORLD_INIT_PATH", tmp_path / "world_init.json")
    monkeypatch.setattr(config, "WORLD_PACK_PATH", tmp_path / "world_pack.yaml")
    monkeypatch.setattr(config, "CHAPTER_PATH", tmp_path / "chapter.md")
    return tmp_path


def _factory_snapshot(main_goal: str = "拯救王国") -> dict:
    from engine.objective_system import default_objectives
    from engine.plot_director import default_plot_state

    state = {
        "scene": "测试场景",
        "status": "SETUP",
        "turn": 0,
        "characters": {},
        "history": [],
        "objectives": default_objectives(main_goal),
    }
    graph = {"nodes": {"0": {"turn": 0}}, "current_node": "0", "edges": []}
    memory = {"characters": {}, "world_flags": [], "global_trust": 0.5}
    plot_state = default_plot_state(main_goal)
    return {"state": state, "graph": graph, "memory": memory, "plot_state": plot_state}


def test_world_init_includes_plot_state(runtime_paths):
    snapshot = _factory_snapshot("找到王冠")
    io_utils.write_json(config.WORLD_INIT_PATH, snapshot)
    loaded = io_utils.read_json(config.WORLD_INIT_PATH)
    assert "plot_state" in loaded
    assert loaded["plot_state"]["main_plot"]["name"] == "找到王冠"


def test_reset_restores_plot_state_and_objectives(runtime_paths):
    snapshot = _factory_snapshot("主线目标")
    io_utils.write_json(config.WORLD_INIT_PATH, snapshot)
    io_utils.write_yaml(config.WORLD_PACK_PATH, {"world": {"main_goal": "主线目标"}})

    # Simulate drift: mutate runtime plot + objectives
    drift_plot = json.loads(json.dumps(snapshot["plot_state"]))
    drift_plot["main_plot"]["progress"] = 77
    save_plot_state(drift_plot)

    drift_state = dict(snapshot["state"])
    drift_state["objectives"] = json.loads(json.dumps(snapshot["state"]["objectives"]))
    drift_state["objectives"]["main"][0]["progress"] = 99
    io_utils.write_yaml(config.SESSION_STATE_PATH, drift_state)

    # Reset logic (mirror ui/routes/game.py)
    from engine.state_store import commit_bundle

    init = io_utils.read_json(config.WORLD_INIT_PATH)
    state = init["state"]
    commit_bundle(state, init["memory"], init["graph"], chapter="")
    plot_state = init["plot_state"]
    save_plot_state(plot_state, persist=True)
    world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
    ensure_objectives(state, world_pack, plot_state)
    sync_main_objective_progress(state, plot_state)
    io_utils.write_yaml(config.SESSION_STATE_PATH, state)

    restored_plot = load_plot_state()
    assert restored_plot["main_plot"]["progress"] == 0
    session = io_utils.read_yaml(config.SESSION_STATE_PATH)
    assert session["objectives"]["main"][0]["progress"] == 0


def test_reset_fallback_init_plot_state_without_plot_in_world_init(runtime_paths):
    """Legacy world_init without plot_state falls back to init_plot_state."""
    from engine.plot_director import init_plot_state

    snapshot = _factory_snapshot("旧档目标")
    del snapshot["plot_state"]
    io_utils.write_json(config.WORLD_INIT_PATH, snapshot)
    io_utils.write_yaml(config.WORLD_PACK_PATH, {"world": {"main_goal": "旧档目标"}})

    init = io_utils.read_json(config.WORLD_INIT_PATH)
    world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
    plot_state = init.get("plot_state")
    if not (isinstance(plot_state, dict) and plot_state.get("main_plot")):
        plot_state = init_plot_state(world_pack)

    assert plot_state["main_plot"]["name"] == "旧档目标"
