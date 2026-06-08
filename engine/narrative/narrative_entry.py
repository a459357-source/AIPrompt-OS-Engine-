"""
narrative_entry.py — V6.6 Narrative Node builder (read-only assembly)
"""

# NARRATIVE SYSTEM IS PASSIVE ONLY — read-only metadata for UI/visuals.
# It must NEVER control story, options, or game flow.

from __future__ import annotations

from typing import Any

import config
from engine import io_utils
from engine.director_state import load_director_state
from engine.event_director import ensure_event_catalog
from engine.narrative.narrative_router import (
    get_choices_for_event,
    get_node_definition,
    resolve_canonical_event_id,
    resolve_character_entry,
    resolve_location_entry,
    resolve_visual_event_entry,
)
from engine.narrative.visual_continuity import build_continuity_hints
from engine.visual.identity_registry import load_identity_registry
from engine.visual.visual_api import _characters_at_turn, get_event_timeline, public_image_url
from engine.visual.visual_registry import list_assets, load_registry


def _catalog_label(event_id: str) -> str:
    catalog = ensure_event_catalog()
    entry = (catalog.get("events") or {}).get(event_id) or {}
    return str(entry.get("label") or event_id)


def _scene_for_event(canonical_event_id: str, visual_event_id: str = "") -> dict[str, Any]:
    """Find scene image from visual registry — read only."""
    registry = load_registry()
    candidates = [visual_event_id, canonical_event_id]
    for record in list_assets(registry, "events").values():
        if not isinstance(record, dict):
            continue
        aid = str(record.get("asset_id") or "")
        eid = str(record.get("entity_id") or "")
        if aid in candidates or eid in candidates or aid == visual_event_id:
            path = str(record.get("image_path") or record.get("uri") or "")
            return {
                "scene_image": public_image_url(path),
                "scene_image_path": path,
                "visual_asset_id": aid,
            }
    # fallback: first event asset or empty
    events = list(list_assets(registry, "events").values())
    if events and isinstance(events[0], dict):
        path = str(events[0].get("image_path") or events[0].get("uri") or "")
        return {
            "scene_image": public_image_url(path),
            "scene_image_path": path,
            "visual_asset_id": str(events[0].get("asset_id") or ""),
        }
    return {"scene_image": "", "scene_image_path": "", "visual_asset_id": ""}


def _characters_for_event(canonical_event_id: str) -> list[dict[str, Any]]:
    director = load_director_state()
    current = director.get("current_event")
    participants: list[str] = []
    if isinstance(current, dict) and str(current.get("event_id") or "") == canonical_event_id:
        participants = [str(p) for p in (current.get("participants") or []) if str(p).strip()]

    if not participants:
        for item in director.get("pending") or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("event_id") or "") == canonical_event_id:
                participants = [str(p) for p in (item.get("participants") or []) if str(p).strip()]
                break

    if not participants:
        try:
            state = io_utils.read_yaml(config.SESSION_STATE_PATH)
            turn = int(state.get("turn") or 0)
            participants = _characters_at_turn(turn)
        except Exception:
            participants = []

    identity_reg = load_identity_registry()
    entity_index = identity_reg.get("entity_index") or {}
    identities = identity_reg.get("identities") or {}

    out: list[dict[str, Any]] = []
    for name in participants:
        iid = entity_index.get(f"character:{name}", "")
        identity_raw = identities.get(iid) if iid else None
        out.append({
            "name": name,
            "identity_id": iid,
            "traits": (identity_raw or {}).get("canonical_traits") or {},
        })
    return out


def _current_state_panel() -> dict[str, Any]:
    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    except Exception:
        state = {}
    director = load_director_state()
    return {
        "turn": int(state.get("turn") or 0),
        "scene": str(state.get("scene") or ""),
        "status": str(state.get("status") or ""),
        "director_state": str((director.get("current_event") or {}).get("state") or ""),
    }


def build_narrative_node(event_id: str, *, visual_event_id: str = "") -> dict[str, Any]:
    """Assemble Narrative Node from registry + routes + director — no generation."""
    canonical = resolve_canonical_event_id(event_id)
    node_def = get_node_definition(canonical)
    choices = get_choices_for_event(canonical)
    next_events = sorted({c["target_event_id"] for c in choices})
    scene = _scene_for_event(canonical, visual_event_id or event_id)
    characters = _characters_for_event(canonical)
    continuity = build_continuity_hints(
        event_id=canonical,
        characters=[c["name"] for c in characters],
        previous_event_id="",
    )

    content_template: dict = {}
    try:
        from engine.templates.template_resolver import resolve_content_template
        content_template = resolve_content_template("event", canonical, context={"scene": node_def.get("context")})
    except Exception:
        pass

    return {
        "event_id": canonical,
        "visual_event_id": visual_event_id or event_id,
        "label": _catalog_label(canonical),
        "scene_image": scene.get("scene_image", ""),
        "scene_image_path": scene.get("scene_image_path", ""),
        "visual_asset_id": scene.get("visual_asset_id", ""),
        "context": str(node_def.get("context") or ""),
        "characters": characters,
        "current_state": _current_state_panel(),
        "choices": choices,
        "next_events": next_events,
        "continuity": continuity,
        "content_template": content_template,
    }


def get_narrative_hub() -> dict[str, Any]:
    """Entry hub metadata — continue + available visual events."""
    from engine.narrative.narrative_state import load_narrative_state

    state = load_narrative_state()
    events = get_event_timeline()
    return {
        "mode": state.get("mode", "explore"),
        "current_event_id": state.get("current_event_id", ""),
        "entry_points": {
            "events": [
                {
                    "visual_event_id": e.get("event_id"),
                    "label": e.get("display_name"),
                    "narrative_event_id": resolve_visual_event_entry(str(e.get("event_id") or "")),
                }
                for e in events
            ],
        },
    }
