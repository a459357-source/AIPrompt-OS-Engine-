"""
image_generation.py — V6.0 generate orchestration (Provider → Cache → Registry)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from engine.visual.visual_cache import prompt_hash, uri_for_path, write_bytes
from engine.visual.visual_provider import VisualProvider
from engine.visual.visual_registry import make_asset_record

logger = logging.getLogger(__name__)


def generate_and_register(
    scope: str,
    asset_id: str,
    display_name: str,
    prompt: str,
    kind: str,
    provider: VisualProvider,
    gen_fn: Callable[..., bytes],
    *,
    turn: int = 0,
    size: str = "1024x1024",
) -> dict[str, Any]:
    """Generate image bytes, write cache, return registry record metadata."""
    phash = prompt_hash(prompt)
    data = gen_fn(prompt=prompt, asset_id=asset_id, size=size)
    path = write_bytes(scope, asset_id, data)
    image_path = uri_for_path(path)
    record = make_asset_record(
        asset_id=asset_id,
        display_name=display_name,
        image_path=image_path,
        entity_id=display_name,
        provider=provider.provider_name,
        kind=kind,
        created_turn=turn,
        prompt_hash=phash,
        meta={"size": size, "bytes": len(data)},
    )
    logger.info(
        "Visual generated scope=%s asset_id=%s provider=%s",
        scope, asset_id, provider.provider_name,
    )
    return record
