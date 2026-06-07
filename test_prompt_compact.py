"""Tests for prompt compaction helpers."""
import json

from engine.prompt_compact import (
    compact_engine_rules,
    compact_state_for_prompt,
    compact_world_for_prompt,
)


def test_compact_world_omits_full_character_dump():
    world_pack = {
        "world": {
            "title": "测试世界",
            "main_goal": "找到星核",
            "characters": [{"name": "林夜", "background": "x" * 5000}],
            "factions": [{"name": "联邦", "description": "星际政府"}],
        }
    }
    text = compact_world_for_prompt(world_pack)
    assert "测试世界" in text
    assert "星核" in text
    assert "联邦" in text
    assert "x" * 100 not in text


def test_compact_state_trims_long_story():
    state = {
        "turn": 5,
        "scene": "舰桥",
        "status": "BUILD",
        "characters": {"A": {"name": "林夜", "role": "船长", "note": "n" * 500}},
        "history": [{"turn": 4, "story": "s" * 2000, "scene": "x", "status": "BUILD", "choice": "A"}],
    }
    compact = compact_state_for_prompt(state)
    assert len(compact["history"][0]["story"]) <= 801
    assert len(compact["characters"]["A"]["note"]) <= 81


def test_compact_engine_rules_is_short_text():
    rules = compact_engine_rules({"engine": {"name": "Test", "state_machine": {"states": ["A", "B"]}}})
    assert "状态机" in rules
    assert len(rules) < 500
