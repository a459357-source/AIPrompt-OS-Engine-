"""
visual_registry.py — V6.0 Visual Asset Registry (Shared System)
================================================================
Single source of truth for visual asset metadata. User runtime data.
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

VISUAL_SCOPES = frozenset({"characters", "locations", "factions", "scenes"})


def empty_registry() -> dict:
    return {
        "version": 1,
        "characters": {},
        "locations": {},
        "factions": {},
        "scenes": {},
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
    for scope in VISUAL_SCOPES:
        bucket = raw.get(scope)
        if isinstance(bucket, dict):
            base[scope] = {
                str(k): v for k, v in bucket.items()
                if isinstance(v, dict) and str(k).strip()
            }
    return base


def get_asset(registry: dict, scope: str, asset_id: str) -> dict | None:
    if scope not in VISUAL_SCOPES:
        return None
    item = (registry.get(scope) or {}).get(asset_id)
    return item if isinstance(item, dict) else None


def set_asset(registry: dict, scope: str, asset_id: str, record: dict) -> dict:
    registry = copy.deepcopy(registry) if registry else empty_registry()
    if scope not in VISUAL_SCOPES:
        raise ValueError(f"invalid visual scope: {scope}")
    bucket = registry.setdefault(scope, {})
    bucket[str(asset_id)] = record
    return registry


def list_assets(registry: dict, scope: str) -> dict:
    if scope not in VISUAL_SCOPES:
        return {}
    data = registry.get(scope) or {}
    return data if isinstance(data, dict) else {}


def image_path_from_record(record: dict | None) -> str:
    if not isinstance(record, dict):
        return ""
    return str(record.get("image_path") or record.get("uri") or "").strip()


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
    created_turn: int = 0,
    prompt_hash: str = "",
    entity_id: str = "",
    meta: dict | None = None,
) -> dict[str, Any]:
    now = int(time.time())
    path = str(image_path or "").strip()
    return {
        "asset_id": asset_id,
        "entity_id": entity_id or display_name,
        "display_name": display_name,
        "prompt_hash": prompt_hash,
        "image_path": path,
        "uri": path,
        "provider": provider,
        "kind": kind,
        "created_turn": created_turn,
        "created_at": now,
        "updated_at": now,
        "meta": meta or {},
    }
