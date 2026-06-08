"""
style_drift.py — Style Drift Detector v1 (prompt-proxy feedback control)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import config
from engine.templates.style_bible import ENTITY_STYLE_MAP, STYLE_BIBLE_V1

DRIFT_MARKERS: tuple[str, ...] = (
    "cyberpunk",
    "neon",
    "cartoon",
    "chibi",
    "manga style",
    "high saturation",
    "oversaturated",
    "random composition",
    "flat color",
    "pixel art",
    "comic book",
    "graffiti",
    "synthwave",
    "vaporwave",
    "low poly",
    "pop art",
)


@dataclass
class StyleSignature:
    palette: list[str] = field(default_factory=list)
    composition_style: list[str] = field(default_factory=list)
    lighting_profile: list[str] = field(default_factory=list)
    material_distribution: list[str] = field(default_factory=list)
    entity_style: list[str] = field(default_factory=list)


@dataclass
class DriftEvaluation:
    score: float
    level: str
    action: str
    features: dict[str, Any] = field(default_factory=dict)
    missing_tokens: list[str] = field(default_factory=list)
    drift_markers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_style_signature(entity_type: str) -> StyleSignature:
    """World style vector derived from Style Bible v1."""
    et = str(entity_type or "").strip().lower()
    return StyleSignature(
        palette=list(STYLE_BIBLE_V1.get("tone") or []),
        composition_style=list(STYLE_BIBLE_V1.get("composition") or []),
        lighting_profile=list(STYLE_BIBLE_V1.get("global") or []),
        material_distribution=list(STYLE_BIBLE_V1.get("material") or []),
        entity_style=list(ENTITY_STYLE_MAP.get(et) or []),
    )


def _prompt_lower(prompt: str) -> str:
    return str(prompt or "").lower()


def _token_match(expected: str, prompt_lower: str) -> bool:
    exp = str(expected or "").strip().lower()
    if not exp:
        return False
    if exp in prompt_lower:
        return True
    for part in prompt_lower.split(","):
        chunk = part.strip()
        if not chunk:
            continue
        if exp in chunk or chunk in exp:
            return True
    return False


def _find_drift_markers(prompt: str) -> list[str]:
    lower = _prompt_lower(prompt)
    return [m for m in DRIFT_MARKERS if m in lower]


def extract_features(
    prompt: str,
    entity_type: str,
    gen_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    v1 feature proxy — prompt analysis + provider metadata (no CV/ML).
    """
    signature = build_style_signature(entity_type)
    prompt_lower = _prompt_lower(prompt)

    def matched(tokens: list[str]) -> list[str]:
        return [t for t in tokens if _token_match(t, prompt_lower)]

    features: dict[str, Any] = {
        "color_profile": matched(signature.palette),
        "composition_score": matched(signature.composition_style),
        "lighting_type": matched(signature.lighting_profile),
        "texture_distribution": matched(signature.material_distribution),
        "entity_style": matched(signature.entity_style),
        "drift_markers": _find_drift_markers(prompt),
        "provider": str((gen_result or {}).get("provider") or ""),
        "bytes": int((gen_result or {}).get("bytes") or 0),
    }
    return features


def compute_drift(features: dict[str, Any], signature: StyleSignature) -> tuple[float, list[str]]:
    """Distance between observed prompt-proxy features and world style signature."""
    buckets: list[tuple[str, list[str]]] = [
        ("color_profile", signature.palette),
        ("composition_score", signature.composition_style),
        ("lighting_type", signature.lighting_profile),
        ("texture_distribution", signature.material_distribution),
        ("entity_style", signature.entity_style),
    ]

    coverages: list[float] = []
    missing: list[str] = []
    for key, expected in buckets:
        if not expected:
            continue
        matched = features.get(key) or []
        if not isinstance(matched, list):
            matched = []
        for token in expected:
            if token not in matched:
                missing.append(token)
        coverages.append(len(matched) / len(expected))

    avg_cov = sum(coverages) / len(coverages) if coverages else 1.0
    base = 1.0 - avg_cov
    markers = features.get("drift_markers") or []
    marker_penalty = min(0.5, len(markers) * 0.15) if isinstance(markers, list) else 0.0
    score = min(1.0, max(0.0, base * 0.7 + marker_penalty))
    return score, missing


def classify_drift(score: float) -> str:
    mild = float(getattr(config, "STYLE_DRIFT_MILD_THRESHOLD", 0.3) or 0.3)
    severe = float(getattr(config, "STYLE_DRIFT_SEVERE_THRESHOLD", 0.6) or 0.6)
    if score <= mild:
        return "ok"
    if score <= severe:
        return "mild"
    return "severe"


def evaluate_generation(
    prompt: str,
    entity_type: str,
    gen_result: dict[str, Any] | None = None,
) -> DriftEvaluation:
    """Evaluate whether a generated asset deviates from the world style signature."""
    signature = build_style_signature(entity_type)
    features = extract_features(prompt, entity_type, gen_result)
    score, missing = compute_drift(features, signature)
    level = classify_drift(score)
    return DriftEvaluation(
        score=round(score, 4),
        level=level,
        action="pending",
        features=features,
        missing_tokens=missing,
        drift_markers=list(features.get("drift_markers") or []),
    )
