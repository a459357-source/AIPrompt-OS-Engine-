"""
agnes_visual_provider.py — Agnes backend (Phase B; Phase A not wired)
"""

from __future__ import annotations

from engine.visual.visual_provider import VisualProvider


class AgnesNotConfiguredError(RuntimeError):
    """Raised when Agnes is selected but Phase A forbids live API."""


class AgnesVisualProvider(VisualProvider):
    """
    Placeholder for V6.0 Phase B Agnes integration.
    Phase A: selecting provider=agnes raises — use stub/mock in tests.
    """

    @property
    def provider_name(self) -> str:
        return "agnes"

    def _not_configured(self) -> bytes:
        raise AgnesNotConfiguredError(
            "Agnes Visual API is not available in V6.0 Phase A. "
            "Use VISUAL_PROVIDER=stub or wait for Phase B."
        )

    def generate_character(self, *, prompt: str, asset_id: str, size: str = "1024x1024") -> bytes:
        return self._not_configured()

    def generate_scene(self, *, prompt: str, asset_id: str, size: str = "1024x1024") -> bytes:
        return self._not_configured()

    def generate_world_map(self, *, prompt: str, asset_id: str, size: str = "1536x1024") -> bytes:
        return self._not_configured()

    def generate_faction_map(self, *, prompt: str, asset_id: str, size: str = "1536x1024") -> bytes:
        return self._not_configured()
