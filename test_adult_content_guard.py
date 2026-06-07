"""Tests for adult content guard."""
import config
from engine.adult_content_guard import ensure_adult_turn_content, _merge_adult_options


def test_adult_system_override_extreme():
    config.save_adult_mode(True)
    config.save_adult_profile("adult_first")
    config.save_content_weights({"story": 0, "romance": 0, "adult": 100})
    config.reload_app_behavior()
    text = config.adult_system_override_text()
    assert "最高优先级" in text
    assert "禁止全部选项" in text


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
