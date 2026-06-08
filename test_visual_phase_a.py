"""V6.0 Visual Narrative System — Phase A tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import config
from engine.visual.asset_manager import (
    get_or_request_character_portrait,
    get_or_request_faction_map,
    get_or_request_scene_image,
    get_or_request_world_map,
    reset_visual_assets,
)
from engine.visual.agnes_visual_provider import AgnesNotConfiguredError, AgnesVisualProvider
from engine.visual.visual_cache import exists, prompt_hash
from engine.visual.provider_factory import get_visual_provider
from engine.visual.visual_provider import MockVisualProvider, StubVisualProvider
from engine.visual.visual_registry import load_registry, normalize_asset_id, save_registry, set_asset


@pytest.fixture
def visual_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "VISUAL_REGISTRY_PATH", tmp_path / "visual_registry.json")
    monkeypatch.setattr(config, "VISUAL_OUTPUT_DIR", tmp_path / "output" / "visual")
    monkeypatch.setattr(config, "VISUAL_SYSTEM_ENABLED", True)
    monkeypatch.setattr(config, "VISUAL_CACHE_ENABLED", True)
    monkeypatch.setattr(config, "SESSION_STATE_PATH", tmp_path / "session_state.yaml")
    monkeypatch.setattr(config, "MEMORY_PATH", tmp_path / "memory.json")
    monkeypatch.setattr(config, "STORY_GRAPH_PATH", tmp_path / "story_graph.json")
    monkeypatch.setattr(config, "WORLD_PACK_PATH", tmp_path / "world_pack.yaml")
    monkeypatch.setattr(config, "SAVES_DIR", tmp_path / "saves")
    monkeypatch.setattr(config, "RELATIONSHIP_GRAPH_PATH", tmp_path / "relationship_graph.json")
    monkeypatch.setattr(config, "RELATIONSHIP_MEMORY_PATH", tmp_path / "relationship_memory.json")
    monkeypatch.setattr(config, "RELATIONSHIP_DYNAMICS_PATH", tmp_path / "relationship_dynamics.json")
    monkeypatch.setattr(config, "PLOT_STATE_PATH", tmp_path / "plot_state.json")
    monkeypatch.setattr(config, "CANDIDATE_NPCS_PATH", tmp_path / "candidate_npcs.json")
    monkeypatch.setattr(config, "CHAPTER_PATH", tmp_path / "chapter.md")
    monkeypatch.setattr(config, "EVENT_HISTORY_PATH", tmp_path / "event_history.json")
    monkeypatch.setattr(config, "DIRECTOR_STATE_PATH", tmp_path / "director_state.json")
    reset_visual_assets()
    return tmp_path


@pytest.fixture
def world_pack():
    return {
        "world": {
            "title": "测试王国",
            "main_goal": "调查灭门案",
            "regions": ["皇都", "北境", "南疆"],
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


@pytest.fixture
def memory():
    return {
        "factions": {
            "北境军": {
                "type": "military",
                "goals": ["夺取边境"],
                "controlledTerritories": ["北境关隘"],
            },
        },
    }


def test_visual_registry_module_exists():
    assert Path("engine/visual/visual_registry.py").exists()
    assert Path("engine/visual/asset_manager.py").exists()


def test_visual_provider_interface():
    stub = StubVisualProvider()
    assert stub.provider_name == "stub"
    assert len(stub.generate_character_portrait(prompt="p", asset_id="a")) > 0
    assert len(stub.generate_scene_image(prompt="p", asset_id="a")) > 0
    assert len(stub.generate_world_map(prompt="p", asset_id="a")) > 0
    assert len(stub.generate_faction_map(prompt="p", asset_id="a")) > 0


def test_character_portrait(visual_env, world_pack):
    mock = MockVisualProvider()
    r1 = get_or_request_character_portrait("长公主", world_pack, provider=mock)
    assert r1["kind"] == "portrait"
    assert r1["provider"] == "mock"
    assert exists("characters", r1["asset_id"])

    r2 = get_or_request_character_portrait("长公主", world_pack, provider=mock)
    assert r2["asset_id"] == r1["asset_id"]
    assert r2["prompt_hash"] == r1["prompt_hash"]


def test_scene_image(visual_env, world_pack):
    mock = MockVisualProvider()
    r = get_or_request_scene_image(
        "palace_night",
        {"scene": "皇宫深夜", "location": "皇都", "story_summary": "密谈"},
        provider=mock,
    )
    assert r["kind"] == "scene"
    assert exists("scenes", r["asset_id"])


def test_world_map(visual_env, world_pack):
    mock = MockVisualProvider()
    r = get_or_request_world_map(world_pack, provider=mock)
    assert r["kind"] == "world_map"
    assert exists("locations", r["asset_id"])


def test_faction_map(visual_env, memory):
    mock = MockVisualProvider()
    r = get_or_request_faction_map("北境军", memory, provider=mock)
    assert r["kind"] == "faction_map"
    assert exists("factions", r["asset_id"])


def test_registry_persistence(visual_env, world_pack):
    mock = MockVisualProvider()
    get_or_request_character_portrait("长公主", world_pack, provider=mock)
    reg = load_registry()
    assert reg["characters"]


def test_agnes_not_available_without_api_key():
    with pytest.raises(AgnesNotConfiguredError):
        AgnesVisualProvider(api_key="")


def test_save_slot_metadata_only_no_image_bytes(visual_env, world_pack):
    import yaml
    from engine import io_utils
    from engine.save_manager import load as load_save, save as save_slot

    (visual_env / "session_state.yaml").write_text(
        yaml.dump({"turn": 3, "status": "BUILD", "scene": "测试", "characters": {}}, allow_unicode=True),
        encoding="utf-8",
    )
    (visual_env / "world_pack.yaml").write_text(
        yaml.dump(world_pack, allow_unicode=True), encoding="utf-8",
    )
    io_utils.write_json(visual_env / "memory.json", {"characters": {}, "factions": {}})
    io_utils.write_json(visual_env / "story_graph.json", {"nodes": [], "edges": []})
    io_utils.write_json(visual_env / "relationship_graph.json", {"version": 1, "nodes": {}, "edges": {}, "events": [], "pending_events": []})
    io_utils.write_json(visual_env / "relationship_memory.json", {"version": 1, "edges": {}})
    io_utils.write_json(visual_env / "relationship_dynamics.json", {"version": 1, "edges": {}, "triangles": []})
    io_utils.write_json(visual_env / "plot_state.json", {"main_plot": {"progress": 0, "stage": 1, "name": "x"}, "unresolved_hooks": []})
    io_utils.write_json(visual_env / "candidate_npcs.json", {})

    get_or_request_character_portrait("长公主", world_pack, provider=MockVisualProvider())
    assert save_slot("slot1") is not None

    slot_raw = (visual_env / "saves" / "slot1.json").read_text(encoding="utf-8")
    assert "base64" not in slot_raw.lower()
    assert "iVBOR" not in slot_raw  # common PNG b64 prefix
    snapshot = json.loads(slot_raw)
    assert "visual_registry" in snapshot
    assert snapshot["visual_registry"]["characters"]

    reset_visual_assets()
    assert load_save("slot1") is not None
    reg = load_registry()
    assert reg["characters"]


def test_reset_clears_registry(visual_env, world_pack):
    get_or_request_character_portrait("长公主", world_pack, provider=StubVisualProvider())
    assert load_registry()["characters"]
    reset_visual_assets()
    assert load_registry()["characters"] == {}


def test_no_dual_visual_implementations():
    visual_dir = Path("engine/visual")
    forbidden = (
        "StoryPortrait", "AdultPortrait", "StoryMap", "AdultMap",
        "StoryScene", "AdultScene",
    )
    for py in visual_dir.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        for name in forbidden:
            assert name not in text, f"{name} in {py.name}"


def test_no_mode_layer_in_visual_code():
    visual_dir = Path("engine/visual")
    for py in visual_dir.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert "adult_mode" not in text
        assert "experience_mode" not in text
        assert "visual_theme" not in text


def test_normalize_asset_id_stable():
    assert normalize_asset_id("Princess") == "princess"
    a = normalize_asset_id("长公主")
    b = normalize_asset_id("长公主")
    assert a == b
    assert a.startswith("asset_")


def test_prompt_hash_deterministic():
    assert prompt_hash("hello") == prompt_hash("hello")
    assert prompt_hash("a") != prompt_hash("b")
