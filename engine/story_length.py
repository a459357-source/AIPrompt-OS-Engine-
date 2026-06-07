"""Story body length counting, ratio thresholds, and continuation prompts."""

from __future__ import annotations

import re

import config

_SENTENCE_END = re.compile(r"[。！？!?…\n]")
CONTINUATION_TAIL_CHARS = 500


def story_length_min_ratio(target: int) -> float:
    """Minimum acceptable ratio by target tier (V2 spec)."""
    t = int(target)
    if t < 1000:
        return config.STORY_LENGTH_MIN_RATIO_SHORT
    if t < 3000:
        return config.STORY_LENGTH_MIN_RATIO_MEDIUM
    return config.STORY_LENGTH_MIN_RATIO_LONG


def story_length_retry_min(target: int) -> int:
    """Minimum acceptable story chars; below this triggers continuation."""
    return max(0, int(int(target) * story_length_min_ratio(target)))


def should_retry_story_length(story_chars: int, target: int) -> bool:
    """True when story is too short; exceeding target never triggers retry."""
    return story_chars < story_length_retry_min(target)


def story_length_deficit(story_chars: int, target: int) -> int:
    """Chars still needed to reach minimum acceptable length."""
    return max(0, story_length_retry_min(target) - story_chars)


def build_continuation_user_prompt(
    *,
    story_tail: str,
    deficit_chars: int,
    scene: str,
    status: str,
    min_len: int,
    max_len: int,
    target: int,
) -> str:
    """Minimal user prompt for continue_writing — no full prompt replay."""
    tail = story_tail[-CONTINUATION_TAIL_CHARS:] if len(story_tail) > CONTINUATION_TAIL_CHARS else story_tail
    return (
        "【续写任务 — 必须遵守】\n"
        "请在保持当前剧情连续性、人物状态、文风、节奏不变的情况下，"
        "从正文结尾继续创作。\n"
        "禁止重复前文内容，禁止重新开始剧情。\n"
        f"当前场景：{scene or '未知'} | 状态：{status or 'SETUP'}\n"
        f"已有正文约 {len(story_tail.replace(' ', '').replace(chr(10), ''))} 字，"
        f"还需续写约 {deficit_chars} 字（目标总共 {target} 字，接受范围 {min_len}–{max_len}）。\n"
        "输出纯 JSON；story 字段**仅包含续写部分**（不要重复已有正文），"
        "state 与 options 与当前剧情一致。\n\n"
        f"【正文结尾】\n{tail}"
    )


def build_story_length_retry_notice(
    story_chars: int,
    target: int,
    min_len: int,
    max_len: int,
) -> str:
    """Legacy wording kept for tests/logging compatibility."""
    return (
        f"【字数修正 — 必须遵守】当前 story 约 {story_chars} 字，低于至少 {min_len} 字。"
        f"请从正文结尾继续创作：最终正文应在 {min_len}–{max_len} 字之间，目标约 {target} 字，"
        f"禁止重复前文，禁止重写开头。"
    )


def count_story_chars(text: str) -> int:
    """Count story body chars (ignore whitespace), matching frontend badge."""
    return len(text.replace(" ", "").replace("\n", "").replace("\r", ""))


def clamp_story_text(text: str, max_len: int, *, min_len: int = 0) -> tuple[str, bool]:
    """
    Trim story to max_len at last sentence boundary before the cut.
    Returns (clamped_text, was_clamped).
    """
    if not text or max_len <= 0:
        return text, False
    chars = count_story_chars(text)
    if chars <= max_len:
        return text, False

    count = 0
    cut_idx = len(text)
    for i, ch in enumerate(text):
        if ch not in " \n\r":
            count += 1
        if count > max_len:
            cut_idx = i
            break

    segment = text[:cut_idx]
    search_from = max(0, int(len(segment) * 0.6))
    best = -1
    for m in _SENTENCE_END.finditer(segment):
        if m.end() >= search_from:
            best = m.end()
    if best > 0:
        segment = segment[:best].rstrip()
    else:
        segment = segment.rstrip()

    if min_len > 0 and count_story_chars(segment) < min_len:
        return text[:cut_idx].rstrip(), True
    return segment, True
