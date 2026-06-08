"""
visual_continuity.py — V6.6 visual continuity hints (read-only constraints)
"""

from __future__ import annotations

from typing import Any

from engine.visual.identity_registry import load_identity_registry
from engine.visual.visual_identity import VisualIdentity


def build_continuity_hints(
    *,
    event_id: str,
    characters: list[str],
    previous_event_id: str = "",
) -> dict[str, Any]:
    """
    Produce prompt_hint + visual_constraints for narrative continuity.
    Does not call providers or generate images.
    """
    identity_reg = load_identity_registry()
    identities = identity_reg.get("identities") or {}
    entity_index = identity_reg.get("entity_index") or {}

    identity_ids: list[str] = []
    style_anchors: dict[str, dict[str, Any]] = {}
    constraints: list[str] = [
        "facial structure stable",
        "hair and color stable",
        "outfit signature stable",
        "scene style consistent with prior event",
    ]

    for name in characters:
        lookup = f"character:{name}"
        iid = entity_index.get(lookup)
        if not iid:
            continue
        identity_ids.append(iid)
        identity = VisualIdentity.from_dict(identities.get(iid))
        if identity:
            style_anchors[iid] = dict(identity.style_anchor)
            constraints.append(f"identity lock: {iid} ({name})")

    prompt_hint = (
        f"maintain visual continuity from event {previous_event_id or event_id}; "
        "same character identities; consistent lighting and render style"
    )

    return {
        "previous_event_id": previous_event_id,
        "event_id": event_id,
        "identity_ids": identity_ids,
        "style_anchors": style_anchors,
        "prompt_hint": prompt_hint,
        "visual_constraints": constraints,
    }
