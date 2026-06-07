"""Per-turn timing metrics (V2 profiling)."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path

import config

logger = logging.getLogger(__name__)


class TurnProfiler:
    """Lightweight stage timer for step()."""

    def __init__(self) -> None:
        self._marks: dict[str, float] = {"turn_start": time.perf_counter()}

    def mark(self, name: str) -> None:
        self._marks[name] = time.perf_counter()

    def _elapsed(self, start: str, end: str) -> float:
        if start not in self._marks or end not in self._marks:
            return 0.0
        return round(self._marks[end] - self._marks[start], 4)

    def flush(self, turn: int) -> None:
        record = {
            "timestamp": datetime.now().isoformat(),
            "turn": turn,
            "prompt_build_time": self._elapsed("prompt_start", "prompt_done"),
            "ai_generation_time": self._elapsed("ai_start", "ai_done"),
            "continuation_time": self._elapsed("continuation_start", "continuation_done"),
            "memory_update_time": self._elapsed("memory_start", "memory_done"),
            "save_time": self._elapsed("save_start", "save_done"),
            "total_time": self._elapsed("turn_start", "save_done"),
        }
        try:
            path = Path(config.TURN_PROFILE_PATH)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.debug("profiling write skipped: %s", exc)
