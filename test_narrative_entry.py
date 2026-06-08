"""V6.6 Narrative Entry Layer tests."""

from __future__ import annotations

import pytest

import config
from engine.narrative.narrative_entry import build_narrative_node
from engine.narrative.narrative_router import get_choices_for_event, route_choice
from engine.narrative.narrative_state import load_narrative_state, set_narrative_mode
from engine.visual.asset_manager import reset_visual_assets
from engine.visual.visual_runtime import get_visual
from engine.visual.visual_provider import MockVisualProvider


@pytest.fixture
def narrative_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "VISUAL_REGISTRY_PATH", tmp_path / "visual_registry.json")
    monkeypatch.setattr(
        config, "VISUAL_IDENTITY_REGISTRY_PATH", tmp_path / "visual_identity_registry.json",
    )
    monkeypatch.setattr(config, "VISUAL_OUTPUT_DIR", tmp_path / "output" / "visual")
    monkeypatch.setattr(config, "NARRATIVE_STATE_PATH", tmp_path / "narrative_state.json")
    monkeypatch.setattr(config, "NARRATIVE_ROUTES_PATH", tmp_path / "narrative_routes.json")
    monkeypatch.setattr(config, "NARRATIVE_ROUTES_DEFAULT_PATH", config.NARRATIVE_ROUTES_DEFAULT_PATH)
    monkeypatch.setattr(config, "NARRATIVE_STATE_DEFAULT_PATH", config.NARRATIVE_STATE_DEFAULT_PATH)
    monkeypatch.setattr(config, "SESSION_STATE_PATH", tmp_path / "session_state.yaml")
    monkeypatch.setattr(config, "DIRECTOR_STATE_PATH", tmp_path / "director_state.json")
    monkeypatch.setattr(config, "VISUAL_SYSTEM_ENABLED", True)
    reset_visual_assets()
    set_narrative_mode("explore")
    return tmp_path


def test_narrative_node_has_scene_and_choices(narrative_env):
    node = build_narrative_node("midnight_talk")
    assert node["event_id"] == "midnight_talk"
    assert node["context"]
    assert len(node["choices"]) >= 2
    assert "continuity" in node
    assert node["continuity"]["identity_ids"] is not None


def test_route_choice_maps_next_event(narrative_env):
    result = route_choice("midnight_talk", "c1")
    assert result["ok"] is True
    assert result["next_event_id"] == "confession"


def test_visual_event_entry_with_asset(narrative_env):
    get_visual("event", "palace_scene", {"scene": "皇宫夜宴"}, provider=MockVisualProvider())
    node = build_narrative_node("midnight_talk", visual_event_id="palace_scene")
    assert node["scene_image"] or node["visual_asset_id"]


def test_mode_switch_independent(narrative_env):
    set_narrative_mode("narrative")
    state = load_narrative_state()
    assert state["mode"] == "narrative"
    set_narrative_mode("explore")
    assert load_narrative_state()["mode"] == "explore"


def test_choices_structure(narrative_env):
    choices = get_choices_for_event("midnight_talk")
    assert choices[0]["choice_id"]
    assert choices[0]["text"]
    assert choices[0]["target_event_id"]
