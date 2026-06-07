"""Tests for adult content guard."""
import config
from engine.adult_content_guard import ensure_adult_turn_content, _merge_adult_options


def test_adult_system_override_extreme():
    config.save_adult_mode(True)
    config.save_adult_profile("adult_first")
    config.save_content_weights({"story": 0, "romance": 0, "adult": 100})
    config.reload_app_behavior()
    assert config.use_adult_extreme_template()
    override = config.adult_system_override_text()
    assert "禁止男男" in override
    assert "男性角色↔女性角色" in override
    assert "女↔女" in override or "女性角色↔女性角色" in override
    text = config.adult_extreme_content_rules_text()
    assert "每轮性内容铁律" in text
    assert "禁止男男" in text


def test_adult_orientation_supreme_all_tiers():
    config.save_adult_mode(True)
    config.save_adult_profile("balanced")
    config.save_content_weights({"story": 40, "romance": 30, "adult": 30})
    config.reload_app_behavior()
    assert "禁止男男" in config.adult_system_override_text()
    assert "禁止男男" in config.content_preference_rules_text()
    config.save_adult_mode(False)
    config.reload_app_behavior()


def test_merge_adult_options_replaces_mission():
    config.save_adult_mode(True)
    config.reload_app_behavior()
    mission = [
        "跟随艾莉森前往驾驶舱，准备对接铁砧基地→推进主线|谨慎|trust+1",
        "与陈锋搜索货舱寻找武器→生存|装备|trust+1",
        "独自前往通讯室窃听→风险|情报|trust+1",
    ]
    merged = _merge_adult_options(
        mission,
        partners=["艾莉森"],
        need=2,
        count=3,
    )
    assert config.intimate_option_count(merged) >= 2


def test_ensure_adult_turn_content_injects_when_needed():
    config.save_adult_mode(True)
    config.save_adult_profile("adult_first")
    config.save_content_weights({"story": 0, "romance": 0, "adult": 100})
    config.reload_app_behavior()
    resp = {
        "story": "林逸与艾莉森在舱室内对话。",
        "options": [
            "前往驾驶舱对接基地",
            "搜索货舱",
            "窃听通讯",
        ],
        "state": {"characters": {"c1": {"name": "艾莉森"}}},
    }
    out = ensure_adult_turn_content(resp, scene="穿梭机", characters={"c1": {"name": "艾莉森"}})
    assert config.intimate_option_count(out["options"]) >= 2
    config.save_adult_mode(False)
    config.reload_app_behavior()
