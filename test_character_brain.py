"""Tests for V3.3 Character Brain."""
from unittest.mock import patch

import config
from engine.character_brain import (
    build_character_brain_context,
    ensure_personalities,
    infer_taboo_fallback,
    normalize_personality,
    resolve_brain_character_names,
    seed_personality_from_world,
)


def test_infer_taboo_fallback_from_fear():
    taboo = infer_taboo_fallback(
        {"isMain": False, "personality": {"fear": "被抛弃"}},
    )
    assert "被抛弃" in taboo


def test_infer_taboo_fallback_preserves_explicit():
    taboo = infer_taboo_fallback(
        {"isMain": False, "personality": {"taboo": "背主"}},
    )
    assert taboo == "背主"


def test_normalize_character_personality_backfills_npc_taboo():
    from ui.routes.world import _normalize_character_personality

    out = _normalize_character_personality({
        "name": "侍女",
        "isMain": False,
        "goal": "活下去",
        "personality": {"desire": "活下去", "fear": "被灭口", "taboo": "", "secret": "", "values": []},
    })
    assert out["personality"]["taboo"]
    assert "被灭口" in out["personality"]["taboo"]


def test_seed_personality_from_world_maps_fields():
    ch = {
        "goal": "获得自由",
        "secret": "私藏禁书",
        "personality_tags": ["冷静", "高傲"],
    }
    p = seed_personality_from_world(ch)
    assert p["desire"] == "获得自由"
    assert p["secret"] == "私藏禁书"
    assert p["values"] == ["冷静", "高傲"]


def test_seed_personality_preserves_explicit_brain():
    ch = {
        "goal": "获得自由",
        "secret": "表层秘密",
        "personality_tags": ["冷静"],
        "personality": {
            "desire": "掌控命运",
            "fear": "失去继承权",
            "taboo": "被命令",
            "secret": "私藏禁书",
            "values": ["荣誉"],
        },
    }
    p = seed_personality_from_world(ch)
    assert p["desire"] == "掌控命运"
    assert p["taboo"] == "被命令"
    assert p["secret"] == "私藏禁书"


def test_finalize_character_field_result_applies_personality():
    from ui.routes.world import _finalize_character_field_result

    result = {
        "name": "甲",
        "goal": "复仇",
        "personality": {
            "desire": "",
            "fear": "失败",
            "taboo": "被命令",
            "secret": "卧底",
            "values": ["荣誉"],
        },
    }
    out = _finalize_character_field_result(result)
    assert out["personality"]["taboo"] == "被命令"
    assert out["personality"]["secret"] == "卧底"
    assert isinstance(out["personality_tags"], list)


def test_finalize_character_field_result_seeds_from_goal():
    from ui.routes.world import _finalize_character_field_result

    out = _finalize_character_field_result({"name": "乙", "goal": "自由", "secret": "禁书"})
    assert out["personality"]["desire"] == "自由"
    assert out["personality"]["secret"] == "禁书"


def test_hybrid_filter_core_always_recent_background_only():
    session = {
        "turn": 20,
        "scene": "皇宫",
        "characters": {
            "a": {"name": "长公主"},
            "b": {"name": "北境使者"},
        },
    }
    memory = {
        "characters": {
            "长公主": {
                "tier": "核心",
                "last_appearance_turn": 20,
                "personality": {"desire": "自由", "fear": "", "taboo": "", "secret": "", "values": []},
            },
            "北境使者": {
                "tier": "背景",
                "last_appearance_turn": 2,
                "personality": {"desire": "南下", "fear": "", "taboo": "", "secret": "", "values": []},
            },
        },
    }
    world_pack = {
        "world": {
            "characters": [
                {"name": "长公主", "is_main": False},
                {"name": "北境使者", "is_main": False},
            ],
        },
    }
    names = resolve_brain_character_names(session, memory, world_pack)
    assert "长公主" in names
    assert "北境使者" not in names


def test_early_game_injects_roster_with_personality():
    session = {
        "turn": 0,
        "scene": "开场",
        "characters": {"a": {"name": "艾琳"}},
    }
    memory = {
        "characters": {
            "艾琳": {
                "personality": {
                    "desire": "查明真相",
                    "fear": "",
                    "taboo": "被命令",
                    "secret": "",
                    "values": ["正义"],
                },
            },
        },
    }
    world_pack = {"world": {"characters": [{"name": "艾琳", "is_main": False}]}}
    names = resolve_brain_character_names(session, memory, world_pack)
    assert names == {"艾琳"}


def test_build_character_brain_context_includes_taboo():
    memory = {
        "characters": {
            "长公主": {
                "personality": normalize_personality({
                    "desire": "获得自由",
                    "fear": "失去继承权",
                    "taboo": "被人操控",
                    "secret": "私藏禁书",
                    "values": ["荣誉", "血统"],
                }),
            },
        },
    }
    world_pack = {"world": {"characters": [{"name": "长公主"}]}}
    text = build_character_brain_context({"长公主"}, memory, world_pack)
    assert "【角色人格核心" in text
    assert "禁忌: 被人操控" in text
    assert "价值观: 荣誉 / 血统" in text


def test_build_character_brain_context_empty_when_no_content():
    memory = {"characters": {"路人": {"personality": normalize_personality({})}}}
    world_pack = {"world": {"characters": [{"name": "路人"}]}}
    assert build_character_brain_context({"路人"}, memory, world_pack) == ""


def test_ensure_personalities_backfills_from_world():
    memory = {"characters": {"甲": {"trust": 0.5}}}
    world_pack = {
        "world": {
            "characters": [
                {"name": "甲", "goal": "复仇", "secret": "卧底", "personality_tags": ["隐忍"]},
            ],
        },
    }
    ensure_personalities(memory, world_pack)
    p = memory["characters"]["甲"]["personality"]
    assert p["desire"] == "复仇"
    assert p["secret"] == "卧底"
    assert "隐忍" in p["values"]


def test_builder_injects_character_brain_block():
    from engine import io_utils

    session = {
        "turn": 5,
        "scene": "内廷",
        "status": "BUILD",
        "chapter": 1,
        "characters": {"a": {"name": "长公主", "level": "L1", "role": "公主"}},
        "history": [{"turn": 5, "story": "长公主在场", "choice": "A", "options": ["opt"] * 4}],
    }
    world = {
        "world": {
            "title": "测试",
            "main_goal": "护驾",
            "characters": [{"name": "长公主", "is_main": False, "role_tags": ["公主"]}],
            "relationship_system": {"stages": ["陌生"], "affection": 0},
        },
    }
    memory = {
        "characters": {
            "长公主": {
                "tier": "核心",
                "last_appearance_turn": 5,
                "personality": {
                    "desire": "获得自由",
                    "fear": "",
                    "taboo": "被命令",
                    "secret": "",
                    "values": ["荣誉"],
                },
            },
            "远客": {
                "tier": "背景",
                "last_appearance_turn": 1,
                "personality": {"desire": "旁观", "fear": "", "taboo": "", "secret": "", "values": []},
            },
        },
        "world_flags": [],
    }

    from engine.builder import build_prompt

    template = {
        "system": "sys {{FORCE_EVENT_NOTICE}} {{STORY_LENGTH}} {{STORY_LENGTH_MIN}} {{STORY_LENGTH_MAX}} {{AI_BEHAVIOR_RULES}} {{OPTION_COUNT}} {{CUSTOM_RULES}} {{MAIN_GOAL}}",
        "user": "{{WORLD}}\n{{LONG_TERM_MEMORY}}\n{{RECENT_SUMMARIES}}\n{{HOT_CONTEXT}}\n{{LAST_CHOICE}}\n{{CHARACTERS_CONTEXT}}\n{{CHARACTER_BRAIN}}\n{{RELATIONSHIP_SYSTEM}}\n{{ENGINE_RULES}}\n{{FORCE_EVENT_PROMPT}}",
    }

    def _yaml(path, use_cache=True):
        p = str(path)
        if "session_state" in p:
            return session
        if "world_pack.yaml" in p:
            return world
        if "engine.yaml" in p:
            return {"rules": []}
        if "prompt_template" in p:
            return template
        if "world_summary" in p:
            return {"summary": "测试"}
        return {}

    io_utils.clear_cache()
    with patch.object(io_utils, "read_yaml", side_effect=_yaml), \
         patch("engine.builder.load_memory", return_value=memory), \
         patch("engine.memory_layers.load_world_summary_text", return_value="世界: 测试"), \
         patch("engine.memory_layers.load_chapter_summaries", return_value=[]), \
         patch.object(config, "OBJECTIVE_SYSTEM_ENABLED", False), \
         patch.object(config, "PLOT_DIRECTOR_ENABLED", False):
        _system, user = build_prompt(current_choice="A")
        assert "【角色人格核心" in user
        assert "禁忌: 被命令" in user
        assert "远客" not in user.split("【角色人格核心")[1]


def test_character_brain_disabled():
    from engine import io_utils

    session = {"turn": 1, "scene": "x", "characters": {"a": {"name": "甲"}}, "history": []}
    world = {
        "world": {
            "characters": [{"name": "甲", "is_main": True}],
            "relationship_system": {},
        },
    }
    memory = {
        "characters": {
            "甲": {
                "personality": {"desire": "测试", "fear": "", "taboo": "", "secret": "", "values": []},
            },
        },
    }
    from engine.builder import build_prompt

    def _yaml(path, use_cache=True):
        p = str(path)
        if "session_state" in p:
            return session
        if "world_pack.yaml" in p:
            return world
        if "engine.yaml" in p:
            return {"rules": []}
        if "prompt_template" in p:
            return {
                "system": "sys {{FORCE_EVENT_NOTICE}} {{STORY_LENGTH}} {{STORY_LENGTH_MIN}} {{STORY_LENGTH_MAX}} {{AI_BEHAVIOR_RULES}} {{OPTION_COUNT}} {{CUSTOM_RULES}} {{MAIN_GOAL}}",
                "user": "{{WORLD}}\n{{CHARACTER_BRAIN}}\n{{CHARACTERS_CONTEXT}}",
            }
        return {}

    io_utils.clear_cache()
    with patch.object(io_utils, "read_yaml", side_effect=_yaml), \
         patch("engine.builder.load_memory", return_value=memory), \
         patch("engine.memory_layers.load_world_summary_text", return_value=""), \
         patch("engine.memory_layers.load_chapter_summaries", return_value=[]), \
         patch.object(config, "CHARACTER_BRAIN_ENABLED", False), \
         patch.object(config, "OBJECTIVE_SYSTEM_ENABLED", False), \
         patch.object(config, "PLOT_DIRECTOR_ENABLED", False):
        _system, user = build_prompt(current_choice=None)
        assert "【角色人格核心" not in user
