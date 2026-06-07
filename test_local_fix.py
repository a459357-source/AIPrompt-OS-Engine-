"""Tests for local JSON/response repair."""
from engine.local_fix import fix_response, salvage_json


def test_salvage_truncated_story_json():
    raw = '{"story": "这是一段足够长的测试正文内容，用于验证 salvage 逻辑可以提取 story 字段", "state": {'
    data = salvage_json(raw)
    assert data is not None
    assert "story" in data
    assert len(data["story"]) >= 20


def test_fix_options_padding():
    data = fix_response({
        "story": "x" * 30,
        "state": {"status": "INVALID", "characters": {}},
        "options": ["仅一个选项"],
    })
    assert len(data["options"]) == 4


def test_clamp_trust_metrics():
    data = fix_response({
        "story": "x" * 30,
        "state": {
            "status": "SETUP",
            "characters": {"A": {"trust": 150, "affection": -5}},
        },
        "options": ["a", "b", "c", "d"],
    })
    ch = data["state"]["characters"]["A"]
    assert ch["trust"] == 100
    assert ch["affection"] == 0
