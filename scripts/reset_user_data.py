#!/usr/bin/env python3
"""Reset runtime data to factory defaults (no API keys, no save progress).

Used by build_release.py before packaging. See .cursor/rules/release-build.mdc
for the full list of paths that must never ship in release zip.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config

DEFAULTS = ROOT / "packaging" / "defaults"

# Reset from factory templates (no API keys, empty progress)
COPY_MAP = {
    "apikey.json": config.APIKEY_PATH,
    "memory.json": config.MEMORY_PATH,
    "story_graph.json": config.STORY_GRAPH_PATH,
    "session_state.yaml": config.SESSION_STATE_PATH,
    "world_pack.yaml": config.WORLD_PACK_PATH,
}

# Remove entirely — usage logs, caches, personal paths
REMOVE_PATHS = (
    config.WORLD_INIT_PATH,
    config.API_USAGE_PATH,
    config.OBSIDIAN_PATH_FILE,
    config.CHAPTER_SUMMARIES_PATH,
    config.WORLD_SUMMARY_PATH,
    config.RUNTIME_MEMORY_PATH,
    config.TURN_PROFILE_PATH,
    config.CANDIDATE_NPCS_PATH,
    config.PLOT_STATE_PATH,
)

# Log files including rotation backups (app.log.1, etc.)
LOG_GLOBS = ("app.log*", "error.log*")


def reset_user_data() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config.SAVES_DIR.mkdir(parents=True, exist_ok=True)

    for name, dest in COPY_MAP.items():
        src = DEFAULTS / name
        if src.exists():
            shutil.copy2(src, dest)
            print(f"  reset {dest.name}")

    for slot in config.SAVES_DIR.glob("*.json"):
        slot.unlink()
        print(f"  removed saves/{slot.name}")

    staging = config.DATA_DIR / ".staging"
    if staging.is_dir():
        shutil.rmtree(staging, ignore_errors=True)
        print("  removed data/.staging/")

    for path in REMOVE_PATHS:
        if path.exists():
            try:
                path.unlink()
                print(f"  removed {path.name}")
            except OSError as exc:
                print(f"  skip {path.name} ({exc})")

    for pattern in LOG_GLOBS:
        for path in config.DATA_DIR.glob(pattern):
            try:
                path.unlink()
                print(f"  removed {path.name}")
            except OSError as exc:
                print(f"  skip {path.name} ({exc})")

    if config.OUTPUT_DIR.is_dir():
        shutil.rmtree(config.OUTPUT_DIR, ignore_errors=True)
        print("  cleared output/")
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    print("Resetting user data...")
    reset_user_data()
    print("Done.")
