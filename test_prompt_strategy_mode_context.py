"""Tests for PromptStrategy Mode Context (unified prompt architecture)."""
import config
from engine.experience.prompt_strategy import get_prompt_strategy


def test_story_mode_context_has_weight_block():
    config.save_experience_mode("story")
    config.reload_app_behavior()
    strategy = get_prompt_strategy()
    ctx = strategy.build_mode_context(
        world_pack={"world": {}},
        session_state={"history": []},
    )
    assert "Story Mode" in ctx.system_block
    assert "World:" in ctx.system_block
    assert ctx.main_goal_suffix == ""
    assert ctx.task_hint == ""
    assert strategy.requires_content_guard() is False


def test_adult_extreme_mode_context(monkeypatch):
    monkeypatch.setenv("PROMPTOS_SKIP_ADULT_UNLOCK", "1")
    config.save_experience_mode("adult")
    config.save_adult_profile("adult_first")
    config.save_content_weights({"story": 0, "romance": 0, "adult": 100})
    config.reload_app_behavior()
    strategy = get_prompt_strategy()
    assert strategy.get_intensity_tier() == "extreme"
    ctx = strategy.build_mode_context(
        world_pack={"world": {}},
        session_state={"status": "BUILD", "history": []},
    )
    assert "Adult Mode" in ctx.system_block
    assert "每轮性内容铁律" in ctx.system_block
    assert "优先级" in ctx.system_block
    assert "70%+" in ctx.task_hint
    assert strategy.requires_content_guard() is True
    config.save_experience_mode("story")
    config.reload_app_behavior()


def test_adult_weights(monkeypatch):
    monkeypatch.setenv("PROMPTOS_SKIP_ADULT_UNLOCK", "1")
    config.save_experience_mode("adult")
    config.reload_app_behavior()
    w = get_prompt_strategy().get_prompt_weights()
    assert w.world == 0.20
    assert w.relationship == 0.55
    config.save_experience_mode("story")
    config.reload_app_behavior()
