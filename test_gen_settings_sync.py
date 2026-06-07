"""Tests for story-length ↔ max_tokens / compress_threshold sync."""
import config


def test_tokens_for_story_length_4000():
    assert config.tokens_for_story_length(4000) == 8900


def test_compress_threshold_scales_with_story_length():
    low = config.compress_threshold_for_story_length(1000)
    high = config.compress_threshold_for_story_length(4000)
    assert low == 7000
    assert high == 16000
    assert high > low


def test_story_length_target_bounds():
    assert config.min_story_length_for_target(600) == 510
    assert config.max_story_length_for_target(600) == 690
    assert config.min_story_length_for_target(1000) == 850
    assert config.max_story_length_for_target(1000) == 1150


def test_save_story_length_syncs_tokens_and_compress(tmp_path, monkeypatch):
    settings_path = tmp_path / "apikey.json"
    monkeypatch.setattr(config, "APIKEY_PATH", settings_path)

    config.save_story_length(4000)
    config.reload_story_length()
    config.reload_max_tokens()
    config.reload_context_settings()

    assert config.STORY_LENGTH == 4000
    assert config.MAX_TOKENS == 8900
    assert config.COMPRESS_THRESHOLD == 16000
