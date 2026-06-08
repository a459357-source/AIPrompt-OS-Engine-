"""
visual_cache.py — V6 visual cache (L1 memory + L2 filesystem)
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import config
from engine.visual.prompt_canonical import normalize_prompt

logger = logging.getLogger(__name__)

_SCOPE_SUBDIR = {
    "characters": "characters",
    "locations": "locations",
    "factions": "factions",
    "events": "events",
    "scenes": "events",  # legacy alias
}

# L1 optional memory cache (idempotency_key → registry record)
_MEMORY_CACHE: dict[str, dict[str, Any]] = {}

# 1x1 PNG (valid minimal image for stub provider)
STUB_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
)


def prompt_hash(prompt: str) -> str:
    """Hash canonical prompt text."""
    return canonical_prompt_hash(normalize_prompt(prompt))


def canonical_prompt_hash(canonical_prompt: str) -> str:
    return hashlib.sha256((canonical_prompt or "").encode("utf-8")).hexdigest()[:16]


def idempotency_key(entity_type: str, entity_id: str, prompt_hash_value: str) -> str:
    return f"{entity_type}:{entity_id}:{prompt_hash_value}"


def memory_get(key: str) -> dict[str, Any] | None:
    item = _MEMORY_CACHE.get(key)
    return item if isinstance(item, dict) else None


def memory_put(key: str, record: dict[str, Any]) -> None:
    if key and isinstance(record, dict):
        _MEMORY_CACHE[key] = record


def clear_memory_cache() -> None:
    _MEMORY_CACHE.clear()


def _scope_dir(scope: str) -> str:
    return _SCOPE_SUBDIR.get(scope, scope)


def cache_path(scope: str, asset_id: str, ext: str = "png") -> Path:
    sub = _scope_dir(scope)
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in asset_id)
    return config.VISUAL_OUTPUT_DIR / sub / f"{safe_id}.{ext}"


def exists(scope: str, asset_id: str) -> bool:
    if not config.VISUAL_CACHE_ENABLED:
        return False
    path = cache_path(scope, asset_id)
    return path.is_file() and path.stat().st_size > 0


def write_bytes(scope: str, asset_id: str, data: bytes, *, ext: str = "png") -> Path:
    path = cache_path(scope, asset_id, ext=ext)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    logger.debug("Visual cache wrote %s (%d bytes)", path, len(data))
    return path


def uri_for_path(path: Path) -> str:
    """Relative URI string stored in registry (not embedded in save slots)."""
    try:
        rel = path.relative_to(config.ROOT)
        return str(rel).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def clear_visual_output() -> None:
    root = config.VISUAL_OUTPUT_DIR
    if root.is_dir():
        import shutil
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    clear_memory_cache()
