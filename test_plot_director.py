"""Plot Director (V3.1) tests."""
from __future__ import annotations

from unittest.mock import patch

import config
from engine.plot_director import (
    apply_analysis_result,
    build_director_advice,
    default_plot_state,
    init_plot_state,
    maybe_analyze_plot,
)


def test_init_plot_state_from_world_pack(tmp_path, monkeypatch):
    plot_path = tmp_path / "plot_state.json"
    monkeypatch.setattr(config, "PLOT_STATE_PATH", plot_path)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    world_pack = {"world": {"main_goal": "找到失落王冠"}}
    state = init_plot_state(world_pack, persist=True)

    assert state["main_plot"]["name"] == "找到失落王冠"
    assert state["main_plot"]["progress"] == 0
    assert plot_path.exists()


def test_build_director_advice_stall():
    plot_state = default_plot_state("拯救王国")
    plot_state["last_progress_turn"] = 2
    session = {"turn": 15, "history": []}

    advice = build_director_advice(plot_state, session)
    assert "剧情导演建议" in advice
    assert "13" in advice or "未推进" in advice


def test_build_director_advice_empty_when_fresh():
    plot_state = default_plot_state("目标")
    session = {"turn": 3, "history": []}
    advice = build_director_advice(plot_state, session)
    assert advice == ""


def test_apply_analysis_result_progress_and_hooks():
    state = default_plot_state("主线")
    state["unresolved_hooks"] = [
        {"id": "a1", "title": "神秘玉佩", "kind": "foreshadow", "created_turn": 5, "status": "open"},
    ]
    analysis = {
        "progress_delta": 10,
        "stage": 2,
        "progress_made": True,
        "new_hooks": [{"title": "黑衣人身份", "kind": "mystery_character"}],
        "resolved_titles": ["神秘玉佩"],
        "summary": "主线小幅推进",
    }
    updated = apply_analysis_result(state, analysis, turn=10)

    assert updated["main_plot"]["progress"] == 10
    assert updated["main_plot"]["stage"] == 2
    assert updated["last_progress_turn"] == 10
    assert len(updated["unresolved_hooks"]) == 1
    assert updated["unresolved_hooks"][0]["title"] == "黑衣人身份"
    assert len(updated["resolved_hooks"]) == 1
    assert updated["resolved_hooks"][0]["title"] == "神秘玉佩"


def test_apply_analysis_result_caps_open_hooks(monkeypatch):
    monkeypatch.setattr(config, "PLOT_DIRECTOR_MAX_OPEN_HOOKS", 2)
    state = default_plot_state("主线")
    state["unresolved_hooks"] = [
        {"id": "1", "title": "A", "kind": "foreshadow", "created_turn": 1, "status": "open"},
        {"id": "2", "title": "B", "kind": "foreshadow", "created_turn": 2, "status": "open"},
    ]
    analysis = {
        "progress_delta": 0,
        "progress_made": False,
        "new_hooks": [{"title": "C", "kind": "foreshadow"}],
        "resolved_titles": [],
    }
    updated = apply_analysis_result(state, analysis, turn=5)
    assert len(updated["unresolved_hooks"]) == 2


def test_maybe_analyze_plot_calls_llm_on_interval():
    plot_state = default_plot_state("主线")
    session = {
        "turn": 5,
        "history": [
            {"turn": 4, "scene": "城", "story": "探索古城。", "choice": "A"},
            {"turn": 5, "scene": "城", "story": "发现线索。", "choice": "B"},
        ],
    }
    memory = {}
    world_pack = {"world": {"main_goal": "主线"}}

    fake_analysis = {
        "progress_delta": 5,
        "stage": 1,
        "progress_made": True,
        "new_hooks": [],
        "resolved_titles": [],
        "summary": "ok",
    }
    with patch("engine.plot_director.analyze_plot_with_llm", return_value=fake_analysis):
        updated = maybe_analyze_plot(plot_state, session, memory, world_pack)

    assert updated["main_plot"]["progress"] == 5
    assert updated["last_progress_turn"] == 5
    assert updated["last_analysis_turn"] == 5


def test_maybe_analyze_plot_skips_off_interval():
    plot_state = default_plot_state("主线")
    session = {"turn": 3, "history": []}
    with patch("engine.plot_director.analyze_plot_with_llm") as mock_llm:
        result = maybe_analyze_plot(plot_state, session, {}, {"world": {}})
    assert result is plot_state
    mock_llm.assert_not_called()


def test_50_turn_mock_progress_at_least_once():
    """Acceptance: over 50 turns with periodic analysis, progress advances at least once."""
    state = default_plot_state("拯救世界")
    session = {"turn": 0, "history": []}

    def _fake_analysis(_plot, sess, _world):
        turn = int(sess.get("turn", 0))
        return {
            "progress_delta": 3,
            "stage": min(5, 1 + turn // 20),
            "progress_made": True,
            "new_hooks": [],
            "resolved_titles": [],
            "summary": f"T{turn}",
        }

    with patch("engine.plot_director.analyze_plot_with_llm", side_effect=_fake_analysis):
        for t in range(1, 51):
            session["turn"] = t
            session["history"].append({
                "turn": t,
                "scene": "场景",
                "story": f"第{t}轮剧情",
                "choice": "A",
            })
            if t % config.PLOT_DIRECTOR_ANALYSIS_INTERVAL == 0:
                state = maybe_analyze_plot(state, session, {}, {"world": {"main_goal": "拯救世界"}})

    assert state["last_progress_turn"] > 0
    assert state["main_plot"]["progress"] > 0
    assert len(state["unresolved_hooks"]) <= config.PLOT_DIRECTOR_MAX_OPEN_HOOKS
