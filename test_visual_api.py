"""V6.5 read-only Visual API tests."""

from __future__ import annotations

import pytest

import config
from engine.visual.asset_manager import get_or_request_character_portrait, reset_visual_assets
from engine.visual.visual_api import (
    get_character_gallery,
    get_event_timeline,
    get_visual_debug_payload,
    get_visual_status,
    get_world_explorer,
)
from engine.visual.visual_provider import MockVisualProvider


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
    monkeypatch.setattr(config, "SESSION_STATE_PATH", tmp_path / "session_state.yaml")
    monkeypatch.setattr(config, "RELATIONSHIP_GRAPH_PATH", tmp_path / "relationship_graph.json")
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


def test_visual_status_read_only():
    status = get_visual_status()
    assert status["read_only"] is True
    assert "provider" in status


def test_character_gallery_identity_view(visual_env, world_pack):
    get_or_request_character_portrait("长公主", world_pack, provider=MockVisualProvider())
    gallery = get_character_gallery()
    assert len(gallery) >= 1
    view = gallery[0]
    assert view["identity_id"].startswith("vid_")
    assert view["entity_name"] == "长公主"
    assert view["latest_image"]
    assert len(view["all_assets"]) >= 1
    assert view["traits"].get("hair_color") == "silver"


def test_world_explorer_structure(visual_env, world_pack):
    get_or_request_character_portrait("长公主", world_pack, provider=MockVisualProvider())
    world = get_world_explorer()
    assert "locations" in world
    assert "factions" in world
    assert "characters" in world
    assert "character_links" in world
    assert isinstance(world["character_links"], list)


def test_event_timeline_sorted(visual_env, world_pack):
    from engine.visual.visual_runtime import get_visual

    get_visual("event", "evt_a", {"scene": "夜宴"}, turn=1, provider=MockVisualProvider())
    get_visual("event", "evt_b", {"scene": "密谈"}, turn=3, provider=MockVisualProvider())
    events = get_event_timeline()
    assert len(events) >= 2
    turns = [e["created_turn"] for e in events]
    assert turns == sorted(turns)
    assert events[0]["event_id"]
    assert "scene_images" in events[0]
    assert "linked_assets" in events[0]


def test_debug_panel_fields(visual_env, world_pack):
    get_or_request_character_portrait("长公主", world_pack, provider=MockVisualProvider())
    debug = get_visual_debug_payload()
    assert debug["assets"]
    asset = debug["assets"][0]
    for key in ("identity_id", "prompt_hash", "seed", "provider", "cache_hit", "registry_id"):
        assert key in asset
    assert asset["cache_hit"] is True
