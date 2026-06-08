"""Style Bible v1 prompt constraint layer tests."""

from __future__ import annotations

import pytest

import config
from engine.templates.style_bible import apply_style_bible, style_tokens_for_entity
from engine.visual.asset_manager import reset_visual_assets
from engine.visual.identity_prompt_builder import build_identity_prompt
from engine.visual.identity_registry import resolve_identity
from engine.visual.visual_provider import MockVisualProvider
from engine.visual.visual_runtime import get_visual


@pytest.fixture
def env(tmp_path, monkeypatch):
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
    monkeypatch.setattr(config, "STYLE_BIBLE_V1_ENABLED", True)
    monkeypatch.setattr(config, "VISUAL_SYSTEM_ENABLED", True)
    reset_visual_assets()
    return tmp_path


@pytest.fixture
def world_pack():
    return {
        "world": {
            "characters": [
                {"name": "长公主", "role": "公主", "gender": "female", "hair_color": "silver"},
            ],
        },
    }


def test_apply_style_bible_prepends_constraints():
    base = "beautiful princess, palace, sunset"
    out = apply_style_bible(base, "character")
    assert "cinematic lighting" in out
    assert "clear silhouette design" in out
    assert base in out
    assert out.index("cinematic lighting") < out.index("beautiful princess")


def test_entity_style_binding_differs_by_type():
    char_tokens = style_tokens_for_entity("character")
    loc_tokens = style_tokens_for_entity("location")
    assert "clear silhouette design" in char_tokens
    assert "architectural coherence" in loc_tokens
    assert char_tokens != loc_tokens


def test_style_bible_does_not_remove_identity_semantics(world_pack, env):
    identity = resolve_identity("character", "长公主", {"world_pack": world_pack})
    prompt = build_identity_prompt(identity, {"world_pack": world_pack})
    assert "entity: 长公主" in prompt
    assert "seed:" in prompt
    assert "cinematic lighting" in prompt


def test_all_assets_pass_through_style_bible(world_pack, env):
    mock = MockVisualProvider()
    get_visual("character", "长公主", {"world_pack": world_pack}, provider=mock)
    identity = resolve_identity("character", "长公主", {"world_pack": world_pack})
    prompt = build_identity_prompt(identity, {"world_pack": world_pack})
    assert "coherent visual identity" in prompt


def test_style_bible_disabled_skips_injection(world_pack, env, monkeypatch):
    monkeypatch.setattr(config, "STYLE_BIBLE_V1_ENABLED", False)
    identity = resolve_identity("character", "长公主", {"world_pack": world_pack})
    prompt = build_identity_prompt(identity, {"world_pack": world_pack})
    assert "cinematic lighting" not in prompt
    assert "entity: 长公主" in prompt
