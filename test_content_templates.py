"""Content Template System (IP layer) tests."""

from __future__ import annotations

import pytest

import config
from engine.templates.template_prompt import build_prompt_from_template
from engine.templates.template_registry import get_entity_template, get_style_bible, load_content_templates
from engine.templates.template_resolver import resolve_content_template
from engine.visual.asset_manager import reset_visual_assets
from engine.visual.identity_registry import resolve_identity
from engine.visual.identity_prompt_builder import build_identity_prompt
from engine.visual.visual_identity import VisualIdentity
from engine.visual.visual_provider import MockVisualProvider
from engine.visual.visual_runtime import get_visual


@pytest.fixture
def tpl_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "VISUAL_REGISTRY_PATH", tmp_path / "visual_registry.json")
    monkeypatch.setattr(
        config, "VISUAL_IDENTITY_REGISTRY_PATH", tmp_path / "visual_identity_registry.json",
    )
    monkeypatch.setattr(config, "CONTENT_TEMPLATES_PATH", tmp_path / "content_templates.json")
    monkeypatch.setattr(config, "CONTENT_TEMPLATES_DEFAULT_PATH", config.CONTENT_TEMPLATES_DEFAULT_PATH)
    monkeypatch.setattr(config, "VISUAL_OUTPUT_DIR", tmp_path / "output" / "visual")
    monkeypatch.setattr(config, "NARRATIVE_STATE_PATH", tmp_path / "narrative_state.json")
    monkeypatch.setattr(config, "NARRATIVE_ROUTES_PATH", tmp_path / "narrative_routes.json")
    monkeypatch.setattr(config, "CONTENT_TEMPLATE_SYSTEM_ENABLED", True)
    monkeypatch.setattr(config, "VISUAL_SYSTEM_ENABLED", True)
    reset_visual_assets()
    return tmp_path


@pytest.fixture
def world_pack():
    return {
        "world": {
            "title": "测试王国",
            "main_goal": "调查灭门案",
            "characters": [
                {
                    "name": "长公主",
                    "role": "公主",
                    "gender": "female",
                    "hair_color": "silver",
                    "outfit": "royal dress",
                    "personality_tags": ["noble", "elegant"],
                },
            ],
        },
    }


def test_character_template_inferred_and_locked(tpl_env, world_pack):
    tpl = resolve_content_template("character", "长公主", {"world_pack": world_pack})
    assert tpl["name"] == "长公主"
    assert tpl.get("archetype")
    assert tpl.get("conflict_vector")
    assert tpl.get("visual_keywords")

    again = resolve_content_template("character", "长公主", {"world_pack": world_pack})
    assert again["archetype"] == tpl["archetype"]


def test_build_prompt_from_template_merges_identity(tpl_env, world_pack):
    identity = resolve_identity("character", "长公主", {"world_pack": world_pack})
    tpl = resolve_content_template("character", "长公主", {"world_pack": world_pack})
    prompt = build_prompt_from_template(tpl, identity, base_prompt="entity: 长公主")
    assert "world_tone" in prompt or "style:" in prompt
    assert "archetype:" in prompt
    assert "entity: 长公主" in prompt


def test_identity_prompt_includes_template_layer(tpl_env, world_pack):
    identity = resolve_identity("character", "长公主", {"world_pack": world_pack})
    prompt = build_identity_prompt(identity, {"world_pack": world_pack})
    assert "archetype:" in prompt
    bible = get_style_bible()
    if bible.get("world_tone"):
        assert "world_tone:" in prompt


def test_style_bible_loaded(tpl_env):
    bible = get_style_bible()
    assert "visual_language" in bible


def test_template_persists_in_registry(tpl_env, world_pack):
    resolve_content_template("character", "长公主", {"world_pack": world_pack})
    reg = load_content_templates()
    assert "长公主" in reg["characters"]
    assert get_entity_template("character", "长公主")


def test_visual_generation_uses_template_prompt(tpl_env, world_pack):
    r = get_visual("character", "长公主", {"world_pack": world_pack}, provider=MockVisualProvider())
    assert r.get("prompt_hash")
    identity = resolve_identity("character", "长公主", {"world_pack": world_pack})
    prompt = build_identity_prompt(identity, {"world_pack": world_pack})
    assert "archetype:" in prompt
