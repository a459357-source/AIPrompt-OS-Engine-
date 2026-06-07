"""
save_manager.py — Save / Load / Autosave System
=================================================
Snapshots and restores the full engine state:
  • session_state.yaml
  • data/memory.json
  • data/story_graph.json
  • output/chapter.md  (last 50 KB only)

Each save is a single JSON file under data/saves/<slot>.json.

Slots:
  • autosave  — written automatically after every successful turn
  • slot1..3  — manual save slots
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import config
from engine import io_utils
from engine.state_store import commit_bundle

logger = logging.getLogger(__name__)

from engine.constants import MAX_CHAPTER_BYTES_IN_SAVE


def _load_candidate_pool() -> dict:
    try:
        return io_utils.read_json(config.CANDIDATE_NPCS_PATH)
    except Exception:
        return {}

# Maximum chapter content to include in a save (avoid giant save files)
_MAX_CHAPTER_BYTES = MAX_CHAPTER_BYTES_IN_SAVE


# ── Public API ─────────────────────────────────────────────────────

def save(slot: str) -> dict | None:
    """
    Save the full engine state to the given slot.

    Args:
        slot: One of "autosave", "slot1", "slot2", "slot3".

    Returns:
        A summary dict with slot name, turn, and timestamp, or None on failure.
    """
    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
        memory = io_utils.read_json(config.MEMORY_PATH)
        graph = io_utils.read_json(config.STORY_GRAPH_PATH)

        chapter = ""
        if config.CHAPTER_PATH.exists():
            raw = config.CHAPTER_PATH.read_bytes()
            if len(raw) > _MAX_CHAPTER_BYTES:
                chapter = raw[-_MAX_CHAPTER_BYTES:].decode("utf-8", errors="replace")
            else:
                chapter = raw.decode("utf-8", errors="replace")

        snapshot = {
            "version": "2.0.0",
            "slot": slot,
            "saved_at": datetime.now().isoformat(),
            "turn": state.get("turn", 0),
            "status": state.get("status", "SETUP"),
            "scene": state.get("scene", ""),
            "session_state": state,
            "memory": memory,
            "story_graph": graph,
            "candidate_npcs": _load_candidate_pool(),
            "chapter": chapter,
            "content_weights": config.CONTENT_WEIGHTS,
            "adult_mode": config.ADULT_MODE,
            "expression_style": config.EXPRESSION_STYLE,
        }

        slot_path = _slot_path(slot)
        slot_path.parent.mkdir(parents=True, exist_ok=True)
        slot_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        logger.info("💾 Saved to slot '%s' (turn %s)", slot, state.get("turn", 0))
        return {
            "slot": slot,
            "turn": state.get("turn", 0),
            "status": state.get("status", "SETUP"),
            "scene": state.get("scene", ""),
            "saved_at": snapshot["saved_at"],
        }

    except Exception as exc:
        logger.error("Failed to save to slot '%s': %s", slot, exc)
        return None


def load(slot: str) -> dict | None:
    """
    Restore the full engine state from the given slot.

    Writes session_state.yaml, memory.json, story_graph.json, and
    chapter.md back to their canonical locations.

    Args:
        slot: One of "autosave", "slot1", "slot2", "slot3".

    Returns:
        A summary dict with slot name, turn, and timestamp, or None on failure.
    """
    slot_path = _slot_path(slot)
    if not slot_path.exists():
        logger.warning("Save slot '%s' does not exist.", slot)
        return None

    try:
        raw = slot_path.read_text(encoding="utf-8")
        snapshot = json.loads(raw)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read save '%s': %s", slot, exc)
        return None

    try:
        commit_bundle(
            snapshot.get("session_state", {}),
            snapshot.get("memory", {}),
            snapshot.get("story_graph", {}),
            chapter=snapshot.get("chapter", ""),
        )
        io_utils.write_json(
            config.CANDIDATE_NPCS_PATH,
            snapshot.get("candidate_npcs", {}),
        )
    except Exception as exc:
        logger.error("Failed to restore save '%s': %s", slot, exc)
        return None

    logger.info("📂 Loaded from slot '%s' (turn %s)", slot, snapshot.get("turn", 0))
    return {
        "slot": slot,
        "turn": snapshot.get("turn", 0),
        "status": snapshot.get("status", "SETUP"),
        "scene": snapshot.get("scene", ""),
        "saved_at": snapshot.get("saved_at", "?"),
    }


def autosave() -> dict | None:
    """Convenience wrapper: save to the autosave slot."""
    return save(config.AUTOSAVE_SLOT)


def snapshot_turn(turn: int) -> dict | None:
    """Rolling turn snapshot every SNAPSHOT_TURN_INTERVAL turns."""
    slot = f"snapshot_T{turn}"
    result = save(slot)
    if result:
        _prune_old_snapshots(keep=3)
    return result


def _prune_old_snapshots(*, keep: int = 3) -> None:
    """Keep only the newest *keep* snapshot_T* files."""
    config.SAVES_DIR.mkdir(parents=True, exist_ok=True)
    snaps = sorted(
        config.SAVES_DIR.glob("snapshot_T*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in snaps[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


def save_runtime_memory(partial: dict) -> None:
    """Persist in-flight generation for disconnect recovery."""
    try:
        io_utils.write_json(config.RUNTIME_MEMORY_PATH, partial)
    except Exception as exc:
        logger.debug("runtime_memory save skipped: %s", exc)


def load_runtime_memory() -> dict | None:
    path = config.RUNTIME_MEMORY_PATH
    if not path.exists():
        return None
    try:
        return io_utils.read_json(path, use_cache=False)
    except Exception:
        return None


def clear_runtime_memory() -> None:
    path = config.RUNTIME_MEMORY_PATH
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass


def list_saves() -> list[dict]:
    """
    List all existing save slots with metadata.

    Returns a list of {slot, turn, status, scene, saved_at} dicts,
    sorted by most recent first.
    """
    saves: list[dict] = []
    config.SAVES_DIR.mkdir(parents=True, exist_ok=True)

    for p in sorted(config.SAVES_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        slot = p.stem  # filename without .json
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            saves.append({
                "slot": slot,
                "turn": data.get("turn", 0),
                "status": data.get("status", "?"),
                "scene": data.get("scene", ""),
                "saved_at": data.get("saved_at", "?"),
            })
        except (json.JSONDecodeError, OSError):
            saves.append({
                "slot": slot,
                "turn": -1,
                "status": "⚠️ 损坏",
                "scene": "",
                "saved_at": "?",
            })
    return saves


def save_exists(slot: str) -> bool:
    """Check whether a save slot has data."""
    return _slot_path(slot).exists()


def delete_save(slot: str) -> bool:
    """Delete a save slot. Returns True if deleted, False if not found."""
    p = _slot_path(slot)
    if p.exists():
        p.unlink()
        logger.info("🗑️  Deleted save slot '%s'", slot)
        return True
    return False


def rollback() -> dict | None:
    """
    Rollback to the previous turn by loading the autosave.
    This effectively undoes the last turn (if autosave was written before it).
    """
    if not save_exists(config.AUTOSAVE_SLOT):
        logger.warning("No autosave to rollback to.")
        return None
    return load(config.AUTOSAVE_SLOT)


# ── Internal helpers ───────────────────────────────────────────────

def _slot_path(slot: str) -> Path:
    """Resolve a slot name to a file path."""
    return config.SAVES_DIR / f"{slot}.json"
