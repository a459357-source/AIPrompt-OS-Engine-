"""
narrative_state.py — V6.6 narrative session state (separate from explore mode)
"""

from __future__ import annotations

import copy
import logging
import shutil
import time
from typing import Any

import config
from engine import io_utils

logger = logging.getLogger(__name__)

MODE_EXPLORE = "explore"
MODE_NARRATIVE = "narrative"


def empty_narrative_state() -> dict:
    return {
        "version": 1,
        "mode": MODE_EXPLORE,
        "current_event_id": "",
        "entry_type": "",
        "choice_history": [],
        "continuity": {},
    }


def normalize_narrative_state(raw: dict | None) -> dict:
    base = empty_narrative_state()
    if not isinstance(raw, dict):
        return base
    base["version"] = int(raw.get("version", 1) or 1)
    mode = str(raw.get("mode") or MODE_EXPLORE).strip().lower()
    base["mode"] = mode if mode in (MODE_EXPLORE, MODE_NARRATIVE) else MODE_EXPLORE
    base["current_event_id"] = str(raw.get("current_event_id") or "").strip()
    base["entry_type"] = str(raw.get("entry_type") or "").strip()
    history = raw.get("choice_history")
    if isinstance(history, list):
        base["choice_history"] = [h for h in history if isinstance(h, dict)]
    continuity = raw.get("continuity")
    if isinstance(continuity, dict):
        base["continuity"] = continuity
    return base


def ensure_narrative_state() -> dict:
    if not config.NARRATIVE_STATE_PATH.exists() and config.NARRATIVE_STATE_DEFAULT_PATH.exists():
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config.NARRATIVE_STATE_DEFAULT_PATH, config.NARRATIVE_STATE_PATH)
    try:
        data = io_utils.read_json(config.NARRATIVE_STATE_PATH)
        if isinstance(data, dict):
            return normalize_narrative_state(data)
    except Exception:
        pass
    if config.NARRATIVE_STATE_DEFAULT_PATH.exists():
        return normalize_narrative_state(io_utils.read_json(config.NARRATIVE_STATE_DEFAULT_PATH))
    return empty_narrative_state()


def load_narrative_state() -> dict:
    return ensure_narrative_state()


def save_narrative_state(state: dict, *, persist: bool = True) -> None:
    if not persist:
        return
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    io_utils.write_json(config.NARRATIVE_STATE_PATH, normalize_narrative_state(state))


def set_narrative_mode(mode: str) -> dict:
    state = load_narrative_state()
    state = copy.deepcopy(state)
    m = str(mode or MODE_EXPLORE).strip().lower()
    state["mode"] = m if m in (MODE_EXPLORE, MODE_NARRATIVE) else MODE_EXPLORE
    save_narrative_state(state)
    return state


def enter_narrative_node(
    event_id: str,
    *,
    entry_type: str = "event",
    continuity: dict | None = None,
) -> dict:
    state = load_narrative_state()
    state = copy.deepcopy(state)
    state["mode"] = MODE_NARRATIVE
    state["current_event_id"] = str(event_id or "").strip()
    state["entry_type"] = str(entry_type or "event").strip()
    if isinstance(continuity, dict):
        state["continuity"] = continuity
    save_narrative_state(state)
    return state


def record_choice(
    *,
    event_id: str,
    choice_id: str,
    next_event_id: str,
) -> dict:
    state = load_narrative_state()
    state = copy.deepcopy(state)
    state["choice_history"].append({
        "event_id": event_id,
        "choice_id": choice_id,
        "next_event_id": next_event_id,
        "at": int(time.time()),
    })
    state["current_event_id"] = next_event_id
    state["mode"] = MODE_NARRATIVE
    save_narrative_state(state)
    return state
