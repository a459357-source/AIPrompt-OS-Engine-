"""Style Drift Detector v1 feedback control tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

import config
from engine.templates.style_bible import apply_style_bible, reinforce_style_bible
from engine.visual.asset_manager import reset_visual_assets
from engine.visual.identity_prompt_builder import build_identity_prompt
from engine.visual.identity_registry import resolve_identity
from engine.visual.style_drift import (
    DriftEvaluation,
    build_style_signature,
    classify_drift,
    compute_drift,
    evaluate_generation,
    extract_features,
)
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
    monkeypatch.setattr(config, "STYLE_DRIFT_DETECTOR_ENABLED", True)
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


def test_style_signature_from_style_bible():
    sig = build_style_signature("character")
    assert "controlled color palette" in sig.palette
    assert "rule of thirds" in sig.composition_style
    assert "cinematic lighting" in sig.lighting_profile
    assert "clear silhouette design" in sig.entity_style


def test_conforming_prompt_low_drift():
    prompt = apply_style_bible("beautiful princess, palace, sunset", "character")
    features = extract_features(prompt, "character")
    sig = build_style_signature("character")
    score, missing = compute_drift(features, sig)
    assert score <= 0.3
    assert classify_drift(score) == "ok"


def test_drift_markers_raise_score():
    prompt = "cyberpunk neon princess, high saturation cartoon, random composition"
    features = extract_features(prompt, "character")
    sig = build_style_signature("character")
    score, _ = compute_drift(features, sig)
    assert score >= 0.6
    assert classify_drift(score) == "severe"
    assert features["drift_markers"]


def test_reinforce_adds_stricter_tokens():
    base = apply_style_bible("princess scene", "character")
    reinforced = reinforce_style_bible("princess scene", "character")
    assert "strict world visual adherence" in reinforced
    assert base in reinforced


def test_get_visual_records_drift_meta(world_pack, env):
    mock = MockVisualProvider()
    record = get_visual("character", "长公主", {"world_pack": world_pack}, provider=mock)
    drift = (record.get("meta") or {}).get("drift") or {}
    assert "score" in drift
    assert drift.get("level") == "ok"
    assert drift.get("action") == "accept"


def test_mild_drift_triggers_retry(world_pack, env):
    mock = MockVisualProvider()
    evaluations = [
        DriftEvaluation(0.45, "mild", "pending"),
        DriftEvaluation(0.1, "ok", "pending"),
    ]

    def fake_eval(prompt, entity_type, gen_result=None):
        return evaluations.pop(0)

    with patch("engine.visual.visual_runtime.evaluate_generation", side_effect=fake_eval):
        record = get_visual("character", "长公主", {"world_pack": world_pack}, provider=mock)
    assert record["meta"]["drift"]["action"] == "retry_accept"


def test_severe_drift_fallback_stub(world_pack, env):
    mock = MockVisualProvider()
    evaluations = [
        DriftEvaluation(0.85, "severe", "pending"),
        DriftEvaluation(0.1, "ok", "pending"),
    ]

    def fake_eval(prompt, entity_type, gen_result=None):
        return evaluations.pop(0)

    with patch("engine.visual.visual_runtime.evaluate_generation", side_effect=fake_eval):
        record = get_visual("character", "长公主", {"world_pack": world_pack}, provider=mock)
    assert record["provider"] == "stub"
    assert record["meta"]["drift"]["action"] == "fallback_reject"


def test_identity_prompt_passes_drift_check(world_pack, env):
    identity = resolve_identity("character", "长公主", {"world_pack": world_pack})
    prompt = build_identity_prompt(identity, {"world_pack": world_pack})
    drift = evaluate_generation(prompt, "character", {"provider": "mock", "bytes": 1024})
    assert drift.level == "ok"
