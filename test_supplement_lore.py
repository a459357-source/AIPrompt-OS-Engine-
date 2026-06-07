"""Tests for supplement lore analysis and apply (no live AI)."""

from unittest.mock import patch

import pytest

import config
from engine import io_utils
from engine.supplement_lore import analyze_supplement, apply_supplement, supplement_lore


@pytest.fixture
def lore_env(tmp_path, monkeypatch):
    world_pack = {
        "world": {
            "title": "测试故事",
            "setting": "魔法学院",
            "main_goal": "揭开秘密",
            "characters": [
                {
                    "name": "主角",
                    "is_main": True,
                    "role_tags": ["学生"],
                    "personality_tags": ["冷静"],
                    "appearance": "黑发",
                    "relationship": [],
                    "goal": "毕业",
                    "secret": "",
                    "background": "",
                    "special_ability": "",
                },
                {
                    "name": "艾莉丝",
                    "is_main": False,
                    "role_tags": ["同学"],
                    "personality_tags": ["活泼"],
                    "appearance": "金发",
                    "relationship": ["同学"],
                    "goal": "交朋友",
                    "secret": "",
                    "background": "",
                    "special_ability": "",
                },
            ],
            "factions": [
                {"name": "学生会", "type": "organization", "description": "管理学院"},
            ],
            "artifacts": [],
            "relationship_system": {"stages": ["陌生", "认识", "朋友"], "affection": 0},
            "locations": [{"name": "教室", "desc": "初始场景"}],
        },
        "custom": {"characterRelations": {}, "stats": []},
    }
    session = {
        "scene": "教室",
        "status": "BUILD",
        "turn": 2,
        "characters": {
            "A": {"name": "主角", "role": "学生", "level": "L0", "relation": "主角", "note": ""},
            "B": {"name": "艾莉丝", "role": "同学", "level": "L0", "relation": "同学", "note": ""},
        },
        "history": [{"turn": 2, "story": "艾莉丝向主角打招呼。", "options": [], "choice": ""}],
        "chapter": 1,
    }
    memory = {
        "characters": {
            "主角": {"trust": 0.5, "flags": [], "relationship": "主角"},
            "艾莉丝": {"trust": 0.5, "flags": [], "relationship": "同学"},
        },
        "factions": {},
    }

    wp = tmp_path / "world_pack.yaml"
    ss = tmp_path / "session_state.yaml"
    mem = tmp_path / "memory.json"
    ws = tmp_path / "world_summary.json"

    io_utils.write_yaml(wp, world_pack)
    io_utils.write_yaml(ss, session)
    io_utils.write_json(mem, memory)
    io_utils.write_json(ws, {"title": "测试故事"})

    monkeypatch.setattr(config, "WORLD_PACK_PATH", wp)
    monkeypatch.setattr(config, "SESSION_STATE_PATH", ss)
    monkeypatch.setattr(config, "MEMORY_PATH", mem)
    monkeypatch.setattr(config, "WORLD_SUMMARY_PATH", ws)

    return {"world_pack_path": wp, "session_path": ss, "memory_path": mem}


def test_merge_special_ability_append_and_remove():
    from engine.supplement_lore import _merge_special_ability

    existing = "能与星辰碎片产生共鸣，短暂强化自身。"
    merged, changed = _merge_special_ability(existing, {"special_ability": "催眠术"})
    assert changed is True
    assert "星辰碎片" in merged
    assert "催眠术" in merged

    merged2, changed2 = _merge_special_ability(merged, {"special_ability": "催眠术"})
    assert changed2 is False

    merged3, changed3 = _merge_special_ability(
        merged,
        {"special_ability_remove": "催眠术"},
    )
    assert changed3 is True
    assert "催眠术" not in merged3
    assert "星辰碎片" in merged3

    merged4, changed4 = _merge_special_ability(
        existing,
        {"special_ability_replace": True, "special_ability": "仅会催眠术"},
    )
    assert changed4 is True
    assert merged4 == "仅会催眠术"


def test_apply_supplement_append_special_ability(lore_env):
    pack_before = io_utils.read_yaml(lore_env["world_pack_path"])
    hero = next(c for c in pack_before["world"]["characters"] if c["name"] == "主角")
    hero["special_ability"] = "原有能力"
    io_utils.write_yaml(lore_env["world_pack_path"], pack_before)

    apply_supplement({
        "story_prompt": "",
        "characters": [{"action": "update", "name": "主角", "special_ability": "催眠术"}],
        "factions": [],
        "artifacts": [],
        "characterRelations": {},
        "summary": "追加催眠术",
    })
    pack = io_utils.read_yaml(lore_env["world_pack_path"])
    hero_after = next(c for c in pack["world"]["characters"] if c["name"] == "主角")
    assert "原有能力" in hero_after["special_ability"]
    assert "催眠术" in hero_after["special_ability"]


def test_normalize_rel_entry_only_explicit_fields():
    from engine.supplement_lore import _normalize_rel_entry

    assert _normalize_rel_entry({"affection": 40}) == {"affection": 40}
    assert _normalize_rel_entry({"relationshipType": "rival", "tags": ["竞争"]}) == {
        "relationshipType": "rival",
        "tags": ["竞争"],
    }
    assert _normalize_rel_entry({}) == {}


def test_apply_supplement_story_prompt_and_relation(lore_env):
    analysis = {
        "story_prompt": "禁止出现现代武器。",
        "characters": [],
        "factions": [],
        "characterRelations": {
            "艾莉丝": {
                "relationshipType": "rival",
                "affection": 40,
                "trust": 30,
                "respect": 50,
                "dependence": 10,
                "hostility": 20,
                "attraction": 15,
                "tags": ["竞争"],
            },
        },
        "summary": "已更新关系与 prompt",
    }
    result = apply_supplement(analysis)
    assert result["story_prompt_added"] is True
    assert "已追加故事专属 prompt" in result["changes"]

    pack = io_utils.read_yaml(lore_env["world_pack_path"])
    assert "禁止出现现代武器" in pack["custom"]["story_prompt"]
    assert pack["custom"]["characterRelations"]["艾莉丝"]["relationshipType"] == "rival"

    memory = io_utils.read_json(lore_env["memory_path"])
    assert memory["characters"]["艾莉丝"]["relationship_type"] == "rival"
    assert memory["characters"]["艾莉丝"]["affection"] == 0.4


def test_apply_supplement_add_faction(lore_env):
    analysis = {
        "story_prompt": "",
        "characters": [],
        "factions": [
            {
                "action": "add",
                "name": "暗部",
                "type": "organization",
                "description": "秘密组织",
                "goals": ["监视"],
                "leader": "",
            },
        ],
        "characterRelations": {},
        "summary": "新增暗部",
    }
    apply_supplement(analysis)
    pack = io_utils.read_yaml(lore_env["world_pack_path"])
    names = [f["name"] for f in pack["world"]["factions"]]
    assert "暗部" in names


def test_apply_supplement_world_core_artifact_stats(lore_env):
    analysis = {
        "story_prompt": "",
        "title": "新标题",
        "world": "扩展后的世界观描述",
        "genre": ["悬疑", "校园"],
        "main_goal": "查明真相",
        "scene": "图书馆",
        "scene_desc": "禁书区在地下",
        "rel_stages": ["陌生", "试探", "盟友"],
        "rel_affection": 10,
        "stats": [{"action": "add", "key": "suspicion", "label": "怀疑度", "max": 100}],
        "characters": [],
        "factions": [],
        "artifacts": [
            {
                "action": "add",
                "name": "古书",
                "type": "world",
                "description": "封印咒语",
                "ownerType": "none",
                "ownerId": "",
                "importance": 80,
                "abilities": ["解封"],
                "tags": ["关键"],
            },
        ],
        "characterRelations": {},
        "summary": "综合更新",
    }
    apply_supplement(analysis)
    pack = io_utils.read_yaml(lore_env["world_pack_path"])
    world = pack["world"]
    assert world["title"] == "新标题"
    assert world["setting"] == "扩展后的世界观描述"
    assert "图书馆" in [loc["name"] for loc in world["locations"]]
    assert world["relationship_system"]["stages"] == ["陌生", "试探", "盟友"]
    assert pack["custom"]["stats"][0]["key"] == "suspicion"
    art_names = [a["name"] for a in world["artifacts"]]
    assert "古书" in art_names


def test_analyze_supplement_empty_raises(lore_env):
    with pytest.raises(ValueError, match="请输入"):
        analyze_supplement("   ")


def test_supplement_lore_end_to_end(lore_env):
    fake_ai = {
        "story_prompt": "叙事偏悬疑。",
        "characters": [
            {
                "action": "update",
                "name": "艾莉丝",
                "secret": "其实是间谍",
            },
        ],
        "factions": [],
        "characterRelations": {},
        "summary": "更新了艾莉丝",
    }
    with patch("engine.supplement_lore.call_deepseek", return_value=fake_ai):
        result = supplement_lore("艾莉丝其实是间谍")
    assert result["summary"] == "更新了艾莉丝"
    pack = io_utils.read_yaml(lore_env["world_pack_path"])
    alice = next(c for c in pack["world"]["characters"] if c["name"] == "艾莉丝")
    assert alice["secret"] == "其实是间谍"
