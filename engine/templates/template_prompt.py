"""
template_prompt.py — merge IP templates with VisualIdentity prompts
"""

from __future__ import annotations

from typing import Any

from engine.templates.template_registry import get_style_bible
from engine.visual.visual_identity import VisualIdentity


def _keywords_from_template(template: dict, entity_type: str) -> list[str]:
    parts: list[str] = []
    for key in ("visual_keywords",):
        vals = template.get(key)
        if isinstance(vals, list):
            parts.extend(str(v) for v in vals if str(v).strip())

    if entity_type == "character":
        for key in ("archetype", "role_in_world", "conflict_vector", "signature_trait"):
            val = template.get(key)
            if val:
                parts.append(f"{key}: {val}")
        axis = template.get("personality_axis")
        if isinstance(axis, list) and axis:
            parts.append("personality_axis: " + ", ".join(str(a) for a in axis[:6]))
        hint = template.get("visual_identity_hint")
        if hint:
            parts.append(f"visual_identity_hint: {hint}")
    elif entity_type == "location":
        for key in ("type", "function_in_world", "atmosphere", "dominant_materials", "story_usage"):
            val = template.get(key)
            if val:
                parts.append(f"{key}: {val}")
    elif entity_type == "faction":
        for key in ("ideology", "power_structure", "public_image", "hidden_goal", "visual_identity"):
            val = template.get(key)
            if val:
                parts.append(f"{key}: {val}")
    elif entity_type == "event":
        for key in ("type", "conflict", "visual_focus", "emotion_tone", "outcome_state"):
            val = template.get(key)
            if val:
                parts.append(f"{key}: {val}")

    return parts


def build_prompt_from_template(
    template: dict[str, Any],
    identity: VisualIdentity,
    *,
    base_prompt: str = "",
) -> str:
    """
    Template decides world style; identity decides entity consistency.

    merge(template.visual_keywords, identity.style_anchor, template.emotion_tone)
    """
    if not template:
        return base_prompt

    et = identity.entity_type
    parts: list[str] = []

    # World-level visual tone only for scenes/locations/factions — NOT for character portraits
    if et != "character":
        bible = get_style_bible()
        tone = str(bible.get("world_tone") or "").strip()
        if tone:
            parts.append(f"world_tone: {tone}")
        for kw in bible.get("visual_language") or []:
            if kw:
                parts.append(f"style: {kw}")

    parts.extend(_keywords_from_template(template, et))

    if et == "event":
        emo = str(template.get("emotion_tone") or "").strip()
        if emo:
            parts.append(f"emotion_tone: {emo}")
        palette = bible.get("emotion_palette") or []
        if isinstance(palette, list) and palette and not emo:
            parts.append(f"emotion_tone: {palette[0]}")

    if base_prompt:
        parts.append(base_prompt)

    return ", ".join(p for p in parts if p)


def augment_identity_prompt(
    base_prompt: str,
    template: dict[str, Any] | None,
    identity: VisualIdentity,
) -> str:
    """Hook used by identity_prompt_builder — template layer above identity merge."""
    if not template:
        return base_prompt
    merged = build_prompt_from_template(template, identity, base_prompt=base_prompt)
    return merged or base_prompt
