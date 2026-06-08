"""
template_registry.py — persistent content template store (user runtime)
"""

from __future__ import annotations

import copy
import logging
import shutil
import time
from typing import Any

import config
from engine import io_utils
from engine.templates.template_models import ENTITY_TEMPLATE_KEYS

logger = logging.getLogger(__name__)


def empty_content_templates() -> dict:
    return {
        "version": 1,
        "style_bible": {
            "world_tone": "",
            "visual_language": [],
            "emotion_palette": [],
        },
        "characters": {},
        "locations": {},
        "factions": {},
        "events": {},
    }


def normalize_content_templates(raw: dict | None) -> dict:
    base = empty_content_templates()
    if not isinstance(raw, dict):
        return base
    base["version"] = int(raw.get("version", 1) or 1)
    bible = raw.get("style_bible")
    if isinstance(bible, dict):
        base["style_bible"] = {
            "world_tone": str(bible.get("world_tone") or ""),
            "visual_language": [
                str(x) for x in (bible.get("visual_language") or []) if str(x).strip()
            ],
            "emotion_palette": [
                str(x) for x in (bible.get("emotion_palette") or []) if str(x).strip()
            ],
        }
    for bucket in ENTITY_TEMPLATE_KEYS.values():
        block = raw.get(bucket)
        if isinstance(block, dict):
            base[bucket] = {
                str(k): v for k, v in block.items()
                if isinstance(v, dict) and str(k).strip()
            }
    return base


def ensure_content_templates() -> dict:
    if not config.CONTENT_TEMPLATES_PATH.exists() and config.CONTENT_TEMPLATES_DEFAULT_PATH.exists():
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config.CONTENT_TEMPLATES_DEFAULT_PATH, config.CONTENT_TEMPLATES_PATH)
    try:
        data = io_utils.read_json(config.CONTENT_TEMPLATES_PATH)
        if isinstance(data, dict):
            return normalize_content_templates(data)
    except Exception:
        pass
    if config.CONTENT_TEMPLATES_DEFAULT_PATH.exists():
        return normalize_content_templates(io_utils.read_json(config.CONTENT_TEMPLATES_DEFAULT_PATH))
    return empty_content_templates()


def load_content_templates() -> dict:
    return ensure_content_templates()


def save_content_templates(data: dict, *, persist: bool = True) -> None:
    if not persist:
        return
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    io_utils.write_json(config.CONTENT_TEMPLATES_PATH, normalize_content_templates(data))


def get_entity_template(entity_type: str, entity_id: str) -> dict | None:
    et = str(entity_type or "").strip().lower()
    bucket = ENTITY_TEMPLATE_KEYS.get(et)
    if not bucket:
        return None
    reg = load_content_templates()
    item = (reg.get(bucket) or {}).get(str(entity_id or "").strip())
    return item if isinstance(item, dict) else None


def set_entity_template(entity_type: str, entity_id: str, template: dict) -> dict:
    et = str(entity_type or "").strip().lower()
    eid = str(entity_id or "").strip()
    bucket = ENTITY_TEMPLATE_KEYS.get(et)
    if not bucket or not eid:
        raise ValueError(f"invalid template target: {entity_type}:{entity_id}")
    reg = copy.deepcopy(load_content_templates())
    entry = copy.deepcopy(template) if isinstance(template, dict) else {}
    entry["name"] = entry.get("name") or eid
    entry["locked_at"] = int(time.time())
    reg.setdefault(bucket, {})[eid] = entry
    save_content_templates(reg)
    return entry


def get_style_bible() -> dict[str, Any]:
    return dict(load_content_templates().get("style_bible") or {})
