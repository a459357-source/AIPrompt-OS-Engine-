"""
provider_factory.py — V6.0 VisualProvider factory (single entry for business layer)
"""

from __future__ import annotations

import logging

import config
from engine.visual.visual_provider import MockVisualProvider, StubVisualProvider, VisualProvider

logger = logging.getLogger(__name__)


def get_visual_provider(name: str | None = None) -> VisualProvider:
    """
    Resolve visual backend. Business code must use this — never import Agnes directly.
    """
    provider = (name or config.VISUAL_PROVIDER or "stub").strip().lower()
    if provider == "mock":
        return MockVisualProvider()
    if provider == "agnes":
        from engine.visual.agnes_visual_provider import AgnesNotConfiguredError, AgnesVisualProvider
        try:
            return AgnesVisualProvider()
        except AgnesNotConfiguredError:
            logger.warning("Agnes API key not configured, falling back to stub provider")
            return StubVisualProvider()
    if provider in ("comfyui", "sd-webui", "openai-image"):
        raise NotImplementedError(f"Visual provider '{provider}' is not implemented yet.")
    return StubVisualProvider()


def list_visual_providers() -> list[str]:
    return ["stub", "mock", "agnes"]
