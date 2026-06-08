"""
game_runtime.py — V6 Game Runtime orchestrator
================================================
Wires narrative + visual into a unified game frame.
Single entry: build_game_frame(state, result) → hydrated game payload.

Design contract:
  - game = only orchestrator (never generates content itself)
  - narrative = world skeleton (nodes, choices, participants)
  - visual = mandatory consequence of narrative
  - UI = pure render (never triggers generation)
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import config
from engine.visual.visual_api import public_image_url

logger = logging.getLogger(__name__)


def ensure_game_visuals(
    state: dict[str, Any],
    *,
    turn: int = 0,
    max_chars: int = 5,
    force: bool = False,
    background: bool = False,
) -> dict[str, Any]:
    """Generate/cache visuals for current game scene.

    Returns {characters: [{name, image_url, ...}], scene: {image_url, ...}}

    When background=True, triggers generation in a daemon thread
    and returns only cached assets immediately.
    """
    if not config.VISUAL_SYSTEM_ENABLED:
        return {"characters": [], "scene": None}

    characters_raw = state.get("characters", {})
    scene_id = str(state.get("scene") or "").strip()

    if background:
        _trigger_background_visuals(characters_raw, scene_id, turn, max_chars, force)
        return _read_cached_visuals(characters_raw, scene_id)

    return _generate_visuals_sync(characters_raw, scene_id, turn, max_chars, force)


def _generate_visuals_sync(
    characters_raw: dict,
    scene_id: str,
    turn: int,
    max_chars: int,
    force: bool,
) -> dict[str, Any]:
    """Synchronous visual generation for current scene."""
    from engine.visual.visual_runtime import get_visual

    result: dict[str, Any] = {"characters": [], "scene": None}

    # Character visuals — prioritize main/recent characters
    char_list = _ranked_characters(characters_raw)[:max_chars]
    for entry in char_list:
        name = entry["name"]
        try:
            visual = get_visual(
                "character",
                name,
                context={"scene": scene_id, "turn": turn, "name": name},
                turn=turn,
                force=force,
            )
            if visual.get("image_path"):
                result["characters"].append({
                    "name": name,
                    "image_url": public_image_url(visual["image_path"]),
                })
        except Exception as exc:
            logger.debug("Game visual — skip character %s: %s", name, exc)

    # Scene visual
    if scene_id:
        try:
            visual = get_visual(
                "event",
                scene_id,
                context={"turn": turn},
                turn=turn,
                force=force,
            )
            if visual.get("image_path"):
                result["scene"] = {
                    "scene_id": scene_id,
                    "image_url": public_image_url(visual["image_path"]),
                }
        except Exception as exc:
            logger.debug("Game visual — skip scene %s: %s", scene_id, exc)

    return result


def _ranked_characters(characters_raw: dict) -> list[dict[str, str]]:
    """Sort characters: main first, then by name."""
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


def _read_cached_visuals(
    characters_raw: dict,
    scene_id: str,
) -> dict[str, Any]:
    """Read existing visuals from registry only (no generation)."""
    from engine.visual.visual_registry import get_asset, list_assets, load_registry

    registry = load_registry()
    result: dict[str, Any] = {"characters": [], "scene": None}

    for key, ch in characters_raw.items():
        if not isinstance(ch, dict):
            continue
        name = str(ch.get("name") or key).strip()
        if not name:
            continue
        asset = get_asset(registry, "characters", name)
        if not asset:
            # try by identity match
            for record in list_assets(registry, "characters").values():
                if isinstance(record, dict) and str(record.get("entity_id") or "") == name:
                    asset = record
                    break
        if asset and isinstance(asset, dict) and asset.get("image_path"):
            result["characters"].append({
                "name": name,
                "image_url": public_image_url(asset["image_path"]),
            })

    if scene_id:
        asset = get_asset(registry, "events", scene_id)
        if asset and isinstance(asset, dict) and asset.get("image_path"):
            result["scene"] = {
                "scene_id": scene_id,
                "image_url": public_image_url(asset["image_path"]),
            }

    return result


def _trigger_background_visuals(
    characters_raw: dict,
    scene_id: str,
    turn: int,
    max_chars: int,
    force: bool,
) -> None:
    """Generate visuals in background thread (fire-and-forget)."""
    def _work():
        try:
            _generate_visuals_sync(characters_raw, scene_id, turn, max_chars, force)
        except Exception as exc:
            logger.warning("Background visual generation failed: %s", exc)

    t = threading.Thread(target=_work, daemon=True)
    t.start()


def build_game_frame(
    result: dict[str, Any],
    state: dict[str, Any],
    *,
    background_visuals: bool = True,
) -> dict[str, Any]:
    """
    Wire step() result with visuals into a complete game frame.

    Args:
        result: step() return value {story, options, state, turn, status, scene}
        state: current session state
        background_visuals: if True, generate visuals in background (non-blocking)

    Returns:
        dict with story, options, state, visuals ready for UI rendering.
    """
    turn = state.get("turn", result.get("turn", 0))
    visuals = ensure_game_visuals(
        state,
        turn=turn,
        force=False,
        background=background_visuals,
    )

    return {
        **result,
        "visuals": visuals,
    }
