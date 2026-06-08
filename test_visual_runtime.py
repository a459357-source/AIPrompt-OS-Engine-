"""V6 Visual Runtime — convergence tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

import config
from engine.visual.asset_manager import reset_visual_assets
from engine.visual.prompt_canonical import normalize_prompt
from engine.visual.visual_cache import canonical_prompt_hash, exists, memory_get
from engine.visual.visual_object import build_visual_object
from engine.visual.visual_provider import MockVisualProvider, StubVisualProvider
from engine.visual.visual_runtime import get_visual


@pytest.fixture
def visual_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "VISUAL_REGISTRY_PATH", tmp_path / "visual_registry.json")
    monkeypatch.setattr(config, "VISUAL_OUTPUT_DIR", tmp_path / "output" / "visual")
    monkeypatch.setattr(config, "VISUAL_SYSTEM_ENABLED", True)
    monkeypatch.setattr(config, "VISUAL_CACHE_ENABLED", True)
    monkeypatch.setattr(config, "VISUAL_MAX_RETRIES", 2)
    reset_visual_assets()
    return tmp_path


@pytest.fixture
def world_pack():
    return {
        "world": {
            "title": "测试王国",
            "regions": ["皇都", "北境"],
            "characters": [
                {"name": "长公主", "gender": "female", "hair_color": "silver"},
            ],
        },
    }


@pytest.fixture
def memory():
    return {
        "factions": {
            "北境军": {"type": "military", "controlledTerritories": ["北境关隘"]},
        },
    }


def test_normalize_prompt_stable_hash():
    a = normalize_prompt("beautiful girl, anime style")
    b = normalize_prompt("anime style, girl, beautiful")
    assert a == b
    assert canonical_prompt_hash(a) == canonical_prompt_hash(b)


def test_visual_object_fields(visual_env, world_pack):
    obj = build_visual_object("character", "长公主", {"world_pack": world_pack})
    assert obj.entity_type == "character"
    assert obj.entity_id == "长公主"
    assert obj.identity_id.startswith("vid_")
    assert obj.seed > 0
    assert obj.prompt
    assert obj.prompt_hash
    assert obj.idempotency_key.startswith("character:")


def test_get_visual_four_entity_types(visual_env, world_pack, memory):
    mock = MockVisualProvider()
    char = get_visual("character", "长公主", {"world_pack": world_pack}, provider=mock)
    loc = get_visual("location", "测试王国", {"world_pack": world_pack}, provider=mock)
    fac = get_visual("faction", "北境军", {"memory": memory}, provider=mock)
    evt = get_visual("event", "palace_night", {"scene": "皇宫深夜"}, provider=mock)

    assert char["entity_type"] == "character"
    assert loc["entity_type"] == "location"
    assert fac["entity_type"] == "faction"
    assert evt["entity_type"] == "event"
    assert exists("characters", char["asset_id"])
    assert exists("locations", loc["asset_id"])
    assert exists("factions", fac["asset_id"])
    assert exists("events", evt["asset_id"])


def test_l1_memory_cache_hit(visual_env, world_pack):
    mock = MockVisualProvider()
    r1 = get_visual("character", "长公主", {"world_pack": world_pack}, provider=mock)
    calls = 0
    original = mock.generate_character

    def counting(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    mock.generate_character = counting  # type: ignore[method-assign]
    r2 = get_visual("character", "长公主", {"world_pack": world_pack}, provider=mock)
    assert r2["asset_id"] == r1["asset_id"]
    assert calls == 0
    assert memory_get(r1.get("prompt_hash", "")) is None  # keyed by idempotency_key
    obj = build_visual_object("character", "长公主", {"world_pack": world_pack})
    assert memory_get(obj.idempotency_key) is not None


def test_provider_fallback_to_stub(visual_env, world_pack):
    mock = MockVisualProvider()

    def boom(**kwargs):
        raise RuntimeError("provider down")

    mock.generate_character = boom  # type: ignore[method-assign]
    r = get_visual("character", "长公主", {"world_pack": world_pack}, provider=mock)
    assert r["provider"] == "stub"
    assert r["image_path"]


def test_agnes_runtime_fallback(visual_env, world_pack, monkeypatch):
    from engine.visual.agnes_visual_provider import AgnesVisualProvider

    monkeypatch.setattr(config, "VISUAL_MAX_RETRIES", 1)
    provider = AgnesVisualProvider(api_key="k", api_base="https://agnes.test/v1")
    bad = type("R", (), {"status_code": 500, "text": "err", "json": lambda self: {}})()
    with patch("engine.visual.agnes_visual_provider.requests.post", return_value=bad):
        r = get_visual("character", "长公主", {"world_pack": world_pack}, provider=provider)
    assert r["provider"] == "stub"


def test_invalid_entity_type_raises(world_pack):
    with pytest.raises(ValueError):
        get_visual("vehicle", "car", {})
