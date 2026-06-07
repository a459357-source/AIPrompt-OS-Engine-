"""Tests for streaming JSON story extraction."""
from engine.deepseek_client import parse_story_from_partial_json


def test_parse_partial_story_incomplete():
    story, done = parse_story_from_partial_json('{"story": "你好，世界')
    assert story == "你好，世界"
    assert done is False


def test_parse_complete_story():
    raw = '{"story": "段落一。\\n段落二。", "options": []}'
    story, done = parse_story_from_partial_json(raw)
    assert story == "段落一。\n段落二。"
    assert done is True


def test_parse_no_story_key():
    story, done = parse_story_from_partial_json('{"options": []}')
    assert story == ""
    assert done is False
