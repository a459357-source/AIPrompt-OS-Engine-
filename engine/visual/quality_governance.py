"""
quality_governance.py — Visual Quality Governance Layer v1
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import config
from engine.visual.style_drift import DriftEvaluation
from engine.visual.visual_object import VisualObject
from engine.visual.visual_registry import ENTITY_TYPES

_REQUIRED_PROMPT_MARKERS = ("entity:", "seed:")

_CROSS_TYPE_VIOLATIONS: tuple[tuple[str, str], ...] = (
    ("location", "anime character portrait"),
    ("location", "full body standing pose"),
    ("character", "top-down illustrated map"),
    ("character", "political faction territory map"),
    ("faction", "anime character portrait"),
    ("event", "top-down illustrated map"),
)

_ENTITY_SCENE_HINTS: dict[str, tuple[str, ...]] = {
    "character": ("character", "portrait", "pose", "outfit"),
    "location": ("map", "world", "region", "location"),
    "faction": ("faction", "territory", "political"),
    "event": ("scene", "cinematic", "story", "event"),
}

_AESTHETIC_DIMENSIONS: dict[str, tuple[str, ...]] = {
    "composition": ("rule of thirds", "strong focal subject", "controlled depth of field"),
    "emotional": ("subtle dramatic tone", "cinematic lighting", "emotional lighting alignment"),
    "clarity": ("illustration-grade detail", "coherent visual identity"),
    "ip_feel": ("high consistency world design", "clear silhouette design", "architectural coherence"),
}

_WEIGHT_CONSISTENCY = 0.3
_WEIGHT_AESTHETIC = 0.3
_WEIGHT_STRUCTURE = 0.4


@dataclass
class StructuralValidation:
    valid: bool
    score: float
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QualityEvaluation:
    structure_validity: float
    consistency_score: float
    aesthetic_score: float
    final_score: float
    decision: str
    action: str
    structure: StructuralValidation = field(default_factory=lambda: StructuralValidation(True, 1.0))
    aesthetic_dimensions: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["structure"] = self.structure.to_dict()
        return data


def _prompt_tokens(prompt_lower: str) -> set[str]:
    return {t.strip() for t in prompt_lower.split(",") if t.strip()}


def _phrase_in_prompt(phrase: str, prompt_lower: str) -> bool:
    """Match multi-word hints against canonical comma-token prompts."""
    lower = str(phrase or "").strip().lower()
    if not lower:
        return False
    if lower in prompt_lower:
        return True
    words = [w for w in lower.split() if w]
    tokens = _prompt_tokens(prompt_lower)
    if not words:
        return False
    return all(
        w in tokens or any(w in t or t in w for t in tokens)
        for w in words
    )


def _entity_binding_ok(obj: VisualObject, prompt_lower: str) -> bool:
    tokens = _prompt_tokens(prompt_lower)
    eid = str(obj.entity_id or "").strip().lower()
    has_entity_marker = any("entity:" in t or t == "entity" for t in tokens)
    if not has_entity_marker and "entity:" not in prompt_lower:
        return False
    if not eid:
        return True
    return eid in tokens or eid in prompt_lower


def validate_structure(obj: VisualObject, prompt: str) -> StructuralValidation:
    """L1 — entity/identity binding and illegal prompt combinations."""
    issues: list[str] = []
    prompt_lower = str(prompt or "").lower()

    if obj.entity_type not in ENTITY_TYPES:
        issues.append(f"invalid entity_type: {obj.entity_type}")

    if not str(obj.identity_id or "").startswith("vid_"):
        issues.append("missing or invalid identity_id")

    if not str(obj.entity_id or "").strip():
        issues.append("missing entity_id")

    for marker in _REQUIRED_PROMPT_MARKERS:
        if marker not in prompt_lower and not any(marker.rstrip(":") in t for t in _prompt_tokens(prompt_lower)):
            issues.append(f"prompt missing {marker}")

    if obj.entity_id and not _entity_binding_ok(obj, prompt_lower):
        issues.append("entity marker mismatch")

    for et, forbidden in _CROSS_TYPE_VIOLATIONS:
        if obj.entity_type == et and _phrase_in_prompt(forbidden, prompt_lower):
            issues.append(f"illegal combo: {et} + {forbidden}")

    hints = _ENTITY_SCENE_HINTS.get(obj.entity_type, ())
    if hints and not any(_phrase_in_prompt(h, prompt_lower) or h in prompt_lower for h in hints):
        issues.append(f"scene hint missing for {obj.entity_type}")

    if not issues:
        return StructuralValidation(valid=True, score=1.0, issues=[])

    critical = any(
        i.startswith("invalid entity_type")
        or i.startswith("missing or invalid identity")
        or i.startswith("entity marker mismatch")
        or i.startswith("illegal combo")
        for i in issues
    )
    score = 0.0 if critical else 0.5
    return StructuralValidation(valid=not critical, score=score, issues=issues)


def score_consistency(drift_eval: DriftEvaluation | None) -> float:
    """L2 — invert drift distance into world consistency score."""
    if drift_eval is None:
        return 1.0
    return round(max(0.0, min(1.0, 1.0 - float(drift_eval.score))), 4)


def _dimension_score(prompt_lower: str, tokens: tuple[str, ...]) -> float:
    if not tokens:
        return 1.0
    matched = sum(1 for t in tokens if _phrase_in_prompt(t, prompt_lower))
    return matched / len(tokens)


def score_aesthetic(prompt: str, entity_type: str) -> tuple[float, dict[str, float]]:
    """L3 — heuristic composition / tone / clarity / IP feel."""
    prompt_lower = str(prompt or "").lower()
    dimensions: dict[str, float] = {}
    for name, tokens in _AESTHETIC_DIMENSIONS.items():
        dimensions[name] = round(_dimension_score(prompt_lower, tokens), 4)

    et = str(entity_type or "").strip().lower()
    entity_tokens = {
        "character": ("clear silhouette design", "recognizable outfit structure"),
        "location": ("architectural coherence", "environmental storytelling"),
        "faction": ("symbolic visual identity", "banner/emblem consistency"),
        "event": ("dynamic composition", "emotional lighting alignment"),
    }.get(et, ())
    dimensions["entity_fit"] = round(_dimension_score(prompt_lower, entity_tokens), 4)

    if len(prompt_lower) < 40:
        dimensions["clarity"] = min(dimensions.get("clarity", 1.0), 0.3)

    aesthetic = sum(dimensions.values()) / len(dimensions) if dimensions else 0.0
    return round(max(0.0, min(1.0, aesthetic)), 4), dimensions


def compute_final_score(
    structure_validity: float,
    consistency_score: float,
    aesthetic_score: float,
) -> float:
    return round(
        _WEIGHT_STRUCTURE * structure_validity
        + _WEIGHT_CONSISTENCY * consistency_score
        + _WEIGHT_AESTHETIC * aesthetic_score,
        4,
    )


def classify_quality(final_score: float) -> str:
    accept_th = float(getattr(config, "VISUAL_QUALITY_ACCEPT_THRESHOLD", 0.75) or 0.75)
    weak_th = float(getattr(config, "VISUAL_QUALITY_WEAK_THRESHOLD", 0.5) or 0.5)
    if final_score >= accept_th:
        return "accept"
    if final_score >= weak_th:
        return "accept_weak"
    return "reject"


def evaluate_quality(
    obj: VisualObject,
    prompt: str,
    gen_result: dict[str, Any] | None,
    drift_eval: DriftEvaluation | None,
) -> QualityEvaluation:
    """Multi-level governance evaluation before cache/registry admission."""
    structure = validate_structure(obj, prompt)
    consistency = score_consistency(drift_eval)
    aesthetic, dimensions = score_aesthetic(prompt, obj.entity_type)
    final_score = compute_final_score(structure.score, consistency, aesthetic)
    decision = classify_quality(final_score)

    if not structure.valid:
        decision = "reject"

    return QualityEvaluation(
        structure_validity=structure.score,
        consistency_score=consistency,
        aesthetic_score=aesthetic,
        final_score=final_score,
        decision=decision,
        action="pending",
        structure=structure,
        aesthetic_dimensions=dimensions,
    )
