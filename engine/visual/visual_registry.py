"""
visual_registry.py — V6 Visual Asset Registry (Shared System)
"""

from __future__ import annotations

import copy
import hashlib
import logging
import re
import shutil
import time
from typing import Any

import config
from engine import io_utils

logger = logging.getLogger(__name__)

ENTITY_TYPES = frozenset({"character", "location", "faction", "event"})
VISUAL_SCOPES = frozenset({"characters", "locations", "factions", "events", "scenes"})

ENTITY_TYPE_TO_SCOPE = {
    "character": "characters",
    "location": "locations",
    "faction": "factions",
    "event": "events",
}

SCOPE_TO_ENTITY_TYPE = {v: k for k, v in ENTITY_TYPE_TO_SCOPE.items()}

_KIND_BY_ENTITY = {
    "character": "portrait",
    "location": "world_map",
    "faction": "faction_map",
    "event": "scene",
}


def entity_type_to_scope(entity_type: str) -> str:
    scope = ENTITY_TYPE_TO_SCOPE.get(str(entity_type or "").strip().lower())
    if not scope:
        raise ValueError(f"invalid entity_type: {entity_type!r}")
    return scope


def kind_for_entity_type(entity_type: str) -> str:
    return _KIND_BY_ENTITY.get(str(entity_type or "").strip().lower(), "visual")


def empty_registry() -> dict:
    return {
        "version": 1,
        "characters": {},
        "locations": {},
        "factions": {},
        "events": {},
    }


def normalize_asset_id(name: str) -> str:
    """Stable slug for registry keys; CJK names hash to asset_<hex>."""
    raw = (name or "").strip()
    if not raw:
        return "unknown"
    ascii_part = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")
    if ascii_part and ascii_part.isascii() and len(ascii_part) >= 2:
        return ascii_part[:64]
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"asset_{digest}"


def ensure_registry() -> dict:
    """Load registry or copy empty default template into data/."""
    if not config.VISUAL_REGISTRY_PATH.exists() and config.VISUAL_REGISTRY_DEFAULT_PATH.exists():
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config.VISUAL_REGISTRY_DEFAULT_PATH, config.VISUAL_REGISTRY_PATH)
    try:
        data = io_utils.read_json(config.VISUAL_REGISTRY_PATH)
        if isinstance(data, dict):
            return normalize_registry(data)
    except Exception:
        pass
    if config.VISUAL_REGISTRY_DEFAULT_PATH.exists():
        return normalize_registry(io_utils.read_json(config.VISUAL_REGISTRY_DEFAULT_PATH))
    return empty_registry()


def load_registry() -> dict:
    return ensure_registry()


def save_registry(registry: dict, *, persist: bool = True) -> None:
    if not persist:
        return
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    io_utils.write_json(config.VISUAL_REGISTRY_PATH, normalize_registry(registry))


def normalize_registry(raw: dict | None) -> dict:
    base = empty_registry()
    if not isinstance(raw, dict):
        return base
    base["version"] = int(raw.get("version", 1) or 1)
    for scope in ("characters", "locations", "factions", "events"):
        bucket = raw.get(scope)
        if isinstance(bucket, dict):
            base[scope] = {
                str(k): v for k, v in bucket.items()
                if isinstance(v, dict) and str(k).strip()
            }
    # migrate legacy scenes → events
    scenes = raw.get("scenes")
    if isinstance(scenes, dict):
        for k, v in scenes.items():
            if isinstance(v, dict) and str(k).strip() and k not in base["events"]:
                rec = copy.deepcopy(v)
                rec.setdefault("entity_type", "event")
                base["events"][str(k)] = rec
    return base


def _resolve_scope(scope: str) -> str:
    if scope == "scenes":
        return "events"
    if scope in ENTITY_TYPE_TO_SCOPE.values():
        return scope
    raise ValueError(f"invalid visual scope: {scope}")


def get_asset(registry: dict, scope: str, asset_id: str) -> dict | None:
    try:
        resolved = _resolve_scope(scope)
    except ValueError:
        return None
    item = (registry.get(resolved) or {}).get(asset_id)
    return item if isinstance(item, dict) else None


def set_asset(registry: dict, scope: str, asset_id: str, record: dict) -> dict:
    registry = copy.deepcopy(registry) if registry else empty_registry()
    resolved = _resolve_scope(scope)
    bucket = registry.setdefault(resolved, {})
    bucket[str(asset_id)] = record
    return registry


def list_assets(registry: dict, scope: str) -> dict:
    try:
        resolved = _resolve_scope(scope)
    except ValueError:
        return {}
    data = registry.get(resolved) or {}
    return data if isinstance(data, dict) else {}


def image_path_from_record(record: dict | None) -> str:
    if not isinstance(record, dict):
        return ""
    return str(record.get("image_path") or record.get("uri") or "").strip()


def find_by_identity_id(registry: dict, scope: str, identity_id: str) -> dict | None:
    if not identity_id:
        return None
    for record in list_assets(registry, scope).values():
        if not isinstance(record, dict):
            continue
        if str(record.get("identity_id", "")) == identity_id:
            return record
    return None


def find_by_prompt_hash(registry: dict, scope: str, prompt_hash: str) -> dict | None:
    """Find an existing registry entry in scope with the same prompt hash."""
    if not prompt_hash:
        return None
    for record in list_assets(registry, scope).values():
        if not isinstance(record, dict):
            continue
        if str(record.get("prompt_hash", "")) == prompt_hash:
            return record
    return None


def make_asset_record(
    *,
    asset_id: str,
    display_name: str,
    image_path: str,
    provider: str,
    kind: str,
    entity_type: str = "",
    identity_id: str = "",
    created_turn: int = 0,
    prompt_hash: str = "",
    entity_id: str = "",
    seed: int = 0,
    meta: dict | None = None,
) -> dict[str, Any]:
    now = int(time.time())
    path = str(image_path or "").strip()
    et = str(entity_type or "").strip().lower()
    record_meta = dict(meta or {})
    if seed:
        record_meta.setdefault("seed", seed)
    return {
        "asset_id": asset_id,
        "entity_type": et,
        "entity_id": entity_id or display_name,
        "identity_id": str(identity_id or "").strip(),
        "display_name": display_name,
        "prompt_hash": prompt_hash,
        "image_path": path,
        "uri": path,
        "provider": provider,
        "kind": kind,
        "created_turn": created_turn,
        "created_at": now,
        "updated_at": now,
        "meta": record_meta,
    }
