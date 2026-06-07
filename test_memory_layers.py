"""Tests for V2 memory layers."""
import json
from pathlib import Path

import config
from engine.memory_layers import (
    build_hot_context,
    build_long_term_memory,
    build_recent_summaries,
    maybe_update_chapter_summary,
    save_chapter_summaries,
)


def test_hot_context_keeps_recent_turns():
    session = {
        "turn": 10,
        "scene": "酒馆",
        "status": "BUILD",
        "chapter": 1,
        "characters": {"A": {"name": "艾琳", "level": "L1"}},
        "history": [
            {"turn": i, "scene": "s", "status": "BUILD", "choice": "A", "story": "正文" * 50}
            for i in range(1, 11)
        ],
    }
    text = build_hot_context(session, {})
    assert "T10" in text
    assert "正文" in text
    assert "【最近回合正文】" in text


def test_long_term_excludes_full_story():
    memory = {
        "characters": {"艾琳": {"trust": 0.6, "flags": ["met"]}},
        "world_flags": ["flag_a"],
    }
    session = {"turn": 5, "history": [{"story": "不应出现" * 100}]}
    block = build_long_term_memory(memory, session)
    assert "不应出现" not in block


def test_chapter_summary_every_five_turns(tmp_path, monkeypatch):
    path = tmp_path / "chapter_summaries.json"
    monkeypatch.setattr(config, "CHAPTER_SUMMARIES_PATH", path)
    monkeypatch.setattr(config, "CHAPTER_SUMMARY_INTERVAL", 5)

    session = {
        "turn": 5,
        "chapter": 1,
        "history": [
            {"turn": i, "scene": "场景", "choice": "A", "story": "s", "summary": "s"}
            for i in range(1, 6)
        ],
    }
    entry = maybe_update_chapter_summary(session, {})
    assert entry is not None
    assert path.exists()
    summaries = json.loads(path.read_text(encoding="utf-8"))["summaries"]
    assert len(summaries) == 1


def test_recent_summaries_injection():
    save_chapter_summaries([
        {"chapter_id": 1, "summary": "第一章摘要", "important_events": ["事件A"]},
        {"chapter_id": 2, "summary": "第二章摘要", "important_events": []},
    ])
    text = build_recent_summaries(count=2)
    assert "第一章摘要" in text or "第二章摘要" in text
