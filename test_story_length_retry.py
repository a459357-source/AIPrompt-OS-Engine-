"""Tests for story-length continuation thresholds (V2 ratio tiers)."""
from engine.story_length import (
    should_retry_story_length,
    story_length_retry_min,
    build_story_length_retry_notice,
    build_continuation_user_prompt,
    story_length_min_ratio,
)


def test_min_ratio_short_story():
    assert story_length_min_ratio(600) == 0.80
    assert story_length_retry_min(600) == 480


def test_min_ratio_medium_story():
    assert story_length_min_ratio(2000) == 0.85
    assert story_length_retry_min(2000) == 1700


def test_min_ratio_long_story():
    assert story_length_min_ratio(4000) == 0.90
    assert story_length_retry_min(4000) == 3600


def test_should_retry_only_when_below_ratio_floor():
    assert should_retry_story_length(479, 600) is True
    assert should_retry_story_length(480, 600) is False
    assert should_retry_story_length(1699, 2000) is True
    assert should_retry_story_length(1700, 2000) is False


def test_continuation_prompt_forbids_rewrite():
    msg = build_continuation_user_prompt(
        story_tail="已有正文结尾。",
        deficit_chars=200,
        scene="酒馆",
        status="BUILD",
        min_len=480,
        max_len=800,
        target=600,
    )
    assert "续写" in msg
    assert "禁止重复" in msg
    assert "禁止重新开始" in msg


def test_retry_notice_uses_acceptable_range_wording():
    msg = build_story_length_retry_notice(350, 600, 400, 800)
    assert "400–800" in msg
    assert "目标约 600" in msg
