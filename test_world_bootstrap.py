"""V6 World Bootstrap tests."""

from __future__ import annotations

import json

import pytest

import config
from engine import io_utils
from engine.templates.world_bootstrap import (
    apply_bootstrap_import,
    build_bootstrap_prompt,
    build_world_seed,
    normalize_bootstrap_dataset,
    validate_bootstrap_dataset,
)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "WORLD_PACK_PATH", tmp_path / "world_pack.yaml")
    monkeypatch.setattr(config, "CONTENT_TEMPLATES_PATH", tmp_path / "content_templates.json")
    monkeypatch.setattr(config, "CONTENT_TEMPLATES_DEFAULT_PATH", config.CONTENT_TEMPLATES_DEFAULT_PATH)
    monkeypatch.setattr(config, "WORLD_CONTENT_PACK_PATH", config.WORLD_CONTENT_PACK_PATH)
    monkeypatch.setattr(config, "WORLD_BOOTSTRAP_PATH", tmp_path / "world_bootstrap.json")
    monkeypatch.setattr(config, "RELATIONSHIP_GRAPH_PATH", tmp_path / "relationship_graph.json")
    return tmp_path


@pytest.fixture
def bootstrap_dataset():
    return {
        "world": {
            "name": "PROJECT_V6_WORLD",
            "core_theme": "power under constraint",
            "visual_bible_anchor": ["cinematic lighting", "low saturation realism"],
            "dominant_material_system": ["stone", "steel", "dark wood"],
            "emotional_signature": "cold tension",
            "genre": "dark imperial fantasy",
            "tone": "cold, restrained, political tension",
        },
        "characters": [
            {
                "entity_type": "character",
                "name": "沈砚",
                "archetype": "冷面贵族",
                "faction": "枢机院",
                "role": "strategist",
                "conflict_vector": "loyalty vs survival",
                "visual_identity_hint": "dark uniform, restrained posture",
                "signature_trait": "never raises voice",
                "personality_axis": ["克制", "理性"],
                "visual_keywords": ["muted gold trim", "ink wash tone"],
                "linked_locations": ["霜华宫"],
                "linked_events": ["宫门夜议"],
            },
            {
                "entity_type": "character",
                "name": "顾青璃",
                "archetype": "失势公主",
                "faction": "流亡王室",
                "role": "exile princess",
                "conflict_vector": "dignity vs survival",
                "visual_identity_hint": "worn royal dress",
                "signature_trait": "smile never reaches eyes",
                "personality_axis": ["高贵", "隐忍"],
                "visual_keywords": ["elegant decay", "silver hair motif"],
            },
        ],
        "locations": [
            {
                "entity_type": "location",
                "name": "霜华宫",
                "type": "palace",
                "function_in_world": "authority hub",
                "dominant_materials": ["stone", "black marble"],
                "atmosphere": "silent pressure",
                "visual_keywords": ["symmetry", "cold light"],
                "story_role": "political center",
            },
        ],
        "factions": [
            {
                "entity_type": "faction",
                "name": "枢机院",
                "ideology": "order through control",
                "structure": "hierarchical bureaucracy",
                "public_face": "stability and justice",
                "hidden_goal": "absolute consolidation of power",
                "visual_identity": "black-gold formal aesthetics",
                "key_symbols": ["eagle crest"],
            },
            {
                "entity_type": "faction",
                "name": "流亡王室",
                "ideology": "legitimate succession",
                "structure": "exiled council",
                "public_face": "restoration hope",
                "hidden_goal": "reclaim throne by any means",
                "visual_identity": "faded silver crest",
                "key_symbols": ["broken crown"],
            },
        ],
        "events": [
            {
                "entity_type": "event",
                "title": "宫门夜议",
                "type": "political",
                "trigger": "succession rumors",
                "participants": ["沈砚", "顾青璃"],
                "location": "霜华宫",
                "linked_location": "霜华宫",
                "conflict": "succession dispute",
                "emotion_tone": "cold suspense",
                "visual_focus": "empty throne room",
                "outcome_state": "unstable equilibrium",
            },
        ],
        "relationships": [
            {
                "from": "沈砚",
                "to": "顾青璃",
                "type": "rival",
                "strength": 0.7,
                "status": "tense alliance",
            },
        ],
    }


def test_build_world_seed():
    seed = build_world_seed({"world_name": "TEST_WORLD", "tone": "cold tension"})
    assert seed["name"] == "TEST_WORLD"
    assert "cinematic lighting" in seed["visual_bible_anchor"]


def test_build_bootstrap_prompt():
    prompt = build_bootstrap_prompt({"world_name": "TEST_WORLD"})
    assert "V6 world initialization" in prompt
    assert "TEST_WORLD" in prompt
    assert "relationships" in prompt


def test_validate_bootstrap_dataset(bootstrap_dataset):
    report = validate_bootstrap_dataset(bootstrap_dataset)
    assert report["valid"] is True


def test_validate_rejects_unbound_faction(bootstrap_dataset):
    bad = json.loads(json.dumps(bootstrap_dataset))
    bad["characters"][0]["faction"] = "无势力"
    report = validate_bootstrap_dataset(bad)
    assert report["valid"] is False


def test_import_bootstrap(env, bootstrap_dataset):
    result = apply_bootstrap_import(bootstrap_dataset, persist=True)
    assert result["imported"] is True
    assert result["relationship_edges"] >= 1

    world = io_utils.read_yaml(env / "world_pack.yaml")
    assert world["world"]["title"] == "PROJECT_V6_WORLD"
    assert world["world"]["world_bootstrap"] is True

    snapshot = io_utils.read_json(env / "world_bootstrap.json")
    assert len(snapshot["relationships"]) == 1

    graph = io_utils.read_json(env / "relationship_graph.json")
    assert graph["edges"]
