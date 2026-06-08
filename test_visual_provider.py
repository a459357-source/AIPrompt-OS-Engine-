"""V6.0 Phase B — VisualProvider / Factory / Cache tests."""

from __future__ import annotations

import base64
from unittest.mock import patch

import pytest

import config
from engine.visual.agnes_visual_provider import AgnesAPIError, AgnesNotConfiguredError, AgnesVisualProvider
from engine.visual.asset_manager import get_or_request_character_portrait
from engine.visual.provider_factory import get_visual_provider, list_visual_providers
from engine.visual.visual_cache import STUB_PNG_BYTES, exists, prompt_hash
from engine.visual.visual_provider import MockVisualProvider, StubVisualProvider
from engine.visual.visual_registry import find_by_prompt_hash, load_registry
from engine.visual.asset_manager import reset_visual_assets


@pytest.fixture
def visual_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "VISUAL_REGISTRY_PATH", tmp_path / "visual_registry.json")
    monkeypatch.setattr(config, "VISUAL_OUTPUT_DIR", tmp_path / "output" / "visual")
    monkeypatch.setattr(config, "VISUAL_SYSTEM_ENABLED", True)
    monkeypatch.setattr(config, "VISUAL_CACHE_ENABLED", True)
    reset_visual_assets()
    return tmp_path


@pytest.fixture
def world_pack():
    return {
        "world": {
            "characters": [{"name": "长公主", "gender": "female", "hair_color": "silver"}],
        },
    }


def test_provider_factory_stub():
    p = get_visual_provider("stub")
    assert isinstance(p, StubVisualProvider)
    assert p.provider_name == "stub"


def test_provider_factory_mock():
    p = get_visual_provider("mock")
    assert isinstance(p, MockVisualProvider)


def test_provider_factory_agnes_requires_key(monkeypatch):
    monkeypatch.setattr(config, "get_agnes_api_key", lambda: "")
    with pytest.raises(AgnesNotConfiguredError):
        get_visual_provider("agnes")


def test_provider_factory_agnes_with_key(monkeypatch):
    monkeypatch.setattr(config, "get_agnes_api_key", lambda: "test-key")
    monkeypatch.setattr(config, "get_agnes_api_base", lambda: "https://agnes.test/v1")
    p = get_visual_provider("agnes")
    assert isinstance(p, AgnesVisualProvider)
    assert p.provider_name == "agnes"


def test_factory_lists_providers():
    names = list_visual_providers()
    assert "stub" in names
    assert "agnes" in names


def test_cache_miss_then_hit(visual_env, world_pack):
    mock = MockVisualProvider()
    r1 = get_or_request_character_portrait("长公主", world_pack, provider=mock)
    assert r1["image_path"]
    assert exists("characters", r1["asset_id"])

    calls = 0
    original = mock.generate_character

    def counting(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    mock.generate_character = counting  # type: ignore[method-assign]
    r2 = get_or_request_character_portrait("长公主", world_pack, provider=mock)
    assert r2["asset_id"] == r1["asset_id"]
    assert calls == 0


def test_prompt_hash_cache_reuse(visual_env, world_pack):
    mock = MockVisualProvider()
    r1 = get_or_request_character_portrait("长公主", world_pack, provider=mock)
    reg = load_registry()
    assert find_by_prompt_hash(reg, "characters", r1["prompt_hash"])

    # different display id, same prompt via duplicate character entry
    wp2 = {
        "world": {
            "characters": [{"name": "长公主", "gender": "female", "hair_color": "silver"}],
        },
    }
    calls = 0
    original = mock.generate_character

    def counting(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    mock.generate_character = counting  # type: ignore[method-assign]
    r2 = get_or_request_character_portrait("长公主", wp2, provider=mock)
    assert r2["prompt_hash"] == r1["prompt_hash"]
    assert calls == 0


def test_registry_write_fields(visual_env, world_pack):
    r = get_or_request_character_portrait("长公主", world_pack, provider=StubVisualProvider())
    for key in ("asset_id", "entity_id", "prompt_hash", "image_path", "provider", "created_at"):
        assert key in r
    assert r["provider"] == "stub"
    reg = load_registry()
    assert reg["characters"][r["asset_id"]]["image_path"]


def test_agnes_mock_api(visual_env):
    provider = AgnesVisualProvider(api_key="k", api_base="https://agnes.test/v1")
    b64 = base64.b64encode(STUB_PNG_BYTES).decode("ascii")
    fake_resp = type("R", (), {"status_code": 200, "text": "{}", "json": lambda self: {"data": [{"b64_json": b64}]}})()

    with patch("engine.visual.agnes_visual_provider.requests.post", return_value=fake_resp):
        data = provider.generate_character(prompt="test", asset_id="hero")
    assert len(data) > 0
    assert data[:8] == STUB_PNG_BYTES[:8]


def test_agnes_api_error(visual_env):
    provider = AgnesVisualProvider(api_key="k", api_base="https://agnes.test/v1")
    bad = type("R", (), {"status_code": 500, "text": "err", "json": lambda self: {}})()
    with patch("engine.visual.agnes_visual_provider.requests.post", return_value=bad):
        with pytest.raises(AgnesAPIError):
            provider.generate_event(prompt="x", asset_id="y")


def test_no_mode_layer_in_factory_and_agnes():
    from pathlib import Path
    root = Path(__file__).resolve().parent / "engine" / "visual"
    for name in ("provider_factory.py", "agnes_visual_provider.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "adult_mode" not in text
        assert "experience_mode" not in text
        assert "visual_theme" not in text


def test_business_uses_factory_not_agnes_import():
    import ast
    from pathlib import Path
    asset_mgr = Path("engine/visual/asset_manager.py").read_text(encoding="utf-8")
    assert "agnes_visual_provider" not in asset_mgr
    tree = ast.parse(asset_mgr)
    imports = [
        node.names[0].name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and "agnes" in node.module
    ]
    assert imports == []
