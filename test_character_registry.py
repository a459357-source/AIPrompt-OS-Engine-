"""Tests for character name dedupe and init relation labels."""
import config
from engine.character_registry import (
    canonicalize_characters_by_name,
    dedupe_characters_by_name,
    initial_relation_label,
    merge_proposed_characters,
)
from ui.routes.api import _merge_characters_with_memory


def _level_idx(level: str) -> int:
    try:
        return config.INTERACTION_LEVELS.index(level)
    except ValueError:
        return 0


def test_initial_relation_from_tags():
    label = initial_relation_label(
        "艾莉丝",
        is_main=False,
        relationship=["青梅竹马：诺亚"],
        char_relations={
            "艾莉丝": {
                "relationshipType": "lover",
                "tags": ["青梅竹马", "暗恋", "守护"],
            }
        },
    )
    assert label == "青梅竹马、暗恋、守护"


def test_initial_relation_main_is_protagonist():
    assert initial_relation_label("诺亚", is_main=True, relationship=[], char_relations={}) == "主角"


def test_initial_relation_from_world_relationship():
    label = initial_relation_label(
        "维克托",
        is_main=False,
        relationship=["死敌：诺亚"],
        char_relations={},
    )
    assert label == "死敌：诺亚"


def test_dedupe_characters_by_name_keeps_latest():
    raw = {
        "A": {"name": "诺亚", "relation": "死敌", "level": "L0"},
        "诺亚": {"name": "诺亚", "relation": "主角", "level": "L1"},
    }
    out = dedupe_characters_by_name(raw)
    assert len(out) == 1
    assert list(out.values())[0]["relation"] == "主角"


def test_merge_proposed_characters_by_name():
    old = {
        "A": {"name": "诺亚", "role": "骑士", "level": "L1", "relation": "死敌"},
        "B": {"name": "艾莉丝", "role": "公主", "level": "L0", "relation": "死敌"},
    }
    proposed = {
        "诺亚": {"name": "诺亚", "role": "主角", "level": "L2", "relation": "主角"},
        "艾莉丝": {"name": "艾莉丝", "level": "L1", "relation": "青梅竹马、暗恋、守护"},
    }
    merged = merge_proposed_characters(old, proposed, level_idx_fn=_level_idx)
    assert len({v["name"] for v in merged.values()}) == 2
    assert merged["A"]["relation"] == "主角"
    assert merged["A"]["level"] == "L2"
    assert merged["B"]["relation"] == "青梅竹马、暗恋、守护"


def test_canonicalize_removes_duplicate_keys():
    chars = {
        "A": {"name": "艾莉丝", "relation": "死敌", "level": "L0"},
        "艾莉丝": {"name": "艾莉丝", "relation": "青梅竹马", "level": "L1"},
    }
    out = canonicalize_characters_by_name(chars, level_idx_fn=_level_idx)
    assert len(out) == 1
    assert "A" in out
    assert out["A"]["relation"] == "青梅竹马"


def test_api_merge_dedupes_for_ui():
    raw = {
        "A": {"name": "诺亚", "relation": "死敌"},
        "诺亚": {"name": "诺亚", "relation": "主角"},
    }
    merged = _merge_characters_with_memory(raw, {}, {})
    assert len(merged) == 1
    assert list(merged.values())[0]["relation"] == "主角"
