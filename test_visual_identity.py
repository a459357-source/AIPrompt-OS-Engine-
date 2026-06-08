"""V6.1 Visual Identity Layer tests."""

from __future__ import annotations

import pytest

import config
from engine.visual.asset_manager import reset_visual_assets
from engine.visual.identity_registry import load_identity_registry, resolve_identity
from engine.visual.prompt_canonical import normalize_prompt
from engine.visual.visual_cache import canonical_prompt_hash
from engine.visual.visual_provider import MockVisualProvider
from engine.visual.visual_runtime import get_visual


@pytest.fixture
def visual_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "VISUAL_REGISTRY_PATH", tmp_path / "visual_registry.json")
    monkeypatch.setattr(
        config, "VISUAL_IDENTITY_REGISTRY_PATH", tmp_path / "visual_identity_registry.json",
    )
    monkeypatch.setattr(config, "VISUAL_OUTPUT_DIR", tmp_path / "output" / "visual")
    monkeypatch.setattr(config, "VISUAL_SYSTEM_ENABLED", True)
    monkeypatch.setattr(config, "VISUAL_CACHE_ENABLED", True)
    reset_visual_assets()
    return tmp_path


@pytest.fixture
def world_pack():
    return {
        "world": {
            "title": "测试王国",
            "characters": [
                {
                    "name": "长公主",
                    "gender": "female",
                    "hair_color": "silver",
                    "outfit": "royal dress",
                    "personality_tags": ["elegant", "noble"],
                },
            ],
        },
    }


def test_identity_created_and_locked(visual_env, world_pack):
    identity = resolve_identity("character", "长公主", {"world_pack": world_pack})
    assert identity.identity_id.startswith("vid_")
    assert identity.seed > 0
    assert identity.canonical_traits.get("hair_color") == "silver"
    assert "character: 长公主" in identity.locked_descriptors

    identity2 = resolve_identity("character", "长公主", {"world_pack": world_pack})
    assert identity2.identity_id == identity.identity_id
    assert identity2.canonical_traits == identity.canonical_traits


def test_same_character_five_generations_same_visual(visual_env, world_pack):
    mock = MockVisualProvider()
    results = []
    for i in range(5):
        r = get_visual(
            "character",
            "长公主",
            {"world_pack": world_pack, "scene": f"event_{i}", "mood": f"mood_{i}"},
            provider=mock,
        )
        results.append(r)

    hashes = {r["prompt_hash"] for r in results}
    assets = {r["asset_id"] for r in results}
    paths = {r["image_path"] for r in results}
    identities = {r["identity_id"] for r in results}

    assert len(hashes) == 1
    assert len(assets) == 1
    assert len(paths) == 1
    assert len(identities) == 1
    assert all(r["identity_id"] for r in results)


def test_event_context_does_not_change_character_appearance(visual_env, world_pack):
    mock = MockVisualProvider()
    r_plain = get_visual("character", "长公主", {"world_pack": world_pack}, provider=mock)
    r_event = get_visual(
        "character",
        "长公主",
        {
            "world_pack": world_pack,
            "scene": "皇宫血战",
            "location": "皇都",
            "story_summary": "完全不同的剧情上下文",
        },
        provider=mock,
    )
    assert r_event["prompt_hash"] == r_plain["prompt_hash"]
    assert r_event["asset_id"] == r_plain["asset_id"]
    assert r_event["identity_id"] == r_plain["identity_id"]


def test_identity_in_registry_traceable(visual_env, world_pack):
    get_visual("character", "长公主", {"world_pack": world_pack}, provider=MockVisualProvider())
    reg = load_identity_registry()
    assert reg["entity_index"].get("character:长公主")
    iid = reg["entity_index"]["character:长公主"]
    assert iid in reg["identities"]


def test_cache_hit_preserves_identity(visual_env, world_pack):
    mock = MockVisualProvider()
    r1 = get_visual("character", "长公主", {"world_pack": world_pack}, provider=mock)
    calls = 0
    original = mock.generate_character

    def counting(**kwargs):
        nonlocal calls
        calls += 1
        return original(**kwargs)

    mock.generate_character = counting  # type: ignore[method-assign]
    r2 = get_visual("character", "长公主", {"world_pack": world_pack}, provider=mock)
    assert calls == 0
    assert r2["identity_id"] == r1["identity_id"]


def test_stub_and_mock_same_identity_structure(visual_env, world_pack):
    from engine.visual.visual_provider import StubVisualProvider

    r_stub = get_visual("character", "长公主", {"world_pack": world_pack}, provider=StubVisualProvider())
    reset_visual_assets()
    r_mock = get_visual("character", "长公主", {"world_pack": world_pack}, provider=MockVisualProvider())
    for key in ("entity_type", "identity_id", "prompt_hash", "asset_id"):
        assert r_stub[key] == r_mock[key]


def test_identity_prompt_stable_despite_modifier_order(visual_env, world_pack):
    from engine.visual.identity_prompt_builder import build_identity_prompt

    identity = resolve_identity("character", "长公主", {"world_pack": world_pack})
    p1 = build_identity_prompt(identity, {"background": "night", "lighting": "soft"})
    p2 = build_identity_prompt(identity, {"lighting": "soft", "background": "night"})
    assert canonical_prompt_hash(normalize_prompt(p1)) == canonical_prompt_hash(normalize_prompt(p2))
