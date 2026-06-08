"""
narrative_router.py — V6.6 choice → next_event mapping (no generation)
"""

from __future__ import annotations

import copy
import logging
import shutil
from typing import Any

import config
from engine import io_utils
from engine.event_director import ensure_event_catalog

logger = logging.getLogger(__name__)


def empty_narrative_routes() -> dict:
    return {
        "version": 1,
        "visual_asset_map": {},
        "character_entry": {},
        "location_entry": {},
        "nodes": {},
    }


def ensure_narrative_routes() -> dict:
    if not config.NARRATIVE_ROUTES_PATH.exists() and config.NARRATIVE_ROUTES_DEFAULT_PATH.exists():
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config.NARRATIVE_ROUTES_DEFAULT_PATH, config.NARRATIVE_ROUTES_PATH)
    try:
        data = io_utils.read_json(config.NARRATIVE_ROUTES_PATH)
        if isinstance(data, dict):
            return _normalize_routes(data)
    except Exception:
        pass
    if config.NARRATIVE_ROUTES_DEFAULT_PATH.exists():
        return _normalize_routes(io_utils.read_json(config.NARRATIVE_ROUTES_DEFAULT_PATH))
    return empty_narrative_routes()


def _normalize_routes(raw: dict) -> dict:
    base = empty_narrative_routes()
    if not isinstance(raw, dict):
        return base
    base["version"] = int(raw.get("version", 1) or 1)
    for key in ("visual_asset_map", "character_entry", "location_entry"):
        block = raw.get(key)
        if isinstance(block, dict):
            base[key] = {str(k): str(v) for k, v in block.items() if str(k).strip()}
    nodes = raw.get("nodes")
    if isinstance(nodes, dict):
        base["nodes"] = {str(k): v for k, v in nodes.items() if isinstance(v, dict)}
    return base


def resolve_canonical_event_id(event_id: str) -> str:
    """Map visual asset id → catalog narrative event id."""
    eid = str(event_id or "").strip()
    if not eid:
        return ""
    routes = ensure_narrative_routes()
    mapped = (routes.get("visual_asset_map") or {}).get(eid)
    if mapped:
        return mapped
    catalog = ensure_event_catalog()
    if eid in (catalog.get("events") or {}):
        return eid
    if eid in (routes.get("nodes") or {}):
        return eid
    return eid


def get_node_definition(event_id: str) -> dict[str, Any]:
    canonical = resolve_canonical_event_id(event_id)
    routes = ensure_narrative_routes()
    nodes = routes.get("nodes") or {}
    if canonical in nodes:
        return copy.deepcopy(nodes[canonical])
    return _fallback_node_definition(canonical)


def _fallback_node_definition(event_id: str) -> dict[str, Any]:
    catalog = ensure_event_catalog()
    events = catalog.get("events") or {}
    entry = events.get(event_id) if isinstance(events, dict) else None
    label = str((entry or {}).get("label") or event_id)
    category = str((entry or {}).get("category") or "unknown")
    return {
        "context": f"叙事节点：{label}（{category}）",
        "choices": [
            {
                "choice_id": "continue",
                "text": f"继续推进：{label}",
                "target_event_id": "act_transition",
                "tone": "neutral",
            },
            {
                "choice_id": "observe",
                "text": "观察局势",
                "target_event_id": event_id,
                "tone": "cautious",
            },
            {
                "choice_id": "retreat",
                "text": "暂时抽身",
                "target_event_id": "act_transition",
                "tone": "neutral",
            },
        ],
    }


def get_choices_for_event(event_id: str) -> list[dict[str, Any]]:
    node_def = get_node_definition(event_id)
    choices = node_def.get("choices")
    if not isinstance(choices, list):
        return []
    out: list[dict[str, Any]] = []
    for raw in choices:
        if not isinstance(raw, dict):
            continue
        cid = str(raw.get("choice_id") or "").strip()
        text = str(raw.get("text") or "").strip()
        target = str(raw.get("target_event_id") or raw.get("target_event_hint") or "").strip()
        if not cid or not text or not target:
            continue
        out.append({
            "choice_id": cid,
            "text": text,
            "target_event_id": target,
            "target_event_hint": target,
            "tone": str(raw.get("tone") or "neutral"),
        })
    return out


def route_choice(event_id: str, choice_id: str) -> dict[str, Any]:
    """Map choice to next_event_id — mapping only, no LLM."""
    canonical = resolve_canonical_event_id(event_id)
    choices = get_choices_for_event(canonical)
    for choice in choices:
        if choice["choice_id"] == choice_id:
            next_id = resolve_canonical_event_id(choice["target_event_id"])
            return {
                "ok": True,
                "event_id": canonical,
                "choice_id": choice_id,
                "next_event_id": next_id,
                "tone": choice.get("tone", "neutral"),
            }
    return {
        "ok": False,
        "event_id": canonical,
        "choice_id": choice_id,
        "error": f"unknown choice: {choice_id}",
    }


def resolve_character_entry(character_name: str) -> str:
    name = str(character_name or "").strip()
    routes = ensure_narrative_routes()
    entry = (routes.get("character_entry") or {}).get(name)
    if entry:
        return resolve_canonical_event_id(entry)
    return resolve_canonical_event_id("midnight_talk")


def resolve_location_entry(location_name: str) -> str:
    name = str(location_name or "").strip()
    routes = ensure_narrative_routes()
    entry = (routes.get("location_entry") or {}).get(name)
    if entry:
        return resolve_canonical_event_id(entry)
    return resolve_canonical_event_id("political_pressure")


def resolve_visual_event_entry(visual_event_id: str) -> str:
    return resolve_canonical_event_id(visual_event_id)
