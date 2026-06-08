"""Unit tests for prompt regression metrics (no API)."""
from __future__ import annotations

import copy

from scripts.prompt_regression.metrics import (
    aggregate_turn_records,
    compare_architectures,
    context_usage_hit,
    detect_brain_conflict,
    evaluate_pass_fail,
    event_progress_delta,
    objective_progress_delta,
    option_repeat_rate,
    relationship_activity_delta,
    snapshot_runtime,
)


def _scenario():
    return {
        "main_goal": "通过宗门试炼",
        "world_pack": {
            "world": {
                "main_goal": "通过宗门试炼",
                "setting": "青云宗试炼",
                "title": "青云试炼",
                "locations": [{"name": "试炼峰"}],
                "characters": [
                    {"name": "林澈", "is_main": True},
                    {
                        "name": "苏清雪",
                        "is_main": False,
                        "personality": {
                            "desire": "公正",
                            "fear": "失败",
                            "taboo": "徇私放水",
                            "secret": "",
                            "values": [],
                        },
                    },
                ],
            }
        },
    }


def test_objective_progress_delta():
    before = {"main_objective_progress": 10, "main_plot_progress": 0}
    after = {"main_objective_progress": 15, "main_plot_progress": 0}
    assert objective_progress_delta(before, after) is True
    assert objective_progress_delta(after, after) is False


def test_event_progress_delta_world_events():
    before = {"world_events_count": 1, "unresolved_hooks": 2, "world_flags": [], "force_event_pending": False}
    after = {"world_events_count": 2, "unresolved_hooks": 2, "world_flags": [], "force_event_pending": False}
    assert event_progress_delta(before, after) is True


def test_relationship_activity_delta_from_memory():
    before = {"memory_metrics": {"苏清雪": {"affection": 0.2, "trust": 0.3}}}
    after = {"memory_metrics": {"苏清雪": {"affection": 0.25, "trust": 0.3}}}
    d = relationship_activity_delta(before, after, [])
    assert d == 0.05


def test_context_usage_hit():
    sc = _scenario()
    assert context_usage_hit("林澈踏上试炼峰", sc, []) is True
    assert context_usage_hit("无关文本", sc, []) is False


def test_brain_conflict_taboo():
    chars = _scenario()["world_pack"]["world"]["characters"]
    assert detect_brain_conflict("苏清雪决定徇私放水帮助林澈", chars) is True
    assert detect_brain_conflict("苏清雪严格监考", chars) is False


def test_option_repeat_rate():
    rate = option_repeat_rate([
        ["去试炼峰", "回洞府"],
        ["去试炼峰", "休息"],
    ])
    assert 0 <= rate <= 1


def test_aggregate_turn_records():
    sc = _scenario()
    turns = [
        {
            "story": "林澈在试炼峰面对苏清雪",
            "options": ["前进", "后退"],
            "objective_progress": True,
            "event_progress": False,
            "relationship_delta": 0.1,
            "brain_conflict": False,
            "context_usage": True,
            "latency_sec": 2.0,
            "prompt_tokens": 1000,
            "completion_tokens": 500,
        },
        {
            "story": "短",
            "options": ["A", "B"],
            "objective_progress": False,
            "event_progress": True,
            "relationship_delta": 0.0,
            "brain_conflict": False,
            "context_usage": False,
            "latency_sec": 1.5,
            "prompt_tokens": 900,
            "completion_tokens": 400,
        },
    ]
    agg = aggregate_turn_records(turns, sc)
    assert agg["turns_ok"] == 2
    assert agg["objective_progress_rate"] == 0.5
    assert agg["avg_story_length"] > 0


def test_compare_architectures():
    legacy = {"objective_progress_rate": 0.4, "relationship_activity_rate": 0.2, "estimated_cost": 0.1}
    unified = {"objective_progress_rate": 0.38, "relationship_activity_rate": 0.19, "estimated_cost": 0.09}
    delta = compare_architectures(legacy, unified)
    assert delta["objective_progress_rate"] == -5.0


def test_evaluate_pass_fail():
    comparisons = [
        {
            "scenario_id": "01",
            "legacy": {"max_goal_absent_streak": 0},
            "unified": {"max_goal_absent_streak": 0},
            "delta_pct": {
                "objective_progress_rate": -5,
                "relationship_activity_rate": -3,
                "brain_consistency_score": -2,
                "estimated_cost": -2,
            },
        }
    ]
    ev = evaluate_pass_fail(comparisons)
    assert ev["verdict"] == "PASS"

    fail_comp = copy.deepcopy(comparisons[0])
    fail_comp["delta_pct"]["objective_progress_rate"] = -25
    ev2 = evaluate_pass_fail([fail_comp])
    assert ev2["verdict"] == "FAIL"


def test_snapshot_runtime():
    session = {"turn": 3, "objectives": {"main": [{"progress": 20}], "side": []}, "force_event_pending": False}
    memory = {"characters": {"A": {"trust": 0.5, "affection": 0.3}}, "world_flags": ["flag1"], "world_events": [{}]}
    plot = {"main_plot": {"progress": 15}, "unresolved_hooks": [1, 2]}
    snap = snapshot_runtime(session, memory, plot)
    assert snap["main_objective_progress"] == 20
    assert snap["world_events_count"] == 1
