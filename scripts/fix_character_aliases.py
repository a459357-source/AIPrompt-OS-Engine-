"""
fix_character_aliases.py — Normalize character name aliases in session_state.

Non-invasive: only merges duplicate character entries, preserves history.
Does NOT modify step(), prompt chain, narrative, or visual systems.
"""

import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import logging
from typing import Any

import config
from engine import io_utils

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fix_aliases")


# Canonical name -> known short-name aliases
_ALIAS_MAP: dict[str, list[str]] = {
    "西园寺皋月": ["皋月"],
}

_SHORT_TO_CANONICAL: dict[str, str] = {}
for canonical, aliases in _ALIAS_MAP.items():
    for alias in aliases:
        _SHORT_TO_CANONICAL[alias] = canonical


def normalize_session_state_characters() -> dict:
    """Merge alias entries in session_state.yaml characters."""
    state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    if not isinstance(state, dict):
        return {"status": "no_state", "merged": 0}

    chars = state.get("characters") or {}
    if not isinstance(chars, dict):
        return {"status": "no_chars", "merged": 0}

    # Find alias keys to merge
    alias_keys: dict[str, str] = {}
    for key, entry in chars.items():
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        if name in _SHORT_TO_CANONICAL:
            canonical = _SHORT_TO_CANONICAL[name]
            alias_keys[key] = canonical

    if not alias_keys:
        logger.info("No aliases found in session_state characters")
        return {"status": "no_aliases", "merged": 0}

    merged_count = 0
    for short_key, canonical_name in alias_keys.items():
        # Find the canonical entry's key
        canonical_key = None
        for ck, ce in chars.items():
            if isinstance(ce, dict) and ce.get("name") == canonical_name:
                canonical_key = ck
                break

        if canonical_key is None:
            # Canonical not present - just rename the alias entry
            chars[short_key]["name"] = canonical_name
            logger.info("Renamed alias entry %s(%s) -> %s",
                       short_key, canonical_name, canonical_name)
            merged_count += 1
            continue

        # Both exist - merge alias into canonical
        alias_entry = chars.pop(short_key)
        canonical_entry = chars[canonical_key]

        for field in ("role", "note"):
            if not canonical_entry.get(field) and alias_entry.get(field):
                canonical_entry[field] = str(alias_entry[field])

        alias_level = str(alias_entry.get("level", "L0"))
        canon_level = str(canonical_entry.get("level", "L0"))
        if alias_level != "L0" and canon_level == "L0":
            canonical_entry["level"] = alias_level

        chars[canonical_key] = canonical_entry
        logger.info("Merged alias %s -> %s", short_key, canonical_name)
        merged_count += 1

    state["characters"] = chars
    io_utils.write_yaml(config.SESSION_STATE_PATH, state)
    logger.info("Saved session_state with %d alias merges", merged_count)
    return {"status": "merged", "merged": merged_count, "aliases": list(alias_keys.keys())}


def main() -> int:
    print("Character Alias Normalization")
    print("-" * 40)
    result = normalize_session_state_characters()
    print(f"Status: {result['status']}, merged: {result.get('merged', 0)}")
    if result.get("aliases"):
        print(f"Fixed aliases: {', '.join(result['aliases'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
