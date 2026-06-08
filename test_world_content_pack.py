"""V6 World Content Generation Template Pack tests."""

from __future__ import annotations

import json

import pytest

import config
from engine.templates.world_content_pack import (
    apply_dataset_import,
    build_entity_prompt,
    build_full_dataset_prompt,
    normalize_world_dataset,
    validate_world_dataset,
)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "WORLD_PACK_PATH", tmp_path / "world_pack.yaml")
    monkeypatch.setattr(config, "CONTENT_TEMPLATES_PATH", tmp_path / "content_templates.json")
    monkeypatch.setattr(config, "CONTENT_TEMPLATES_DEFAULT_PATH", config.CONTENT_TEMPLATES_DEFAULT_PATH)
    monkeypatch.setattr(config, "WORLD_CONTENT_PACK_PATH", config.WORLD_CONTENT_PACK_PATH)
    return tmp_path


@pytest.fixture
def sample_dataset():
    return {
        "characters": [
            {
                "entity_type": "character",
                "name": "沈砚",
                "archetype": "冷面贵族",
                "role": "内阁学士",
                "faction": "枢机院",
                "visual_identity_hint": "墨色长袍，冷峻眉眼",
                "personality_axis": ["克制", "理性"],
                "conflict_vector": "忠诚 vs 野心",
                "signature_trait": "永远先观察再开口",
                "visual_keywords": ["muted gold trim", "ink wash tone"],
                "scene_usage": "conflict",
            },
            {
                "entity_type": "character",
                "name": "顾青璃",
                "archetype": "失势公主",
                "role": "流亡王女",
                "faction": "流亡王室",
                "visual_identity_hint": "残旧礼服与坚韧目光",
                "personality_axis": ["高贵", "隐忍"],
                "conflict_vector": "尊严 vs 生存",
                "signature_trait": "微笑从不达眼底",
                "visual_keywords": ["elegant decay", "silver hair motif"],
                "scene_usage": "intro",
            },
        ],
        "locations": [
            {
                "entity_type": "location",
                "name": "霜华宫",
                "type": "palace",
                "function_in_world": "权力中心",
                "dominant_materials": ["stone", "wood", "silk"],
                "atmosphere": "庄严压迫",
                "visual_keywords": ["symmetry", "throne hall"],
                "story_role": "宫廷冲突主舞台",
            },
        ],
        "factions": [
            {
                "entity_type": "faction",
                "name": "枢机院",
                "ideology": "秩序优先",
                "structure": "元老议会",
                "public_face": "合法统治",
                "hidden_goal": "控制继承序列",
                "visual_identity": "青铜鹰徽与深蓝纹章",
                "key_symbols": ["eagle crest", "deep blue banner"],
            },
        ],
        "events": [
            {
                "entity_type": "event",
                "title": "宫门夜议",
                "type": "political",
                "trigger": "继承权争议公开化",
                "participants": ["沈砚", "顾青璃"],
                "location": "霜华宫",
                "conflict": "公开质询 vs 沉默回避",
                "outcome_state": "紧张升级",
                "visual_focus": "长廊烛火与对峙剪影",
                "emotion_tone": "tense",
                "scene_prompt_hint": "cinematic corridor lighting, two-figure standoff",
            },
        ],
    }


def test_build_character_prompt():
    prompt = build_entity_prompt("character", 5)
    assert "Generate characters" in prompt or "Generate" in prompt
    assert "5" in prompt
    assert "archetype" in prompt


def test_build_full_dataset_prompt():
    prompt = build_full_dataset_prompt({"characters": 3, "locations": 2, "events": 2, "factions": 1})
    assert "V6-compliant IP dataset" in prompt
    assert "3" in prompt
    assert "Style Bible" in prompt


def test_validate_sample_dataset(sample_dataset):
    report = validate_world_dataset(sample_dataset)
    assert report["valid"] is True
    assert not report["errors"]


def test_validate_rejects_duplicate_archetype(sample_dataset):
    bad = json.loads(json.dumps(sample_dataset))
    bad["characters"][1]["archetype"] = bad["characters"][0]["archetype"]
    report = validate_world_dataset(bad)
    assert report["valid"] is False
    assert any("duplicate archetype" in e for e in report["errors"])


def test_validate_rejects_drift_marker(sample_dataset):
    bad = json.loads(json.dumps(sample_dataset))
    bad["locations"][0]["visual_keywords"].append("cyberpunk neon city")
    report = validate_world_dataset(bad)
    assert report["valid"] is False
    assert any("style drift" in e for e in report["errors"])


def test_import_merges_world_and_templates(env, sample_dataset):
    from engine import io_utils

    result = apply_dataset_import(sample_dataset, persist=True)
    assert result["imported"] is True
    world = io_utils.read_yaml(env / "world_pack.yaml")
    assert len(world["world"]["characters"]) == 2
    assert "霜华宫" in [l["name"] for l in world["world"]["locations"]]
    templates = io_utils.read_json(env / "content_templates.json")
    assert "沈砚" in templates["characters"]
    assert "宫门夜议" in templates["events"]


def test_normalize_world_dataset(sample_dataset):
    ds = normalize_world_dataset(sample_dataset)
    assert ds["characters"][0]["role"] == "内阁学士"
    assert ds["locations"][0]["dominant_materials"] == ["stone", "wood", "silk"]
