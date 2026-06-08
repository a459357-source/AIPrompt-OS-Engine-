"""
visual_api.py — V6.5 read-only Visual API helpers (no provider / no writes)
"""

from __future__ import annotations

from typing import Any

import config
from engine.visual.identity_registry import load_identity_registry, list_identities
from engine.visual.visual_identity import VisualIdentity
from engine.visual.visual_registry import ENTITY_TYPE_TO_SCOPE, list_assets, load_registry


def public_image_url(image_path: str) -> str:
    rel = str(image_path or "").replace("\\", "/").strip()
    if rel.startswith("output/"):
        rel = rel[len("output/"):]
    return f"/static/{rel}" if rel else ""


def _enrich_asset(record: dict, identity: VisualIdentity | None = None) -> dict[str, Any]:
    image_path = str(record.get("image_path") or record.get("uri") or "")
    meta = record.get("meta") if isinstance(record.get("meta"), dict) else {}
    return {
        "asset_id": record.get("asset_id", ""),
        "entity_type": record.get("entity_type", ""),
        "entity_id": record.get("entity_id", ""),
        "identity_id": record.get("identity_id", ""),
        "display_name": record.get("display_name", ""),
        "prompt_hash": record.get("prompt_hash", ""),
        "image_path": image_path,
        "image_url": public_image_url(image_path),
        "provider": record.get("provider", ""),
        "kind": record.get("kind", ""),
        "created_turn": record.get("created_turn", 0),
        "created_at": record.get("created_at", 0),
        "seed": meta.get("seed") or (identity.seed if identity else 0),
        "cache_status": "hit" if image_path else "miss",
    }


def _identity_map() -> dict[str, dict]:
    reg = load_identity_registry()
    return {
        str(k): v for k, v in (reg.get("identities") or {}).items()
        if isinstance(v, dict)
    }


def get_visual_status() -> dict[str, Any]:
    return {
        "enabled": bool(config.VISUAL_SYSTEM_ENABLED),
        "provider": str(getattr(config, "VISUAL_PROVIDER", "stub")),
        "cache_enabled": bool(config.VISUAL_CACHE_ENABLED),
    }


def get_character_gallery() -> list[dict[str, Any]]:
    registry = load_registry()
    identities = _identity_map()
    items: list[dict[str, Any]] = []
    for record in list_assets(registry, "characters").values():
        if not isinstance(record, dict):
            continue
        iid = str(record.get("identity_id") or "")
        identity = VisualIdentity.from_dict(identities.get(iid))
        item = _enrich_asset(record, identity)
        if identity:
            item["identity"] = identity.to_dict()
        items.append(item)
    items.sort(key=lambda x: str(x.get("display_name") or ""))
    return items


def get_world_explorer() -> dict[str, list[dict[str, Any]]]:
    registry = load_registry()
    identities = _identity_map()
    locations: list[dict[str, Any]] = []
    factions: list[dict[str, Any]] = []
    for record in list_assets(registry, "locations").values():
        if isinstance(record, dict):
            iid = str(record.get("identity_id") or "")
            locations.append(_enrich_asset(record, VisualIdentity.from_dict(identities.get(iid))))
    for record in list_assets(registry, "factions").values():
        if isinstance(record, dict):
            iid = str(record.get("identity_id") or "")
            factions.append(_enrich_asset(record, VisualIdentity.from_dict(identities.get(iid))))
    locations.sort(key=lambda x: str(x.get("display_name") or ""))
    factions.sort(key=lambda x: str(x.get("display_name") or ""))
    return {"locations": locations, "factions": factions}


def get_event_timeline() -> list[dict[str, Any]]:
    registry = load_registry()
    identities = _identity_map()
    items: list[dict[str, Any]] = []
    for record in list_assets(registry, "events").values():
        if not isinstance(record, dict):
            continue
        iid = str(record.get("identity_id") or "")
        items.append(_enrich_asset(record, VisualIdentity.from_dict(identities.get(iid))))
    items.sort(key=lambda x: (int(x.get("created_turn") or 0), int(x.get("created_at") or 0)))
    return items


def get_visual_debug_payload() -> dict[str, Any]:
    registry = load_registry()
    identity_reg = load_identity_registry()
    assets: list[dict[str, Any]] = []
    for entity_type, scope in ENTITY_TYPE_TO_SCOPE.items():
        for record in list_assets(registry, scope).values():
            if not isinstance(record, dict):
                continue
            iid = str(record.get("identity_id") or "")
            identity = VisualIdentity.from_dict((identity_reg.get("identities") or {}).get(iid))
            entry = _enrich_asset(record, identity)
            entry["scope"] = scope
            if identity:
                entry["canonical_traits"] = identity.canonical_traits
                entry["style_anchor"] = identity.style_anchor
                entry["locked_descriptors"] = identity.locked_descriptors
            assets.append(entry)
    return {
        "status": get_visual_status(),
        "identities": list_identities(identity_reg),
        "assets": assets,
    }
