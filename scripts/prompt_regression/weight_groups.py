"""Phase 3B weight calibration experiment groups."""
from __future__ import annotations

import json
from typing import Any

WEIGHT_GROUPS: dict[str, dict[str, Any]] = {
    "A": {
        "label": "当前版本（ADR Story 基准）",
        "world": 45,
        "plot": 35,
        "relationship": 20,
    },
    "B": {
        "label": "关系 +10",
        "world": 40,
        "plot": 30,
        "relationship": 30,
    },
    "C": {
        "label": "关系 +15",
        "world": 35,
        "plot": 30,
        "relationship": 35,
    },
    "D": {
        "label": "关系 +20",
        "world": 30,
        "plot": 30,
        "relationship": 40,
    },
}

FAIL_SCENARIOS = ("05_noble_academy", "08_xianxia_dual", "09_adventure_romance")

CODE_DEFAULTS = {
    "story": {"world": 45, "plot": 35, "relationship": 20},
    "adult": {"world": 20, "plot": 25, "relationship": 55},
}


def group_env_json(group_id: str) -> str:
    g = WEIGHT_GROUPS[group_id]
    return json.dumps(
        {"world": g["world"], "plot": g["plot"], "relationship": g["relationship"]},
        ensure_ascii=False,
    )
