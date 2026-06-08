"""
asset_manager.py — V6.0 Visual Asset Manager (public API)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import config
from engine.visual import image_generation
from engine.visual.visual_cache import exists, uri_for_path, cache_path, clear_visual_output
from engine.visual.visual_context import (
    build_character_prompt,
    build_faction_map_prompt,
    build_scene_prompt,
    build_world_map_prompt,
)
from engine.visual.visual_provider import VisualProvider, get_visual_provider
from engine.visual.visual_registry import (
    get_asset,
    load_registry,
    make_asset_record,
    normalize_asset_id,
    save_registry,
    set_asset,
)

logger = logging.getLogger(__name__)


def _registry_record_valid(record: dict | None) -> bool:
    if not isinstance(record, dict):
        return False
    uri = str(record.get("uri", "")).strip()
    if not uri:
        return False
    path = config.ROOT / uri.replace("\\", "/")
    return path.is_file() and path.stat().st_size > 0


def _resolve_or_generate(
    scope: str,
    asset_id: str,
    display_name: str,
    prompt: str,
    kind: str,
    gen_method: str,
    *,
    turn: int = 0,
    size: str = "1024x1024",
    provider: VisualProvider | None = None,
    force: bool = False,
) -> dict[str, Any]:
    if not config.VISUAL_SYSTEM_ENABLED:
        return {}

    provider = provider or get_visual_provider()
    registry = load_registry()

    if not force:
        existing = get_asset(registry, scope, asset_id)
        if _registry_record_valid(existing):
            return existing
        if exists(scope, asset_id):
            path = cache_path(scope, asset_id)
            record = make_asset_record(
                asset_id=asset_id,
                display_name=display_name,
                uri=uri_for_path(path),
                provider=existing.get("provider", provider.provider_name) if existing else provider.provider_name,
                kind=kind,
                created_turn=int((existing or {}).get("created_turn", turn) or turn),
                prompt_hash=str((existing or {}).get("prompt_hash", "")),
            )
            registry = set_asset(registry, scope, asset_id, record)
            save_registry(registry)
            return record

    gen_fn = getattr(provider, gen_method)
    record = image_generation.generate_and_register(
        scope,
        asset_id,
        display_name,
        prompt,
        kind,
        provider,
        gen_fn,
        turn=turn,
        size=size,
    )
    registry = set_asset(registry, scope, asset_id, record)
    save_registry(registry)
    return record


def get_or_request_character_portrait(
    name: str,
    world_pack: dict,
    *,
    turn: int = 0,
    provider: VisualProvider | None = None,
    force: bool = False,
) -> dict[str, Any]:
    asset_id = normalize_asset_id(name)
    prompt = build_character_prompt(name, world_pack)
    return _resolve_or_generate(
        "characters",
        asset_id,
        name,
        prompt,
        "portrait",
        "generate_character",
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
    asset_id = normalize_asset_id(scene_key)
    display = str(context.get("scene") or scene_key)
    prompt = build_scene_prompt(scene_key, context)
    return _resolve_or_generate(
        "scenes",
        asset_id,
        display,
        prompt,
        "scene",
        "generate_scene",
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
    asset_id = normalize_asset_id(title) + "_map"
    prompt = build_world_map_prompt(world_pack)
    return _resolve_or_generate(
        "locations",
        asset_id,
        title,
        prompt,
        "world_map",
        "generate_world_map",
        turn=turn,
        size="1536x1024",
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
    asset_id = normalize_asset_id(faction_name) + "_territory"
    prompt = build_faction_map_prompt(faction_name, memory)
    return _resolve_or_generate(
        "factions",
        asset_id,
        faction_name,
        prompt,
        "faction_map",
        "generate_faction_map",
        turn=turn,
        size="1536x1024",
        provider=provider,
        force=force,
    )


def reset_visual_assets(*, persist: bool = True) -> None:
    """Clear registry and visual output cache."""
    from engine.visual.visual_registry import empty_registry

    clear_visual_output()
    save_registry(empty_registry(), persist=persist)
    if config.VISUAL_REGISTRY_PATH.exists() and not persist:
        try:
            config.VISUAL_REGISTRY_PATH.unlink()
        except OSError:
            pass
    logger.info("Visual assets reset")
