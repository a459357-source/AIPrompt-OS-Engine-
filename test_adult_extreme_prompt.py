"""Tests for adult extreme prompt template selection and rules."""
import config
from engine.builder import build_prompt


def _enable_extreme():
    config.save_adult_mode(True)
    config.save_adult_profile("adult_first")
    config.save_content_weights({"story": 0, "romance": 0, "adult": 100})
    config.reload_app_behavior()


def test_resolve_extreme_template_path():
    _enable_extreme()
    path = config.resolve_prompt_template_path()
    assert path.name == "prompt_template_adult_extreme.yaml"
    assert path.is_file()


def test_adult_system_override_empty_when_extreme_template():
    _enable_extreme()
    assert config.adult_system_override_text() == ""
    rules = config.adult_extreme_content_rules_text()
    assert "每轮性内容铁律" in rules
    assert "COOLDOWN" in rules


def test_vocabulary_domain_from_world_pack():
    world = {
        "custom": {"vocabulary_domain": "古代宫廷语境，使用「承欢」「侍寝」等词汇"},
        "world": {},
    }
    text = config.vocabulary_domain_text(world)
    assert "古代宫廷" in text


def test_normalized_intimacy_block_disabled_by_default():
    assert config.normalized_intimacy_block({}) == ""


def test_normalized_intimacy_block_when_enabled():
    world = {
        "custom": {
            "normalized_intimacy_mode": {
                "enabled": True,
                "description": "后入式为默认常态",
            }
        }
    }
    block = config.normalized_intimacy_block(world)
    assert "常态操法模式" in block
    assert "后入式" in block


def test_intimacy_escalation_hint_cooldown():
    _enable_extreme()
    session = {"status": "COOLDOWN", "history": [{"intimacy_level": 3}]}
    hint = config.intimacy_escalation_hint(session)
    assert "COOLDOWN" in hint
    assert "3" in hint


def test_validate_adult_story_content_extreme():
    _enable_extreme()
    warnings = config.validate_adult_story_content("他们在驾驶舱讨论任务计划。", status="BUILD")
    assert any("亲密标记" in w for w in warnings)


def test_build_prompt_uses_extreme_template():
    _enable_extreme()
    from engine import io_utils

    io_utils.clear_cache()
    system, user = build_prompt(current_choice=None)
    assert "每轮性内容铁律" in system
    assert "优先级" in system
    assert "性内容进度" in user
    config.save_adult_mode(False)
    config.reload_app_behavior()


def test_infer_intimacy_level_increases():
    prev = 2
    story = "他解开她的衣扣，唇舌缠绵，她高潮颤抖着释放。"
    level = config.infer_intimacy_level(story, prev)
    assert level > prev
