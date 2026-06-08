"""
asset_manager.py — V6 Visual Asset Manager (backward-compatible wrappers)
"""

from __future__ import annotations

import logging
from typing import Any

import config
from engine.visual.provider_factory import get_visual_provider
from engine.visual.visual_cache import clear_visual_output
from engine.visual.visual_provider import VisualProvider
from engine.visual.visual_registry import empty_registry, save_registry
from engine.visual.visual_runtime import get_visual

logger = logging.getLogger(__name__)


def get_or_request_character_portrait(
    name: str,
    world_pack: dict,
    *,
    turn: int = 0,
    provider: VisualProvider | None = None,
    force: bool = False,
) -> dict[str, Any]:
    return get_visual(
        "character",
        name,
        {"world_pack": world_pack, "name": name},
        turn=turn,
        provider=provider,
        force=force,
    )


def get_or_request_scene_image(
    scene_key: str,
    context: dict,
    *,
    turn: int = 0,
    provider: VisualProvider | None = None,
    force: bool = False,
) -> dict[str, Any]:
    ctx = dict(context) if isinstance(context, dict) else {}
    ctx.setdefault("name", str(ctx.get("scene") or scene_key))
    return get_visual(
        "event",
        scene_key,
        ctx,
        turn=turn,
        provider=provider,
        force=force,
    )


def get_or_request_world_map(
    world_pack: dict,
    *,
    turn: int = 0,
    provider: VisualProvider | None = None,
    force: bool = False,
) -> dict[str, Any]:
    world = world_pack.get("world", world_pack) if isinstance(world_pack, dict) else {}
    title = str(world.get("title") or world.get("name") or "world_map")
    return get_visual(
        "location",
        title,
        {"world_pack": world_pack, "name": title},
        turn=turn,
        provider=provider,
        force=force,
    )


def get_or_request_faction_map(
    faction_name: str,
    memory: dict,
    *,
    turn: int = 0,
    provider: VisualProvider | None = None,
    force: bool = False,
) -> dict[str, Any]:
    return get_visual(
        "faction",
        faction_name,
        {"memory": memory, "name": faction_name},
        turn=turn,
        provider=provider,
        force=force,
    )


def reset_visual_assets(*, persist: bool = True) -> None:
    """Clear registry, identity registry, narrative state, and visual output cache."""
    from engine.narrative.narrative_state import empty_narrative_state, save_narrative_state
    from engine.visual.identity_registry import empty_identity_registry, save_identity_registry

    clear_visual_output()
    save_registry(empty_registry(), persist=persist)
    save_identity_registry(empty_identity_registry(), persist=persist)
    save_narrative_state(empty_narrative_state(), persist=persist)
    for path in (config.VISUAL_REGISTRY_PATH, config.VISUAL_IDENTITY_REGISTRY_PATH):
        if path.exists() and not persist:
            try:
                path.unlink()
            except OSError:
                pass
    logger.info("Visual assets reset")
