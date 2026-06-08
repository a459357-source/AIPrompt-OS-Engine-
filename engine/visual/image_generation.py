"""
image_generation.py — V6 provider bytes → filesystem cache (no registry writes)
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import config
from engine.visual.visual_cache import uri_for_path, write_bytes
from engine.visual.visual_object import VisualObject
from engine.visual.visual_provider import StubVisualProvider, VisualProvider

logger = logging.getLogger(__name__)


def invoke_provider_with_retry(
    obj: VisualObject,
    provider: VisualProvider,
    gen_fn: Callable[..., bytes],
    *,
    prompt_override: str | None = None,
) -> tuple[bytes, VisualProvider]:
    """Retry primary provider; fallback to stub on exhaustion."""
    stub = StubVisualProvider()
    stub_fn = getattr(stub, obj.provider_method)
    max_retries = max(1, int(getattr(config, "VISUAL_MAX_RETRIES", 3) or 3))
    last_err: Exception | None = None
    prompt = str(prompt_override or obj.prompt or "")

    for attempt in range(max_retries):
        try:
            data = gen_fn(
                prompt=prompt,
                asset_id=obj.asset_id,
                size=obj.default_size,
            )
            return data, provider
        except Exception as exc:
            last_err = exc
            if attempt < max_retries - 1:
                delay = 0.1 * (2 ** attempt)
                logger.warning(
                    "Visual provider attempt %s/%s failed: %s; retry in %.1fs",
                    attempt + 1,
                    max_retries,
                    exc,
                    delay,
                )
                time.sleep(delay)

    logger.warning("Visual provider failed after %s attempts, fallback stub: %s", max_retries, last_err)
    data = stub_fn(
        prompt=prompt,
        asset_id=obj.asset_id,
        size=obj.default_size,
    )
    return data, stub


def write_generated_image(
    scope: str,
    obj: VisualObject,
    provider: VisualProvider,
    gen_fn: Callable[..., bytes],
    *,
    prompt_override: str | None = None,
) -> dict[str, Any]:
    """Generate image bytes and write L2 cache. Does not touch registry."""
    data, used_provider = invoke_provider_with_retry(
        obj, provider, gen_fn, prompt_override=prompt_override,
    )
    path = write_bytes(scope, obj.asset_id, data)
    return {
        "image_path": uri_for_path(path),
        "provider": used_provider.provider_name,
        "bytes": len(data),
        "size": obj.default_size,
    }
