"""
bootstrap_generator.py — Generate minimal narrative_routes from world_pack on new story.

Design contract:
  - Only populates empty slots — never overwrites existing data.
  - Does NOT introduce new data formats or APIs.
  - Intro node is the only node created; downstream routing stays on default nodes.
"""

from __future__ import annotations

import logging
from typing import Any

import config
from engine import io_utils

logger = logging.getLogger(__name__)


def bootstrap_narrative_routes(world_pack: dict) -> dict:
    """Initialize narrative_routes.json from world_pack data.

    Merges character_entry / location_entry / faction_entry mappings
    (all pointing to the default opening node "midnight_talk") and
    creates a world-specific "intro" node for context display.

    Returns the merged routes dict (also persisted to disk).
    """
    world = world_pack.get("world", world_pack)
    characters: list[dict] = world.get("characters", [])
    factions: list[dict] = world.get("factions", [])
    locations: list[dict] = world.get("locations", [])

    # Build entry patches
    char_entry = _build_character_entry(characters)
    loc_entry = _build_location_entry(locations)
    faction_entry = _build_faction_entry(factions)

    # Build intro node
    intro_context = _build_intro_context(characters, factions, locations)
    intro_node = {
        "context": intro_context,
        "participants": [c.get("name", "") for c in characters[:5] if c.get("name")],
        "choices": [
            {
                "choice_id": "explore",
                "text": "探索当前局势",
                "target_event_id": "midnight_talk",
                "tone": "neutral",
            },
            {
                "choice_id": "interact",
                "text": "与关键人物交谈",
                "target_event_id": "midnight_talk",
                "tone": "warm",
            },
            {
                "choice_id": "observe",
                "text": "观察事态发展",
                "target_event_id": "midnight_talk",
                "tone": "cautious",
            },
        ],
    }

    patch = {
        "character_entry": char_entry,
        "location_entry": loc_entry,
        "faction_entry": faction_entry,
        "nodes": {"intro": intro_node},
    }

    return _merge_into_narrative_routes(patch)


# ── Entry builders ──────────────────────────────────────────────────

def _build_character_entry(characters: list[dict]) -> dict[str, str]:
    return {c["name"]: "midnight_talk" for c in characters if c.get("name")}


def _build_location_entry(locations: list[dict]) -> dict[str, str]:
    return {loc["name"]: "midnight_talk" for loc in locations if loc.get("name")}


def _build_faction_entry(factions: list[dict]) -> dict[str, str]:
    return {f["name"]: "midnight_talk" for f in factions if f.get("name")}


def _build_intro_context(
    characters: list[dict],
    factions: list[dict],
    locations: list[dict],
) -> str:
    world = {}
    try:
        world = io_utils.read_yaml(config.WORLD_PACK_PATH).get("world", {})
    except Exception:
        pass
    title = world.get("title", "")
    genre = world.get("genre", "")
    setting = world.get("setting", "")
    scene = ""
    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
        scene = state.get("scene", "")
    except Exception:
        pass

    parts = [f"故事「{title}」开局"]
    if genre:
        parts.append(f"类型：{genre}")
    if scene:
        parts.append(f"当前场景：{scene}")
    if setting:
        parts.append(f"背景：{setting[:200]}")

    char_names = [c.get("name", "") for c in characters[:8] if c.get("name")]
    if char_names:
        parts.append(f"关键角色：{'、'.join(char_names)}")

    fac_names = [f.get("name", "") for f in factions[:5] if f.get("name")]
    if fac_names:
        parts.append(f"主要势力：{'、'.join(fac_names)}")

    loc_names = [loc.get("name", "") for loc in locations[:3] if loc.get("name")]
    if loc_names:
        parts.append(f"地点：{'、'.join(loc_names)}")

    return "。".join(p for p in parts if p) + "。"


# ── Merge logic ─────────────────────────────────────────────────────

def _merge_into_narrative_routes(patch: dict) -> dict:
    """Load existing narrative_routes.json, fill only missing keys, save.

    - If a key in the current file is non-empty (e.g. nodes already populated),
      it is NOT overwritten.
    - Only empty maps/lists are filled from *patch*.
    """
    from engine.narrative.narrative_router import ensure_narrative_routes

    routes = ensure_narrative_routes()

    def _is_empty(val: Any) -> bool:
        if isinstance(val, dict):
            return len(val) == 0
        if isinstance(val, list):
            return len(val) == 0
        return not val

    # Merge top-level entry maps
    for key in ("character_entry", "location_entry", "faction_entry"):
        current = routes.get(key)
        incoming = patch.get(key)
        if _is_empty(current) and isinstance(incoming, dict):
            routes[key] = incoming
            logger.info("narrative_routes.%s initialized (%d entries)", key, len(incoming))

    # Merge nodes — always add intro, never overwrite existing
    current_nodes = routes.get("nodes") or {}
    incoming_nodes = patch.get("nodes") or {}
    for node_id, node_def in incoming_nodes.items():
        if node_id not in current_nodes and isinstance(node_def, dict):
            current_nodes[node_id] = node_def
            logger.info("narrative_routes.nodes.%s initialized", node_id)
    routes["nodes"] = current_nodes

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    io_utils.write_json(config.NARRATIVE_ROUTES_PATH, routes)
    logger.info("narrative_routes.json saved -> %s", config.NARRATIVE_ROUTES_PATH)

    return routes
