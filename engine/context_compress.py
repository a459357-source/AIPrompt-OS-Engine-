"""
context_compress.py — History compression for prompt context
=============================================================
Uses compress_threshold + auto_compress settings to shrink older
turn history before it is injected into STATE_JSON.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Match builder.py Chinese token heuristic
CHARS_TO_TOKENS = 0.6
MIN_FULL_TURNS = 4


def estimate_text_tokens(text: str) -> int:
    """Rough token estimate for mixed Chinese/JSON text."""
    return max(0, int(len(text) * CHARS_TO_TOKENS))


def estimate_history_tokens(history: list) -> int:
    """Estimate tokens for a history list as serialized in STATE_JSON."""
    if not history:
        return 0
    return estimate_text_tokens(json.dumps(history, ensure_ascii=False))


def summarize_turn_line(entry: dict, *, max_chars: int = 120) -> str:
    text = entry.get("summary") or entry.get("story", "")
    choice = entry.get("choice") or "-"
    return (
        f"T{entry.get('turn', '?')} [{entry.get('status', '?')}] "
        f"{entry.get('scene', '?')} 选:{choice}: {str(text)[:max_chars]}"
    )


def lightweight_entry(entry: dict, *, max_summary: int = 200) -> dict:
    """Drop heavy fields; keep enough context for continuity."""
    story = entry.get("story", "")
    summary = entry.get("summary") or story
    return {
        "turn": entry.get("turn"),
        "scene": entry.get("scene"),
        "status": entry.get("status"),
        "choice": entry.get("choice"),
        "summary": str(summary)[:max_summary],
        "compressed": True,
    }


def _entry_is_lightweight(entry: dict) -> bool:
    return bool(entry.get("compressed")) or not entry.get("story")


def compress_history_for_prompt(
    full_history: list,
    *,
    max_full_turns: int,
    auto_compress: bool,
    compress_threshold: int,
) -> tuple[list, str | None, dict[str, Any]]:
    """
    Build history payload for STATE_JSON.

    1. Cap recent full turns at max_full_turns (上下文消息上限).
    2. If auto_compress and history tokens > compress_threshold, move older
       turns into summary lines and/or lightweight recent entries.
    """
    stats: dict[str, Any] = {
        "original_turns": len(full_history),
        "original_tokens": estimate_history_tokens(full_history),
        "auto_compress": auto_compress,
        "compress_threshold": compress_threshold,
        "max_full_turns": max_full_turns,
        "compressed": False,
        "summarized_turns": 0,
        "lightweight_turns": 0,
    }

    if not full_history:
        stats["final_turns"] = 0
        stats["final_tokens"] = 0
        return [], None, stats

    max_full = max(MIN_FULL_TURNS, min(100, int(max_full_turns)))
    summary_bucket: list[dict] = []
    recent: list[dict] = list(full_history)

    if len(recent) > max_full:
        summary_bucket.extend(recent[:-max_full])
        recent = recent[-max_full:]
        stats["compressed"] = True

    if auto_compress:
        while estimate_history_tokens(recent) > compress_threshold and len(recent) > MIN_FULL_TURNS:
            summary_bucket.append(recent.pop(0))
            stats["compressed"] = True

        idx = 0
        while estimate_history_tokens(recent) > compress_threshold and idx < len(recent) - MIN_FULL_TURNS:
            entry = recent[idx]
            if not _entry_is_lightweight(entry):
                recent[idx] = lightweight_entry(entry)
                stats["compressed"] = True
                stats["lightweight_turns"] += 1
            idx += 1

    history_summary: str | None = None
    if summary_bucket:
        stats["summarized_turns"] = len(summary_bucket)
        lines = [summarize_turn_line(h) for h in summary_bucket]
        history_summary = f"（已压缩 {len(summary_bucket)} 轮历史摘要）\n" + "\n".join(lines)

    stats["final_turns"] = len(recent)
    stats["final_tokens"] = estimate_history_tokens(recent) + estimate_text_tokens(history_summary or "")

    if stats["compressed"] or stats["summarized_turns"]:
        logger.info(
            "🗜️ 上下文压缩: auto=%s 阈值=%d | 历史 %d轮 %d→%d tokens | "
            "保留%d轮 摘要%d轮 轻量%d轮",
            auto_compress,
            compress_threshold,
            stats["original_turns"],
            stats["original_tokens"],
            stats["final_tokens"],
            stats["final_turns"],
            stats["summarized_turns"],
            stats["lightweight_turns"],
        )
    elif auto_compress and stats["original_tokens"] > compress_threshold:
        logger.info(
            "🗜️ 上下文未再压缩: 已达最少保留 %d 轮，当前约 %d tokens（阈值 %d）",
            MIN_FULL_TURNS,
            stats["final_tokens"],
            compress_threshold,
        )

    return recent, history_summary, stats
