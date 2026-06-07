"""Tests for story-length ↔ max_tokens / compress_threshold sync."""
import config


def test_tokens_for_story_length_4000():
    assert config.tokens_for_story_length(4000, option_count=4) == 6320
    assert config.tokens_for_story_length(4000, option_count=3) == 6240


def test_tokens_for_story_length_600():
    assert config.tokens_for_story_length(600, option_count=4) == 1730
    assert config.tokens_for_story_length(600, option_count=3) == 1650


def test_compress_threshold_scales_with_story_length():
    low = config.compress_threshold_for_story_length(1000)
    high = config.compress_threshold_for_story_length(4000)
    assert low == 7000
    assert high == 16000
    assert high > low


def test_story_length_float_margin():
    assert config.story_length_float_margin(600) == 200
    assert config.story_length_float_margin(999) == 200
    assert config.story_length_float_margin(1000) == 200
    assert config.story_length_float_margin(4000) == 600
    assert config.story_length_float_margin(10000) == 1000


def test_story_length_target_bounds():
    assert config.min_story_length_for_target(600) == 400
    assert config.max_story_length_for_target(600) == 800
    assert config.min_story_length_for_target(1000) == 800
    assert config.max_story_length_for_target(1000) == 1200
    assert config.min_story_length_for_target(4000) == 3400
    assert config.max_story_length_for_target(4000) == 4600


def test_save_story_length_syncs_tokens_and_compress(tmp_path, monkeypatch):
    settings_path = tmp_path / "apikey.json"
    monkeypatch.setattr(config, "APIKEY_PATH", settings_path)

    config.save_story_length(4000)
    config.reload_story_length()
    config.reload_max_tokens()
    config.reload_context_settings()

    assert config.STORY_LENGTH == 4000
    assert config.MAX_TOKENS == config.tokens_for_story_length(4000)
    assert config.MAX_TOKENS == 6320
    assert config.COMPRESS_THRESHOLD == 16000
