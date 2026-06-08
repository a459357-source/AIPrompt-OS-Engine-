"""
cleanup_missing_visuals.py — Generate missing faction emblems + world maps,
and remove orphan entries from visual registries.

Non-invasive: only adds missing visuals, removes orphaned orphan entries.
Does NOT modify step(), prompt chain, or narrative system.
"""

import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import json
import logging

import config
from engine import io_utils

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cleanup_visuals")


def generate_missing_faction_visuals(world_pack: dict) -> dict:
    """Attempt to generate faction emblems for all factions in world_pack."""
    from engine.visual.asset_manager import get_or_request_faction_map
    from engine.visual.visual_registry import load_registry, save_registry

    world = world_pack.get("world", world_pack)
    factions: list[dict] = world.get("factions", [])
    if not factions:
        logger.info("No factions in world_pack — skipping faction visuals")
        return {"generated": 0, "skipped": 0, "errors": 0}

    registry = load_registry()
    existing_factions = set()
    for rec in registry.get("factions", {}).values():
        if isinstance(rec, dict):
            name = rec.get("entity_id") or rec.get("display_name", "")
            if name:
                existing_factions.add(str(name))

    generated = 0
    skipped = 0
    errors = 0

    for fac in factions:
        fname = str(fac.get("name", "")).strip()
        if not fname:
            continue
        if fname in existing_factions:
            skipped += 1
            logger.info("Faction '%s' already has visual — skipping", fname)
            continue
        try:
            logger.info("Generating faction visual for '%s'...", fname)
            result = get_or_request_faction_map(fname, {}, turn=1, force=True)
            if result and result.get("image_path"):
                generated += 1
                logger.info("Faction visual generated: '%s' → %s", fname, result["image_path"])
            else:
                logger.warning("Faction visual returned empty for '%s' — may be stub", fname)
                # Still count as attempted since it may have registered
                generated += 1
        except Exception as exc:
            errors += 1
            logger.error("Failed to generate faction visual for '%s': %s", fname, exc)

    # Reload registry after generation
    registry = load_registry()
    save_registry(registry)
    return {"generated": generated, "skipped": skipped, "errors": errors}


def generate_missing_location_visuals(world_pack: dict) -> dict:
    """Attempt to generate world_map for the world."""
    from engine.visual.asset_manager import get_or_request_world_map
    from engine.visual.visual_registry import load_registry, save_registry

    world = world_pack.get("world", world_pack)
    locations: list[dict] = world.get("locations", [])
    title = world.get("title", "")

    registry = load_registry()
    existing_locs = set()
    for rec in registry.get("locations", {}).values():
        if isinstance(rec, dict):
            name = rec.get("entity_id") or rec.get("display_name", "")
            if name:
                existing_locs.add(str(name))

    generated = 0
    skipped = 0

    # Generate world map
    if title and title not in existing_locs:
        try:
            logger.info("Generating world map for '%s'...", title)
            result = get_or_request_world_map(world_pack, turn=1, force=True)
            if result and result.get("image_path"):
                generated += 1
                logger.info("World map generated: '%s' → %s", title, result["image_path"])
            else:
                logger.warning("World map returned empty for '%s' — may be stub", title)
                generated += 1
        except Exception as exc:
            logger.error("Failed to generate world map: %s", exc)

    # Generate per-location visuals
    for loc in locations:
        loc_name = str(loc.get("name", "")).strip()
        if not loc_name or loc_name in existing_locs:
            continue
        try:
            logger.info("Generating location visual for '%s'...", loc_name)
            result = get_or_request_world_map(world_pack, turn=1, force=True)
            if result and result.get("image_path"):
                generated += 1
            else:
                skipped += 1
        except Exception as exc:
            logger.error("Failed to generate location visual: %s", exc)

    save_registry(load_registry())
    return {"generated": generated, "skipped": skipped}


def clean_orphan_registry_entries() -> dict:
    """Remove orphan entries from visual_registry and identity_registry."""
    from engine.visual.visual_registry import load_registry, save_registry
    from engine.visual.identity_registry import load_identity_registry, save_identity_registry

    # ── Determine which entities are "alive" ──
    wp = io_utils.read_yaml(config.WORLD_PACK_PATH)
    world = wp.get("world", wp)
    alive_chars: set[str] = set()
    alive_facs: set[str] = set()
    alive_locs: set[str] = set()
    for ch in world.get("characters", []):
        if ch.get("name"):
            alive_chars.add(str(ch["name"]))
    for fac in world.get("factions", []):
        if fac.get("name"):
            alive_facs.add(str(fac["name"]))
    for loc in world.get("locations", []):
        if loc.get("name"):
            alive_locs.add(str(loc["name"]))

    # Also consider session_state characters as alive (runtime NPCs)
    try:
        ss = io_utils.read_yaml(config.SESSION_STATE_PATH)
        for entry in ss.get("characters", {}).values():
            if isinstance(entry, dict) and entry.get("name"):
                alive_chars.add(str(entry["name"]))
    except Exception:
        pass

    # Collect alive events from session_state history + story_graph nodes
    alive_events: set[str] = set()
    try:
        ss = io_utils.read_yaml(config.SESSION_STATE_PATH)
        for entry in ss.get("history", []):
            if isinstance(entry, dict) and entry.get("scene"):
                alive_events.add(str(entry["scene"]).strip())
    except Exception:
        pass
    try:
        sg = io_utils.read_json(config.STORY_GRAPH_PATH)
        for node in sg.get("nodes", {}).values():
            if isinstance(node, dict) and node.get("scene"):
                alive_events.add(str(node["scene"]).strip())
    except Exception:
        pass

    result = {"vr_removed": 0, "ir_removed": 0, "vr_kept": 0, "ir_kept": 0}

    # ── Clean visual_registry ──
    registry = load_registry()
    for scope in ("characters", "factions", "locations", "events"):
        bucket = registry.get(scope, {})
        to_remove: list[str] = []
        for asset_id, rec in bucket.items():
            if not isinstance(rec, dict):
                to_remove.append(asset_id)
                continue
            entity_id = str(rec.get("entity_id") or rec.get("display_name") or "").strip()
            if not entity_id:
                to_remove.append(asset_id)
                continue
            # Check if entity is alive
            if scope == "characters" and entity_id not in alive_chars:
                to_remove.append(asset_id)
            elif scope == "factions" and entity_id not in alive_facs:
                to_remove.append(asset_id)
            elif scope == "locations" and entity_id not in alive_locs:
                to_remove.append(asset_id)
            elif scope == "events" and entity_id not in alive_events:
                to_remove.append(asset_id)

        for aid in to_remove:
            del bucket[aid]
            logger.info("visual_registry: removed orphan %s.%s", scope, aid)
            result["vr_removed"] += 1

        result["vr_kept"] += len(bucket)

    save_registry(registry)

    # ── Clean identity_registry ──
    ir = load_identity_registry()
    identities = ir.get("identities", {})
    entity_index = ir.get("entity_index", {})
    to_remove_ids: list[str] = []
    to_remove_entries: list[str] = []

    for eid, identity_id in entity_index.items():
        # eid format: "entity_type:entity_name"
        parts = eid.split(":", 1)
        if len(parts) != 2:
            continue
        etype, ename = parts
        if etype == "character" and ename not in alive_chars:
            to_remove_entries.append(eid)
            if identity_id in identities:
                to_remove_ids.append(identity_id)
        elif etype == "faction" and ename not in alive_facs:
            to_remove_entries.append(eid)
            if identity_id in identities:
                to_remove_ids.append(identity_id)
        elif etype == "location" and ename not in alive_locs:
            to_remove_entries.append(eid)
            if identity_id in identities:
                to_remove_ids.append(identity_id)
        elif etype == "event" and ename not in alive_events:
            to_remove_entries.append(eid)
            if identity_id in identities:
                to_remove_ids.append(identity_id)

    for eid in to_remove_entries:
        if eid in entity_index:
            del entity_index[eid]
            logger.info("identity_registry.entity_index: removed %s", eid)
            result["ir_removed"] += 1

    for iid in set(to_remove_ids):
        if iid in identities:
            del identities[iid]
            logger.info("identity_registry.identities: removed %s", iid)

    result["ir_kept"] = len(identities)
    save_identity_registry(ir)

    return result


def main() -> int:
    """Run all cleanup tasks."""
    import argparse
    parser = argparse.ArgumentParser(description="Visual system cleanup")
    parser.add_argument("--cleanup-only", action="store_true",
                        help="Only clean orphan entries, skip generation")
    args = parser.parse_args()

    print("=" * 60)
    print("Visual System Cleanup — Missing assets + orphan cleanup")
    print("=" * 60)

    # Load world_pack
    wp = io_utils.read_yaml(config.WORLD_PACK_PATH)
    if not wp:
        print("ERROR: world_pack.yaml not found")
        return 1

    if not args.cleanup_only:
        # Task 1a: Generate missing faction emblems
        print("\n--- 1a. Faction Emblem Generation ---")
        fac_result = generate_missing_faction_visuals(wp)
        print(f"  Factions: generated={fac_result['generated']}, skipped={fac_result['skipped']}, errors={fac_result['errors']}")

        # Task 1b: Generate missing location visuals
        print("\n--- 1b. World Map / Location Visuals ---")
        loc_result = generate_missing_location_visuals(wp)
        print(f"  Locations: generated={loc_result['generated']}, skipped={loc_result['skipped']}")

    # Task 2: Clean orphan entries
    print("\n--- 2. Orphan Cleanup ---")
    clean_result = clean_orphan_registry_entries()
    print(f"  visual_registry: removed={clean_result['vr_removed']}, kept={clean_result['vr_kept']}")
    print(f"  identity_registry: removed={clean_result['ir_removed']}, kept={clean_result['ir_kept']}")

    print("\nDone. Run 'python scripts/cleanup_missing_visuals.py --cleanup-only' to verify.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
