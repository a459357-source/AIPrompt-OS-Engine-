"""
bootstrap_generator.py — Passive narrative enhancement layer for /game.

Design contract:
  - narrative_routes is a SENSORY enhancement, NOT a story controller.
  - It provides scene context, participant visibility, and visual mapping.
  - It MUST NOT replace AI story or AI options.
  - It MUST NOT introduce a new narrative graph system.
  - choices is always [] — AI options remain the single source of truth.
"""

from __future__ import annotations

import logging
from typing import Any

import config
from engine import io_utils

logger = logging.getLogger(__name__)


# ── Main entry: called from NewStory form + bootstrap import ──────────

def init_narrative_for_game(dataset: dict, session_state: dict) -> dict:
    """Generate a passive game enhancement patch from world data + session state.

    Returns a patch dict with:
      - entity -> "game_intro" entry mappings
      - a single "game_intro" node (scene context, participants, empty choices)
      - visual_asset_map binding entities to visual IDs

    This patch is merged into data/narrative_routes.json without overwriting
    existing nodes.
    """
    world = dataset.get("world", dataset)
    characters: list[dict] = world.get("characters", []) if isinstance(world, dict) else []
    factions: list[dict] = world.get("factions", []) if isinstance(world, dict) else []
    locations: list[dict] = world.get("locations", []) if isinstance(world, dict) else []

    current_scene = session_state.get("scene", "unknown location")

    # intro node is NOT a plot system — it is a "current game state explanation layer"
    intro_node = {
        "context": build_scene_context(current_scene, characters, factions),
        "participants": extract_active_characters(session_state, characters),
        "choices": [],  # critical: do NOT take over AI options
    }

    return {
        "character_entry": map_entities_to_intro(characters),
        "location_entry": map_entities_to_intro(locations),
        "faction_entry": map_entities_to_intro(factions),
        "nodes": {"game_intro": intro_node},
        "visual_asset_map": build_visual_map(characters, locations, factions),
    }


# ── Scene context (natural language, not system language) ────────────

def build_scene_context(scene: str, characters: list[dict], factions: list[dict]) -> str:
    char_names = [c.get("name", "") for c in characters[:5] if c.get("name")]
    fac_names = [f.get("name", "") for f in factions[:3] if f.get("name")]

    parts = [f"当前场景：{scene}"]
    parts.append("场景中正在发生的事件由主叙事引擎推进，")
    if char_names:
        parts.append(f"以下角色处于当前叙事范围内：{', '.join(char_names)}")
    if fac_names:
        parts.append(f"相关势力：{', '.join(fac_names)}")

    return "".join(p for p in parts if p)


# ── Active character extraction ──────────────────────────────────────

def extract_active_characters(session_state: dict, characters: list[dict]) -> list[str]:
    """Extract characters currently active in the session.

    Prioritizes characters explicitly mentioned in session state,
    falls back to first 5 characters from world_pack.
    """
    names: list[str] = []

    # Check session_state.characters for active keys
    state_chars = session_state.get("characters")
    if isinstance(state_chars, dict):
        for entry in state_chars.values():
            if isinstance(entry, dict) and entry.get("name"):
                names.append(str(entry["name"]))
    if names:
        return names[:5]

    # Fallback: first N from world_pack
    return [c.get("name", "") for c in characters[:5] if c.get("name")]


# ── Entry mapping (only points to game_intro, no plot logic) ─────────

def map_entities_to_intro(entities: list[dict]) -> dict[str, str]:
    return {e["name"]: "game_intro" for e in entities if e.get("name")}


# ── Visual map (bind entities to visual IDs) ─────────────────────────

def build_visual_map(
    characters: list[dict],
    locations: list[dict],
    factions: list[dict],
) -> dict[str, dict[str, str]]:
    return {
        "characters": {c["name"]: c.get("id", c.get("name", "")) for c in characters if c.get("name")},
        "locations": {l["name"]: l.get("id", l.get("name", "")) for l in locations if l.get("name")},
        "factions": {f["name"]: f.get("id", f.get("name", "")) for f in factions if f.get("name")},
    }


# ── Merge & persist ──────────────────────────────────────────────────

def merge_game_intro(patch: dict) -> dict:
    """Merge a narrative patch into data/narrative_routes.json.

    - Never overwrites existing nodes or entry maps.
    - Only fills empty slots.
    """
    from engine.narrative.narrative_router import ensure_narrative_routes

    routes = ensure_narrative_routes()

    def _is_empty(val: Any) -> bool:
        if isinstance(val, dict):
            return len(val) == 0
        if isinstance(val, list):
            return len(val) == 0
        return not val

    # Merge entry maps (only fill empty)
    for key in ("character_entry", "location_entry", "faction_entry"):
        current = routes.get(key)
        incoming = patch.get(key)
        if _is_empty(current) and isinstance(incoming, dict):
            routes[key] = incoming
            logger.info("narrative_routes.%s initialized (%d entries)", key, len(incoming))

    # Merge nodes — add game_intro only if it doesn't exist
    current_nodes = routes.get("nodes") or {}
    incoming_nodes = patch.get("nodes") or {}
    for node_id, node_def in incoming_nodes.items():
        if node_id not in current_nodes and isinstance(node_def, dict):
            current_nodes[node_id] = node_def
            logger.info("narrative_routes.nodes.%s initialized", node_id)
    routes["nodes"] = current_nodes

    # Merge visual_asset_map (only fill empty)
    current_vam = routes.get("visual_asset_map") or {}
    incoming_vam = patch.get("visual_asset_map") or {}
    if _is_empty(current_vam) and isinstance(incoming_vam, dict):
        routes["visual_asset_map"] = incoming_vam

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    io_utils.write_json(config.NARRATIVE_ROUTES_PATH, routes)
    logger.info("narrative_routes.json saved -> %s", config.NARRATIVE_ROUTES_PATH)

    return routes


# ── Backward-compat wrapper for world.py NewStory flow ─────────────────

def bootstrap_narrative_routes(world_pack: dict) -> dict:
    """Convenience wrapper for ui/routes/world.py create_new_story.

    Builds session_state from files, then delegates to init_narrative_for_game.
    """
    session_state: dict = {"scene": "unknown location"}
    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
        if isinstance(state, dict):
            session_state = state
    except Exception:
        pass

    patch = init_narrative_for_game(world_pack, session_state)
    return merge_game_intro(patch)
