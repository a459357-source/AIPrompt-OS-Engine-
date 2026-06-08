"""
visual_runtime.py — V6 Visual Runtime Core (single legal entry)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import config
from engine.visual import image_generation
from engine.visual.provider_factory import get_visual_provider
from engine.visual.visual_cache import (
    exists,
    memory_get,
    memory_put,
    uri_for_path,
)
from engine.visual.visual_object import VisualObject, build_visual_object
from engine.visual.visual_provider import VisualProvider
from engine.visual.visual_registry import (
    entity_type_to_scope,
    find_by_identity_id,
    find_by_prompt_hash,
    get_asset,
    image_path_from_record,
    kind_for_entity_type,
    load_registry,
    make_asset_record,
    save_registry,
    set_asset,
)

logger = logging.getLogger(__name__)


def get_visual(
    entity_type: str,
    entity_id: str,
    context: dict | None = None,
    *,
    turn: int = 0,
    provider: VisualProvider | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """
    Single entry for visual asset resolution.

    Flow: VisualObject → registry → L1 → L2 → provider (miss only) → store → image_path
    """
    if not config.VISUAL_SYSTEM_ENABLED:
        return {}

    obj = build_visual_object(entity_type, entity_id, context)
    scope = entity_type_to_scope(obj.entity_type)
    provider = provider or get_visual_provider()

    if not force:
        cached = memory_get(obj.idempotency_key)
        if _record_valid(cached):
            return cached

        registry = load_registry()
        existing = get_asset(registry, scope, obj.asset_id)
        if _record_valid(existing) and _record_matches_object(existing, obj):
            enriched = _ensure_identity_on_record(existing, obj)
            if enriched is not existing:
                registry = set_asset(registry, scope, obj.asset_id, enriched)
                save_registry(registry)
            memory_put(obj.idempotency_key, enriched)
            return enriched

        if obj.entity_type == "character" and obj.identity_id:
            identity_match = find_by_identity_id(registry, scope, obj.identity_id)
            if identity_match and _record_valid(identity_match):
                record = _bind_existing(obj, identity_match, provider.provider_name, turn)
                registry = set_asset(registry, scope, obj.asset_id, record)
                save_registry(registry)
                memory_put(obj.idempotency_key, record)
                return record

        prompt_match = find_by_prompt_hash(registry, scope, obj.prompt_hash)
        if prompt_match and _record_valid(prompt_match):
            record = _bind_existing(obj, prompt_match, provider.provider_name, turn)
            registry = set_asset(registry, scope, obj.asset_id, record)
            save_registry(registry)
            memory_put(obj.idempotency_key, record)
            logger.debug(
                "Visual prompt cache hit scope=%s entity_id=%s",
                scope,
                obj.entity_id,
            )
            return record

        if exists(scope, obj.asset_id):
            record = _record_from_filesystem(obj, existing, provider.provider_name, turn)
            registry = set_asset(registry, scope, obj.asset_id, record)
            save_registry(registry)
            memory_put(obj.idempotency_key, record)
            return record

    gen_fn = getattr(provider, obj.provider_method)
    gen_result = image_generation.write_generated_image(scope, obj, provider, gen_fn)
    record = make_asset_record(
        asset_id=obj.asset_id,
        display_name=obj.name,
        image_path=gen_result["image_path"],
        entity_id=obj.entity_id,
        entity_type=obj.entity_type,
        identity_id=obj.identity_id,
        provider=gen_result["provider"],
        kind=kind_for_entity_type(obj.entity_type),
        created_turn=turn,
        prompt_hash=obj.prompt_hash,
        seed=obj.seed,
        meta={"size": gen_result["size"], "bytes": gen_result["bytes"]},
    )
    registry = load_registry()
    registry = set_asset(registry, scope, obj.asset_id, record)
    save_registry(registry)
    memory_put(obj.idempotency_key, record)
    logger.info(
        "Visual generated entity_type=%s entity_id=%s provider=%s",
        obj.entity_type,
        obj.entity_id,
        gen_result["provider"],
    )
    return record


def _path_from_record(record: dict | None) -> Path | None:
    rel = image_path_from_record(record)
    if not rel:
        return None
    path = config.ROOT / rel.replace("\\", "/")
    if path.is_file() and path.stat().st_size > 0:
        return path
    return None


def _record_valid(record: dict | None) -> bool:
    return _path_from_record(record) is not None


def _record_matches_object(record: dict, obj: VisualObject) -> bool:
    if obj.entity_type == "character" and obj.identity_id:
        rid = str(record.get("identity_id") or "")
        if rid:
            return rid == obj.identity_id
        return str(record.get("entity_id") or "") == obj.entity_id
    return str(record.get("prompt_hash", "")) == obj.prompt_hash


def _ensure_identity_on_record(record: dict, obj: VisualObject) -> dict:
    if str(record.get("identity_id") or "") == obj.identity_id:
        return record
    updated = dict(record)
    updated["identity_id"] = obj.identity_id
    if obj.seed and not (updated.get("meta") or {}).get("seed"):
        meta = dict(updated.get("meta") or {})
        meta["seed"] = obj.seed
        updated["meta"] = meta
    return updated


def _bind_existing(
    obj: VisualObject,
    source: dict,
    provider_name: str,
    turn: int,
) -> dict[str, Any]:
    image_path = image_path_from_record(source)
    if not _record_valid(source):
        return {}
    return make_asset_record(
        asset_id=obj.asset_id,
        display_name=obj.name,
        image_path=image_path,
        entity_id=obj.entity_id,
        entity_type=obj.entity_type,
        identity_id=obj.identity_id,
        provider=str(source.get("provider") or provider_name),
        kind=kind_for_entity_type(obj.entity_type),
        created_turn=turn,
        prompt_hash=obj.prompt_hash,
        seed=obj.seed,
        meta=dict(source.get("meta") or {}),
    )


def _record_from_filesystem(
    obj: VisualObject,
    existing: dict | None,
    provider_name: str,
    turn: int,
) -> dict[str, Any]:
    from engine.visual.visual_cache import cache_path

    path = cache_path(scope=entity_type_to_scope(obj.entity_type), asset_id=obj.asset_id)
    return make_asset_record(
        asset_id=obj.asset_id,
        display_name=obj.name,
        image_path=uri_for_path(path),
        entity_id=obj.entity_id,
        entity_type=obj.entity_type,
        identity_id=obj.identity_id,
        provider=str((existing or {}).get("provider") or provider_name),
        kind=kind_for_entity_type(obj.entity_type),
        created_turn=int((existing or {}).get("created_turn", turn) or turn),
        prompt_hash=obj.prompt_hash,
        seed=obj.seed,
    )
