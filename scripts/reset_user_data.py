#!/usr/bin/env python3
"""Reset runtime data to factory defaults (no API keys, no save progress)."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config

DEFAULTS = ROOT / "packaging" / "defaults"

COPY_MAP = {
    "apikey.json": config.APIKEY_PATH,
    "memory.json": config.MEMORY_PATH,
    "story_graph.json": config.STORY_GRAPH_PATH,
    "session_state.yaml": config.SESSION_STATE_PATH,
    "world_pack.yaml": config.WORLD_PACK_PATH,
}


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
        print(f"  removed {slot.name}")

    for path in (config.WORLD_INIT_PATH, config.API_USAGE_PATH,
                 config.LOG_PATH, config.ERROR_LOG_PATH,
                 config.DATA_DIR / "obsidian_path.json"):
        if path.exists():
            path.unlink()
            print(f"  removed {path.name}")

    for path in (config.CHAPTER_PATH, config.TURN_LOG_PATH, config.DASHBOARD_HTML_PATH):
        if path.exists():
            path.unlink()
            print(f"  removed output/{path.name}")

    out_reports = config.OUTPUT_DIR / "browser_report"
    if out_reports.is_dir():
        shutil.rmtree(out_reports, ignore_errors=True)
        print("  removed output/browser_report/")


if __name__ == "__main__":
    print("Resetting user data...")
    reset_user_data()
    print("Done.")
