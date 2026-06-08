"""
asset_manager.py — V6.0 Visual Asset Manager (public API)
"""

from __future__ import annotations

import logging
from typing import Any

import config
from engine.visual import image_generation
from engine.visual.provider_factory import get_visual_provider
from engine.visual.visual_cache import (
    cache_path,
    clear_visual_output,
    exists,
    prompt_hash,
    uri_for_path,
)
from engine.visual.visual_context import (
    build_character_prompt,
    build_faction_map_prompt,
    build_scene_prompt,
    build_world_map_prompt,
)
from engine.visual.visual_provider import VisualProvider
from engine.visual.visual_registry import (
    find_by_prompt_hash,
    get_asset,
    image_path_from_record,
    load_registry,
    make_asset_record,
    normalize_asset_id,
    save_registry,
    set_asset,
)

logger = logging.getLogger(__name__)


def _path_from_record(record: dict | None) -> Path | None:
    rel = image_path_from_record(record)
    if not rel:
        return None
    path = config.ROOT / rel.replace("\\", "/")
    if path.is_file() and path.stat().st_size > 0:
        return path
    return None


def _registry_record_valid(record: dict | None) -> bool:
    return _path_from_record(record) is not None


def _record_from_existing(
    *,
    asset_id: str,
    display_name: str,
    kind: str,
    turn: int,
    prompt: str,
    source: dict,
    provider_name: str,
) -> dict[str, Any]:
    src_path = _path_from_record(source)
    image_path = image_path_from_record(source)
    if src_path is None:
        return {}
    return make_asset_record(
        asset_id=asset_id,
        display_name=display_name,
        image_path=image_path,
        entity_id=str(source.get("entity_id") or display_name),
        provider=str(source.get("provider") or provider_name),
        kind=kind,
        created_turn=turn,
        prompt_hash=prompt_hash(prompt),
        meta=dict(source.get("meta") or {}),
    )


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
    phash = prompt_hash(prompt)

    if not force:
        existing = get_asset(registry, scope, asset_id)
        if _registry_record_valid(existing):
            if str(existing.get("prompt_hash", "")) == phash or not phash:
                return existing

        prompt_match = find_by_prompt_hash(registry, scope, phash)
        if prompt_match and _registry_record_valid(prompt_match):
            record = _record_from_existing(
                asset_id=asset_id,
                display_name=display_name,
                kind=kind,
                turn=turn,
                prompt=prompt,
                source=prompt_match,
                provider_name=provider.provider_name,
            )
            if record:
                registry = set_asset(registry, scope, asset_id, record)
                save_registry(registry)
                logger.debug("Visual prompt cache hit scope=%s asset_id=%s", scope, asset_id)
                return record

        if exists(scope, asset_id):
            path = cache_path(scope, asset_id)
            record = make_asset_record(
                asset_id=asset_id,
                display_name=display_name,
                image_path=uri_for_path(path),
                entity_id=display_name,
                provider=(
                    str((existing or {}).get("provider") or provider.provider_name)
                ),
                kind=kind,
                created_turn=int((existing or {}).get("created_turn", turn) or turn),
                prompt_hash=phash,
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
        "generate_character_portrait",
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
        "generate_scene_image",
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
