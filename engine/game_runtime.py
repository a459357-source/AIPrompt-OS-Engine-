"""
game_runtime.py — V6 Game Runtime orchestrator
================================================
Wires narrative + visual into a unified game frame.
Single entry: build_game_frame(state, result) → hydrated game payload.

Design contract:
  - game = only orchestrator (never generates content itself)
  - narrative = world skeleton (nodes, choices, participants) — drives visual
  - visual = mandatory consequence of narrative node
  - UI = pure render (never triggers generation)
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import config
from engine.visual.visual_api import public_image_url

logger = logging.getLogger(__name__)


# ── Narrative node resolution ───────────────────────────────────────

def resolve_game_narrative_node(scene_id: str) -> dict[str, Any]:
    """Resolve the narrative node for the current game scene.

    This is the bridge that connects game state → narrative system.
    Returns a lightweight node dict with event_id, context, characters, choices.
    """
    from engine.narrative.narrative_router import (
        get_choices_for_event,
        get_node_definition,
        resolve_canonical_event_id,
    )

    canonical = resolve_canonical_event_id(scene_id) if scene_id else ""
    node_def = get_node_definition(canonical) if canonical else {}
    choices = get_choices_for_event(canonical) if canonical else []

    # Extract participants from node definition (P0 patch field) or fallback
    participants: list[str] = []
    raw_participants = node_def.get("participants") if isinstance(node_def, dict) else None
    if isinstance(raw_participants, list):
        participants = [str(p).strip() for p in raw_participants if str(p).strip()]
    if not participants:
        # fallback: try to extract from context
        try:
            state = _read_session_state()
            chars = state.get("characters", {})
            participants = [str(ch.get("name") or k).strip() for k, ch in chars.items()
                            if isinstance(ch, dict) and str(ch.get("name") or k).strip()][:5]
        except Exception:
            pass

    context = str(node_def.get("context") or "") if isinstance(node_def, dict) else ""

    return {
        "event_id": canonical or scene_id or "unknown",
        "context": context,
        "characters": [{"name": name} for name in participants],
        "choices": [{"choice_id": c.get("choice_id", ""), "text": c.get("text", ""),
                      "target_event_id": c.get("target_event_id", ""), "tone": c.get("tone", "neutral")}
                     for c in (choices if isinstance(choices, list) else [])],
    }


def _read_session_state() -> dict[str, Any]:
    try:
        from engine import io_utils
        return io_utils.read_yaml(config.SESSION_STATE_PATH)
    except Exception:
        return {}


# ── Visual generation (narrative-node driven) ───────────────────────

def ensure_game_visuals(
    state: dict[str, Any],
    *,
    turn: int = 0,
    max_chars: int = 5,
    force: bool = False,
    background: bool = False,
) -> dict[str, Any]:
    """Generate/cache visuals for current game scene (convenience wrapper).

    Prefer ensure_game_visuals_from_node() when a narrative node is available.
    """
    scene_id = str(state.get("scene") or "").strip()
    node = resolve_game_narrative_node(scene_id)
    return ensure_game_visuals_from_node(node, turn=turn, max_chars=max_chars,
                                         force=force, background=background)


def ensure_game_visuals_from_node(
    node: dict[str, Any],
    *,
    turn: int = 0,
    max_chars: int = 5,
    force: bool = False,
    background: bool = False,
) -> dict[str, Any]:
    """Generate/cache visuals driven by a narrative node.

    Only generates visuals for characters that appear in this node (participants),
    not all characters in the world. Scene visual is keyed by node's event_id.

    Args:
        node: narrative node dict from resolve_game_narrative_node()
              {event_id, context, characters: [{name, ...}], choices}
        turn: current turn for registry tagging
        max_chars: max character portraits to generate
        force: ignore cache and regenerate
        background: fire-and-forget in daemon thread, return cached only
    """
    if not config.VISUAL_SYSTEM_ENABLED:
        return {"characters": [], "scene": None}

    char_names = [c.get("name", "") for c in node.get("characters", []) if c.get("name")]
    event_id = str(node.get("event_id") or "").strip()

    if background:
        _trigger_background_visuals_from_node(char_names, event_id, turn, max_chars, force)
        return _read_cached_visuals_from_node(char_names, event_id)

    return _generate_visuals_sync_from_node(char_names, event_id, turn, max_chars, force)


def _generate_visuals_sync_from_node(
    char_names: list[str],
    event_id: str,
    turn: int,
    max_chars: int,
    force: bool,
) -> dict[str, Any]:
    """Generate portraits + scene for a narrative node's participants."""
    from engine.visual.visual_runtime import get_visual

    result: dict[str, Any] = {"characters": [], "scene": None}

    for name in char_names[:max_chars]:
        try:
            visual = get_visual(
                "character", name,
                context={"scene": event_id, "turn": turn, "name": name},
                turn=turn, force=force,
            )
            if visual.get("image_path"):
                result["characters"].append({
                    "name": name,
                    "image_url": public_image_url(visual["image_path"]),
                })
        except Exception as exc:
            logger.debug("Game visual — skip character %s: %s", name, exc)

    if event_id:
        try:
            visual = get_visual(
                "event", event_id,
                context={"turn": turn},
                turn=turn, force=force,
            )
            if visual.get("image_path"):
                result["scene"] = {
                    "scene_id": event_id,
                    "image_url": public_image_url(visual["image_path"]),
                }
        except Exception as exc:
            logger.debug("Game visual — skip scene %s: %s", event_id, exc)

    return result


def _read_cached_visuals_from_node(
    char_names: list[str],
    event_id: str,
) -> dict[str, Any]:
    """Read existing visuals for node participants (no generation)."""
    from engine.visual.visual_registry import get_asset, list_assets, load_registry
    from pathlib import Path

    registry = load_registry()
    result: dict[str, Any] = {"characters": [], "scene": None}

    def _file_exists(image_path: str) -> bool:
        if not image_path:
            return False
        rel = str(image_path).replace("\\", "/")
        return (config.ROOT / rel).is_file()

    for name in char_names:
        asset = get_asset(registry, "characters", name)
        if not asset:
            for record in list_assets(registry, "characters").values():
                if isinstance(record, dict) and str(record.get("entity_id") or "") == name:
                    asset = record
                    break
        if not asset:
            for record in list_assets(registry, "characters").values():
                if isinstance(record, dict) and str(record.get("display_name") or "").strip() == str(name).strip():
                    asset = record
                    break
        image_path = str((asset or {}).get("image_path") or "")
        if isinstance(asset, dict) and image_path and _file_exists(image_path):
            result["characters"].append({
                "name": name,
                "image_url": public_image_url(image_path),
            })

    if event_id:
        asset = get_asset(registry, "events", event_id)
        image_path = str((asset or {}).get("image_path") or "")
        if asset and image_path and _file_exists(image_path):
            result["scene"] = {
                "scene_id": event_id,
                "image_url": public_image_url(image_path),
            }
        else:
            for record in list_assets(registry, "events").values():
                if isinstance(record, dict) and record.get("image_path"):
                    ip = str(record["image_path"])
                    if _file_exists(ip):
                        result["scene"] = {
                            "scene_id": str(record.get("entity_id") or record.get("asset_id") or ""),
                            "image_url": public_image_url(ip),
                        }
                        break

    return result


def _trigger_background_visuals_from_node(
    char_names: list[str],
    event_id: str,
    turn: int,
    max_chars: int,
    force: bool,
) -> None:
    def _work():
        try:
            _generate_visuals_sync_from_node(char_names, event_id, turn, max_chars, force)
        except Exception as exc:
            logger.warning("Background visual generation failed: %s", exc)
    t = threading.Thread(target=_work, daemon=True)
    t.start()


# ── Legacy helpers (keep backward compat) ───────────────────────────

def _ranked_characters(characters_raw: dict) -> list[dict[str, str]]:
    entries = []
    for key, ch in characters_raw.items():
        if not isinstance(ch, dict):
            continue
        name = str(ch.get("name") or key).strip()
        if not name:
            continue
        is_main = ch.get("is_main") or ch.get("isMain") or False
        entries.append({"name": name, "is_main": is_main})
    entries.sort(key=lambda x: (not x["is_main"], x["name"]))
    return entries


def _read_cached_visuals(characters_raw: dict, scene_id: str) -> dict[str, Any]:
    char_names = [e["name"] for e in _ranked_characters(characters_raw)]
    return _read_cached_visuals_from_node(char_names, scene_id)


# ── Game frame builder ──────────────────────────────────────────────

def build_game_frame(
    result: dict[str, Any],
    state: dict[str, Any],
    *,
    background_visuals: bool = True,
) -> dict[str, Any]:
    """Wire step() result + narrative node + visuals into a complete game frame."""
    turn = state.get("turn", result.get("turn", 0))
    scene_id = str(state.get("scene") or "").strip()
    node = resolve_game_narrative_node(scene_id)
    visuals = ensure_game_visuals_from_node(
        node, turn=turn, force=False, background=background_visuals,
    )
    return {
        **result,
        "visuals": visuals,
        "narrative_node": node,
    }
