"""
identity_registry.py — V6.1 Visual Identity Registry (above asset registry)
"""

from __future__ import annotations

import copy
import logging
import shutil
import time
from typing import Any

import config
from engine import io_utils
from engine.visual.identity_prompt_builder import (
    extract_character_traits,
    extract_event_traits,
    extract_faction_traits,
    extract_location_traits,
)
from engine.visual.visual_identity import (
    VisualIdentity,
    entity_lookup_key,
    make_identity_id,
    seed_from_identity_id,
)

logger = logging.getLogger(__name__)


def empty_identity_registry() -> dict:
    return {"version": 1, "identities": {}, "entity_index": {}}


def normalize_identity_registry(raw: dict | None) -> dict:
    base = empty_identity_registry()
    if not isinstance(raw, dict):
        return base
    base["version"] = int(raw.get("version", 1) or 1)
    identities = raw.get("identities")
    if isinstance(identities, dict):
        base["identities"] = {
            str(k): v for k, v in identities.items()
            if isinstance(v, dict) and str(k).strip()
        }
    index = raw.get("entity_index")
    if isinstance(index, dict):
        base["entity_index"] = {str(k): str(v) for k, v in index.items() if str(k).strip() and str(v).strip()}
    return base


def ensure_identity_registry() -> dict:
    if (
        not config.VISUAL_IDENTITY_REGISTRY_PATH.exists()
        and config.VISUAL_IDENTITY_REGISTRY_DEFAULT_PATH.exists()
    ):
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config.VISUAL_IDENTITY_REGISTRY_DEFAULT_PATH, config.VISUAL_IDENTITY_REGISTRY_PATH)
    try:
        data = io_utils.read_json(config.VISUAL_IDENTITY_REGISTRY_PATH)
        if isinstance(data, dict):
            return normalize_identity_registry(data)
    except Exception:
        pass
    if config.VISUAL_IDENTITY_REGISTRY_DEFAULT_PATH.exists():
        return normalize_identity_registry(io_utils.read_json(config.VISUAL_IDENTITY_REGISTRY_DEFAULT_PATH))
    return empty_identity_registry()


def load_identity_registry() -> dict:
    return ensure_identity_registry()


def save_identity_registry(registry: dict, *, persist: bool = True) -> None:
    if not persist:
        return
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    io_utils.write_json(config.VISUAL_IDENTITY_REGISTRY_PATH, normalize_identity_registry(registry))


def get_identity(registry: dict, identity_id: str) -> VisualIdentity | None:
    raw = (registry.get("identities") or {}).get(identity_id)
    return VisualIdentity.from_dict(raw)


def resolve_identity(
    entity_type: str,
    entity_id: str,
    context: dict | None = None,
    *,
    persist: bool = True,
) -> VisualIdentity:
    """Map entity → VisualIdentity. Creates and locks identity on first access."""
    et = str(entity_type or "").strip().lower()
    eid = str(entity_id or "").strip() or "unknown"
    ctx = context if isinstance(context, dict) else {}
    lookup = entity_lookup_key(et, eid)

    registry = load_identity_registry()
    identity_id = (registry.get("entity_index") or {}).get(lookup)
    if identity_id:
        existing = get_identity(registry, identity_id)
        if existing:
            return existing

    identity = _create_identity(et, eid, ctx)
    registry = copy.deepcopy(registry)
    registry.setdefault("identities", {})[identity.identity_id] = {
        **identity.to_dict(),
        "created_at": int(time.time()),
    }
    registry.setdefault("entity_index", {})[lookup] = identity.identity_id
    save_identity_registry(registry, persist=persist)
    logger.info("Visual identity created %s for %s", identity.identity_id, lookup)
    return identity


def _create_identity(entity_type: str, entity_id: str, context: dict) -> VisualIdentity:
    identity_id = make_identity_id(entity_type, entity_id)
    if entity_type == "character":
        canonical, anchor, locked = extract_character_traits(entity_id, context)
    elif entity_type == "location":
        canonical, anchor, locked = extract_location_traits(entity_id, context)
    elif entity_type == "faction":
        canonical, anchor, locked = extract_faction_traits(entity_id, context)
    elif entity_type == "event":
        canonical, anchor, locked = extract_event_traits(entity_id, context)
    else:
        canonical, anchor, locked = {}, {}, []

    return VisualIdentity(
        identity_id=identity_id,
        entity_type=entity_type,
        entity_id=entity_id,
        canonical_traits=canonical,
        style_anchor=anchor,
        seed=seed_from_identity_id(identity_id),
        locked_descriptors=sorted(set(locked)),
    )


def list_identities(registry: dict | None = None) -> list[dict[str, Any]]:
    reg = registry if isinstance(registry, dict) else load_identity_registry()
    out: list[dict[str, Any]] = []
    for raw in (reg.get("identities") or {}).values():
        if isinstance(raw, dict):
            out.append(raw)
    return out
