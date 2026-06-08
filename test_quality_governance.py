"""Visual Quality Governance Layer v1 tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

import config
from engine.visual.asset_manager import reset_visual_assets
from engine.visual.identity_prompt_builder import build_identity_prompt
from engine.visual.identity_registry import resolve_identity
from engine.visual.quality_governance import (
    QualityEvaluation,
    classify_quality,
    compute_final_score,
    evaluate_quality,
    score_aesthetic,
    validate_structure,
)
from engine.visual.style_drift import DriftEvaluation, evaluate_generation
from engine.visual.visual_object import build_visual_object
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
    monkeypatch.setattr(config, "VISUAL_QUALITY_GOVERNANCE_ENABLED", True)
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


def test_structure_validation_passes_for_identity_prompt(world_pack, env):
    obj = build_visual_object("character", "长公主", {"world_pack": world_pack})
    structure = validate_structure(obj, obj.prompt)
    assert structure.valid is True
    assert structure.score == 1.0
    assert not structure.issues


def test_structure_rejects_illegal_combo(world_pack, env):
    obj = build_visual_object("location", "测试王国", {"world_pack": world_pack})
    bad_prompt = obj.prompt + ", anime character portrait, full body standing pose"
    structure = validate_structure(obj, bad_prompt)
    assert structure.valid is False
    assert structure.score == 0.0


def test_consistency_inverts_drift_score():
    from engine.visual.quality_governance import score_consistency

    drift = DriftEvaluation(0.2, "ok", "accept")
    assert score_consistency(drift) == 0.8


def test_aesthetic_scores_style_bible_tokens():
    prompt = (
        "cinematic lighting, rule of thirds, strong focal subject, "
        "illustration-grade detail, coherent visual identity, clear silhouette design"
    )
    score, dims = score_aesthetic(prompt, "character")
    assert score >= 0.5
    assert dims["composition"] > 0


def test_final_score_weighting():
    assert compute_final_score(1.0, 1.0, 1.0) == 1.0
    assert compute_final_score(0.0, 0.0, 0.0) == 0.0
    assert classify_quality(0.8) == "accept"
    assert classify_quality(0.6) == "accept_weak"
    assert classify_quality(0.3) == "reject"


def test_identity_prompt_passes_governance(world_pack, env):
    obj = build_visual_object("character", "长公主", {"world_pack": world_pack})
    drift = evaluate_generation(obj.prompt, obj.entity_type, {"provider": "mock", "bytes": 512})
    quality = evaluate_quality(obj, obj.prompt, {"bytes": 512}, drift)
    assert quality.decision in ("accept", "accept_weak")
    assert quality.final_score >= config.VISUAL_QUALITY_WEAK_THRESHOLD


def test_get_visual_records_quality_meta(world_pack, env):
    mock = MockVisualProvider()
    record = get_visual("character", "长公主", {"world_pack": world_pack}, provider=mock)
    quality = (record.get("meta") or {}).get("quality") or {}
    assert "final_score" in quality
    assert quality.get("decision") in ("accept", "accept_weak")
    assert "structure_validity" in quality


def test_quality_reject_triggers_regenerate(world_pack, env):
    mock = MockVisualProvider()
    reject_eval = QualityEvaluation(
        structure_validity=0.0,
        consistency_score=0.2,
        aesthetic_score=0.2,
        final_score=0.2,
        decision="reject",
        action="pending",
    )
    accept_eval = QualityEvaluation(
        structure_validity=1.0,
        consistency_score=0.9,
        aesthetic_score=0.9,
        final_score=0.93,
        decision="accept",
        action="pending",
    )

    with patch("engine.visual.visual_runtime.evaluate_quality", side_effect=[reject_eval, accept_eval]):
        record = get_visual("character", "长公主", {"world_pack": world_pack}, provider=mock)
    assert record["meta"]["quality"]["action"] == "reject_regenerate"
    assert record["provider"] == "stub"
