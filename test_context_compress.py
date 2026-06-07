"""Tests for history compression (auto_compress + compress_threshold)."""
from engine.context_compress import (
    compress_history_for_prompt,
    estimate_history_tokens,
    lightweight_entry,
)


def _turn(n: int, chars: int = 500) -> dict:
    story = "字" * chars
    return {
        "turn": n,
        "scene": f"场景{n}",
        "status": "BUILD",
        "story": story,
        "summary": story[:120],
        "choice": "A",
        "characters": {"主角": {"level": "L1"}},
    }


def test_no_compression_when_small_history():
    history = [_turn(i, 200) for i in range(1, 6)]
    recent, summary, stats = compress_history_for_prompt(
        history,
        max_full_turns=20,
        auto_compress=True,
        compress_threshold=100_000,
    )
    assert len(recent) == 5
    assert summary is None
    assert stats["compressed"] is False


def test_max_context_messages_truncates_without_auto_compress():
    history = [_turn(i, 300) for i in range(1, 26)]
    recent, summary, stats = compress_history_for_prompt(
        history,
        max_full_turns=10,
        auto_compress=False,
        compress_threshold=100,
    )
    assert len(recent) == 10
    assert summary is not None
    assert "已压缩 15 轮" in summary
    assert stats["summarized_turns"] == 15
    assert stats["lightweight_turns"] == 0


def test_auto_compress_moves_old_turns_when_over_threshold():
    history = [_turn(i, 2000) for i in range(1, 12)]
    tokens_before = estimate_history_tokens(history)
    assert tokens_before > 4000

    recent, summary, stats = compress_history_for_prompt(
        history,
        max_full_turns=20,
        auto_compress=True,
        compress_threshold=4000,
    )
    assert stats["final_tokens"] <= 4000 or len(recent) == 4
    assert stats["compressed"] is True
    assert summary is not None
    assert len(recent) >= 4


def test_lightweight_entry_drops_heavy_fields():
    entry = _turn(1, 1000)
    lite = lightweight_entry(entry)
    assert "story" not in lite
    assert lite["compressed"] is True
    assert len(lite["summary"]) <= 200
