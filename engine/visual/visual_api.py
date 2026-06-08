"""
visual_api.py — V6.5 read-only Visual World Explorer API (no generation)
"""

from __future__ import annotations

from typing import Any

import config
from engine import io_utils
from engine.visual.identity_registry import load_identity_registry, list_identities
from engine.visual.visual_identity import VisualIdentity
from engine.visual.visual_registry import ENTITY_TYPE_TO_SCOPE, list_assets, load_registry


def public_image_url(image_path: str) -> str:
    rel = str(image_path or "").replace("\\", "/").strip()
    if rel.startswith("output/"):
        rel = rel[len("output/"):]
    return f"/static/{rel}" if rel else ""


def _cache_hit(image_path: str) -> bool:
    if not image_path:
        return False
    rel = str(image_path).replace("\\", "/")
    if rel.startswith("output/"):
        rel = rel[len("output/"):]
    path = config.OUTPUT_DIR / rel if rel else None
    if path and path.is_file() and path.stat().st_size > 0:
        return True
    root_path = config.ROOT / rel.replace("\\", "/")
    return root_path.is_file() and root_path.stat().st_size > 0


def _enrich_asset(
    record: dict,
    identity: VisualIdentity | None = None,
    *,
    scope: str = "",
) -> dict[str, Any]:
    image_path = str(record.get("image_path") or record.get("uri") or "")
    meta = record.get("meta") if isinstance(record.get("meta"), dict) else {}
    hit = _cache_hit(image_path)
    asset_id = str(record.get("asset_id") or "")
    return {
        "registry_id": asset_id,
        "asset_id": asset_id,
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
        "cache_status": "hit" if hit else "miss",
        "cache_hit": hit,
        "scope": scope,
    }


def _identity_map() -> dict[str, dict]:
    reg = load_identity_registry()
    return {
        str(k): v for k, v in (reg.get("identities") or {}).items()
        if isinstance(v, dict)
    }


def _entity_index() -> dict[str, str]:
    reg = load_identity_registry()
    return {
        str(k): str(v)
        for k, v in (reg.get("entity_index") or {}).items()
        if str(k).strip() and str(v).strip()
    }


def _resolve_identity_id(record: dict, entity_index: dict[str, str]) -> str:
    iid = str(record.get("identity_id") or "").strip()
    if iid:
        return iid
    et = str(record.get("entity_type") or "").strip().lower()
    eid = str(record.get("entity_id") or "").strip()
    if et and eid:
        return entity_index.get(f"{et}:{eid}", "")
    return ""


def _characters_at_turn(turn: int) -> list[str]:
    """Read-only: names present in session at event turn."""
    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    except Exception:
        return []
    names: set[str] = set()
    chars = state.get("characters") or {}
    if isinstance(chars, dict):
        for sc in chars.values():
            if isinstance(sc, dict) and sc.get("name"):
                names.add(str(sc["name"]))
    history = state.get("history") or []
    if isinstance(history, list):
        for entry in history:
            if not isinstance(entry, dict):
                continue
            if int(entry.get("turn") or 0) != int(turn or 0):
                continue
            for key in ("characters", "active_characters", "present_characters"):
                block = entry.get(key)
                if isinstance(block, dict):
                    for sc in block.values():
                        if isinstance(sc, dict) and sc.get("name"):
                            names.add(str(sc["name"]))
                elif isinstance(block, list):
                    for name in block:
                        if name:
                            names.add(str(name))
    return sorted(names)


def _character_links_readonly() -> list[dict[str, str]]:
    """Read-only relationship edges for world explorer."""
    links: list[dict[str, str]] = []
    try:
        data = io_utils.read_json(config.RELATIONSHIP_GRAPH_PATH)
        edges = data.get("edges") if isinstance(data, dict) else {}
        if isinstance(edges, dict):
            for key, edge in edges.items():
                if not isinstance(edge, dict):
                    continue
                src = str(edge.get("from") or edge.get("source") or "").strip()
                tgt = str(edge.get("to") or edge.get("target") or "").strip()
                if not src or not tgt:
                    parts = str(key).split("→", 1)
                    if len(parts) == 2:
                        src, tgt = parts[0].strip(), parts[1].strip()
                if src and tgt:
                    links.append({
                        "from": src,
                        "to": tgt,
                        "label": str(edge.get("relation") or edge.get("type") or ""),
                    })
    except Exception:
        pass
    return links


def get_visual_status() -> dict[str, Any]:
    return {
        "enabled": bool(config.VISUAL_SYSTEM_ENABLED),
        "provider": str(getattr(config, "VISUAL_PROVIDER", "stub")),
        "cache_enabled": bool(config.VISUAL_CACHE_ENABLED),
        "read_only": True,
    }


def get_character_gallery() -> list[dict[str, Any]]:
    """Identity View list — grouped by identity_id."""
    registry = load_registry()
    identities = _identity_map()
    entity_index = _entity_index()
    assets_by_identity: dict[str, list[dict[str, Any]]] = {}

    for record in list_assets(registry, "characters").values():
        if not isinstance(record, dict):
            continue
        iid = _resolve_identity_id(record, entity_index)
        identity = VisualIdentity.from_dict(identities.get(iid)) if iid else None
        enriched = _enrich_asset(record, identity, scope="characters")
        key = iid or f"orphan:{record.get('asset_id')}"
        assets_by_identity.setdefault(key, []).append(enriched)

    views: list[dict[str, Any]] = []
    seen: set[str] = set()

    for iid, raw in identities.items():
        if str(raw.get("entity_type") or "").lower() != "character":
            continue
        identity = VisualIdentity.from_dict(raw)
        assets = sorted(
            assets_by_identity.get(iid, []),
            key=lambda x: (int(x.get("created_at") or 0), str(x.get("asset_id") or "")),
        )
        latest = assets[-1] if assets else None
        content_template: dict = {}
        try:
            from engine.templates.template_registry import get_entity_template
            content_template = get_entity_template("character", str(raw.get("entity_id") or "")) or {}
        except Exception:
            pass
        views.append({
            "identity_id": iid,
            "entity_name": str(raw.get("entity_id") or ""),
            "latest_image": latest["image_url"] if latest else "",
            "latest_image_path": latest["image_path"] if latest else "",
            "all_assets": assets,
            "traits": identity.canonical_traits if identity else {},
            "style_anchor": identity.style_anchor if identity else {},
            "content_template": content_template,
            "seed": identity.seed if identity else 0,
        })
        seen.add(iid)

    for key, assets in assets_by_identity.items():
        if key.startswith("orphan:") or key in seen:
            if key in seen:
                continue
        assets = sorted(assets, key=lambda x: int(x.get("created_at") or 0))
        latest = assets[-1] if assets else None
        iid = str(assets[0].get("identity_id") or key) if assets else key
        views.append({
            "identity_id": iid,
            "entity_name": str(assets[0].get("entity_id") or assets[0].get("display_name") or "") if assets else "",
            "latest_image": latest["image_url"] if latest else "",
            "latest_image_path": latest["image_path"] if latest else "",
            "all_assets": assets,
            "traits": {},
            "style_anchor": {},
            "seed": int(assets[0].get("seed") or 0) if assets else 0,
        })

    views.sort(key=lambda x: str(x.get("entity_name") or x.get("identity_id") or ""))
    return views


def get_world_explorer() -> dict[str, Any]:
    """World View — locations, factions, character identity summaries, links."""
    registry = load_registry()
    identities = _identity_map()
    entity_index = _entity_index()
    locations: list[dict[str, Any]] = []
    factions: list[dict[str, Any]] = []

    for record in list_assets(registry, "locations").values():
        if isinstance(record, dict):
            iid = _resolve_identity_id(record, entity_index)
            locations.append(
                _enrich_asset(
                    record,
                    VisualIdentity.from_dict(identities.get(iid)),
                    scope="locations",
                )
            )
    for record in list_assets(registry, "factions").values():
        if isinstance(record, dict):
            iid = _resolve_identity_id(record, entity_index)
            factions.append(
                _enrich_asset(
                    record,
                    VisualIdentity.from_dict(identities.get(iid)),
                    scope="factions",
                )
            )

    locations.sort(key=lambda x: str(x.get("display_name") or ""))
    factions.sort(key=lambda x: str(x.get("display_name") or ""))

    return {
        "locations": locations,
        "factions": factions,
        "characters": get_character_gallery(),
        "character_links": _character_links_readonly(),
    }


def get_event_timeline() -> list[dict[str, Any]]:
    """Event View — time-sorted with scene images and character participation."""
    registry = load_registry()
    identities = _identity_map()
    entity_index = _entity_index()
    items: list[dict[str, Any]] = []

    for record in list_assets(registry, "events").values():
        if not isinstance(record, dict):
            continue
        iid = _resolve_identity_id(record, entity_index)
        identity = VisualIdentity.from_dict(identities.get(iid)) if iid else None
        asset = _enrich_asset(record, identity, scope="events")
        turn = int(record.get("created_turn") or 0)
        event_id = str(record.get("asset_id") or record.get("entity_id") or "")
        items.append({
            "event_id": event_id,
            "display_name": str(record.get("display_name") or record.get("entity_id") or event_id),
            "linked_assets": [asset],
            "scene_images": [asset["image_url"]] if asset.get("image_url") else [],
            "characters": _characters_at_turn(turn),
            "timestamp": int(record.get("created_at") or 0),
            "created_turn": turn,
            "identity_id": asset.get("identity_id", ""),
            "prompt_hash": asset.get("prompt_hash", ""),
        })

    items.sort(key=lambda x: (int(x.get("created_turn") or 0), int(x.get("timestamp") or 0)))
    return items


def get_visual_debug_payload() -> dict[str, Any]:
    registry = load_registry()
    identity_reg = load_identity_registry()
    identities = identity_reg.get("identities") or {}
    entity_index = _entity_index()
    assets: list[dict[str, Any]] = []

    for entity_type, scope in ENTITY_TYPE_TO_SCOPE.items():
        for record in list_assets(registry, scope).values():
            if not isinstance(record, dict):
                continue
            iid = _resolve_identity_id(record, entity_index)
            identity = VisualIdentity.from_dict(identities.get(iid)) if iid else None
            entry = _enrich_asset(record, identity, scope=scope)
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
