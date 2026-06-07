"""Objective System (V3.2) tests."""
from __future__ import annotations

from unittest.mock import patch

import config
from engine.objective_system import (
    MAIN_OBJECTIVE_ID,
    apply_objective_updates,
    apply_rule_progress,
    build_objectives_context,
    dashboard_payload,
    default_objectives,
    ensure_objectives,
    process_turn_objectives,
    sync_main_objective_progress,
    sync_plot_from_main_objective,
    visible_for_game,
)
from engine.plot_director import default_plot_state


def test_default_objectives_from_main_goal():
    objs = default_objectives("调查灭门案")
    assert len(objs["main"]) == 1
    assert objs["main"][0]["id"] == MAIN_OBJECTIVE_ID
    assert objs["main"][0]["title"] == "调查灭门案"
    assert objs["main"][0]["status"] == "active"
    assert objs["side"] == []


def test_ensure_objectives_lazy_init():
    session = {"turn": 5, "status": "BUILD"}
    world_pack = {"world": {"main_goal": "拯救王国"}}
    plot_state = default_plot_state("拯救王国")
    plot_state["main_plot"]["progress"] = 42

    ensure_objectives(session, world_pack, plot_state)

    assert "objectives" in session
    assert session["objectives"]["main"][0]["title"] == "拯救王国"
    assert session["objectives"]["main"][0]["progress"] == 42


def test_apply_objective_updates_side_and_status():
    session = {
        "turn": 3,
        "objectives": default_objectives("主线"),
    }
    session["objectives"]["side"] = [{
        "id": "side_001",
        "title": "参加诗会",
        "progress": 20,
        "status": "active",
    }]
    updates = [
        {"id": "side_001", "progress_delta": 15},
        {"action": "add", "scope": "side", "title": "寻找证人", "progress": 0, "status": "active"},
        {"id": "side_002", "status": "completed", "title": "dummy"},
    ]
    apply_objective_updates(session, updates, turn=3)

    side = {o["id"]: o for o in session["objectives"]["side"]}
    assert side["side_001"]["progress"] == 35
    assert any(o["title"] == "寻找证人" for o in session["objectives"]["side"])


def test_apply_objective_updates_main_syncs_plot_state(tmp_path, monkeypatch):
    plot_path = tmp_path / "plot_state.json"
    monkeypatch.setattr(config, "PLOT_STATE_PATH", plot_path)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    from engine.plot_director import init_plot_state, load_plot_state

    init_plot_state({"world": {"main_goal": "主线"}}, persist=True)
    session = {"turn": 5, "objectives": default_objectives("主线")}

    apply_objective_updates(session, [{"id": MAIN_OBJECTIVE_ID, "progress_delta": 25}], turn=5)

    assert session["objectives"]["main"][0]["progress"] == 25
    plot_state = load_plot_state()
    assert plot_state["main_plot"]["progress"] == 25


def test_sync_main_objective_progress_from_plot():
    session = {"objectives": default_objectives("主线")}
    plot_state = default_plot_state("主线")
    plot_state["main_plot"]["progress"] = 60

    sync_main_objective_progress(session, plot_state)

    assert session["objectives"]["main"][0]["progress"] == 60


def test_sync_plot_from_main_objective():
    session = {"objectives": default_objectives("主线")}
    session["objectives"]["main"][0]["progress"] = 75
    plot_state = default_plot_state("主线")

    updated = sync_plot_from_main_objective(session, plot_state)

    assert updated["main_plot"]["progress"] == 75


def test_apply_rule_progress_on_status_advance():
    session = {
        "turn": 4,
        "status": "TENSION",
        "objectives": default_objectives("主线"),
    }
    session["objectives"]["side"] = [{
        "id": "side_001",
        "title": "支线",
        "progress": 10,
        "status": "active",
    }]

    apply_rule_progress(session, "BUILD", "TENSION", turn=4)

    assert session["objectives"]["side"][0]["progress"] == 10 + config.OBJECTIVE_RULE_PROGRESS_DELTA


def test_build_objectives_context_filters_hidden():
    session = {
        "turn": 2,
        "objectives": {
            "main": [{"id": "main_001", "title": "主线任务", "progress": 30, "status": "active"}],
            "side": [
                {"id": "s1", "title": "可见支线", "progress": 5, "status": "active"},
                {"id": "s2", "title": "隐藏支线", "progress": 0, "status": "hidden"},
            ],
        },
    }
    ctx = build_objectives_context(session)
    assert "主线任务" in ctx
    assert "可见支线" in ctx
    assert "隐藏支线" not in ctx


def test_visible_for_game_limits_side():
    session = {
        "objectives": {
            "main": [{"id": "m1", "title": "主线", "progress": 50, "status": "active"}],
            "side": [
                {"id": f"s{i}", "title": f"支线{i}", "progress": i, "status": "active"}
                for i in range(5)
            ],
        },
    }
    visible = visible_for_game(session)
    assert len(visible["main"]) == 1
    assert len(visible["side"]) == 3
    assert visible["side_extra"] == 2


def test_dashboard_payload_buckets():
    session = {
        "objectives": {
            "main": [{"id": "m1", "title": "主线", "progress": 80, "status": "active"}],
            "side": [
                {"id": "s1", "title": "活跃", "progress": 10, "status": "active"},
                {"id": "s2", "title": "完成", "progress": 100, "status": "completed"},
                {"id": "s3", "title": "失败", "progress": 0, "status": "failed"},
                {"id": "s4", "title": "隐藏", "progress": 0, "status": "hidden"},
            ],
        },
    }
    payload = dashboard_payload(session)
    assert len(payload["main"]) == 1
    assert len(payload["side"]) == 1
    assert len(payload["completed"]) == 1
    assert len(payload["failed"]) == 1
    assert len(payload["hidden"]) == 1


def test_process_turn_objectives_integration(tmp_path, monkeypatch):
    plot_path = tmp_path / "plot_state.json"
    world_path = tmp_path / "world_pack.yaml"
    monkeypatch.setattr(config, "PLOT_STATE_PATH", plot_path)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "WORLD_PACK_PATH", world_path)

    from engine import io_utils
    from engine.plot_director import init_plot_state

    io_utils.write_yaml(world_path, {"world": {"main_goal": "找到王冠"}})
    init_plot_state({"world": {"main_goal": "找到王冠"}}, persist=True)

    session = {"turn": 1, "status": "BUILD"}
    world_pack = {"world": {"main_goal": "找到王冠"}}
    response = {
        "objective_updates": [
            {"action": "add", "scope": "side", "title": "打听消息", "progress": 0, "status": "active"},
        ],
    }

    process_turn_objectives(session, response, "SETUP", world_pack)

    assert session["objectives"]["main"][0]["title"] == "找到王冠"
    assert any(o["title"] == "打听消息" for o in session["objectives"]["side"])


def test_build_objectives_disabled(monkeypatch):
    monkeypatch.setattr(config, "OBJECTIVE_SYSTEM_ENABLED", False)
    session = {"turn": 5, "objectives": default_objectives("x")}
    assert build_objectives_context(session) == ""
