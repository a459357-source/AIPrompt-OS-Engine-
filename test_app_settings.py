"""Tests for app behavior settings (AI + save + export)."""
import config
from engine.repetition import check_story_repetition, similarity_ratio


def test_option_count_clamp():
    config.save_option_count(99)
    config.reload_option_count()
    assert config.OPTION_COUNT == 5


def test_save_slots_dynamic():
    config.save_max_save_slots(5)
    config.reload_max_save_slots()
    slots = config.all_save_slots()
    assert "slot5" in slots
    assert "slot6" not in slots


def test_force_event_thresholds_strict():
    config.save_repetition_check("strict")
    config.reload_repetition_check()
    thresholds = config.force_event_thresholds()
    assert thresholds["same_scene"] <= config.MAX_TURNS_SAME_SCENE


def test_repetition_detection():
    a = "她站在窗前望着樱花飘落，心中泛起涟漪。"
    b = "她站在窗前望着樱花飘落，心中泛起涟漪。"
    assert similarity_ratio(a, b) >= 0.9
    repetitive, _ = check_story_repetition(b, [{"turn": 1, "story": a}], "standard")
    assert repetitive is True


def test_ai_behavior_rules_contains_option_count():
    config.save_option_count(3)
    config.reload_option_count()
    text = config.ai_behavior_rules_text()
    assert "3 个 options" in text


def test_adult_mode_high_weight_prompts_explicit_content():
    config.save_adult_mode(True)
    config.save_adult_profile("adult_first")
    config.save_content_weights({"story": 0, "romance": 0, "adult": 100})
    config.reload_app_behavior()
    text = config.content_preference_rules_text()
    assert "成人强度 · 极高" in text
    assert "性行为描写" in text
    assert "解除全年龄限制" in text
    assert "禁止自我审查" in text
    behavior = config.ai_behavior_rules_text()
    assert "unrestricted adult fiction" in behavior
    assert config.adult_options_hint_text().startswith("；至少 3 个")
    assert "色情行动" in config.adult_task_hint_text()
    hint = config.adult_choice_execution_hint("解开她的衣扣，吻上去")
    assert "成人执行" in hint
    config.save_adult_mode(False)
    config.reload_app_behavior()
