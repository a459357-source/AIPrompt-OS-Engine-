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
