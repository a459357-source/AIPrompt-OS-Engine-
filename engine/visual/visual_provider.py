"""
visual_provider.py — V6.0 VisualProvider abstract interface
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import config
from engine.visual.visual_cache import STUB_PNG_BYTES


class VisualProvider(ABC):
    """Shared visual generation interface. No mode-layer branching."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @abstractmethod
    def generate_character(self, *, prompt: str, asset_id: str, size: str = "1024x1024") -> bytes:
        ...

    @abstractmethod
    def generate_scene(self, *, prompt: str, asset_id: str, size: str = "1024x1024") -> bytes:
        ...

    @abstractmethod
    def generate_world_map(self, *, prompt: str, asset_id: str, size: str = "1536x1024") -> bytes:
        ...

    @abstractmethod
    def generate_faction_map(self, *, prompt: str, asset_id: str, size: str = "1536x1024") -> bytes:
        ...


class StubVisualProvider(VisualProvider):
    """Phase A default — deterministic placeholder bytes, no network."""

    @property
    def provider_name(self) -> str:
        return "stub"

    def generate_character(self, *, prompt: str, asset_id: str, size: str = "1024x1024") -> bytes:
        return STUB_PNG_BYTES

    def generate_scene(self, *, prompt: str, asset_id: str, size: str = "1024x1024") -> bytes:
        return STUB_PNG_BYTES

    def generate_world_map(self, *, prompt: str, asset_id: str, size: str = "1536x1024") -> bytes:
        return STUB_PNG_BYTES

    def generate_faction_map(self, *, prompt: str, asset_id: str, size: str = "1536x1024") -> bytes:
        return STUB_PNG_BYTES


class MockVisualProvider(VisualProvider):
    """Test double — embeds asset_id in PNG stub for assertions."""

    @property
    def provider_name(self) -> str:
        return "mock"

    def _payload(self, asset_id: str) -> bytes:
        return STUB_PNG_BYTES + asset_id.encode("utf-8")[:32]

    def generate_character(self, *, prompt: str, asset_id: str, size: str = "1024x1024") -> bytes:
        return self._payload(asset_id)

    def generate_scene(self, *, prompt: str, asset_id: str, size: str = "1024x1024") -> bytes:
        return self._payload(asset_id)

    def generate_world_map(self, *, prompt: str, asset_id: str, size: str = "1536x1024") -> bytes:
        return self._payload(asset_id)

    def generate_faction_map(self, *, prompt: str, asset_id: str, size: str = "1536x1024") -> bytes:
        return self._payload(asset_id)


def get_visual_provider(name: str | None = None) -> VisualProvider:
    provider = (name or config.VISUAL_PROVIDER or "stub").strip().lower()
    if provider == "mock":
        return MockVisualProvider()
    if provider == "agnes":
        from engine.visual.agnes_visual_provider import AgnesVisualProvider
        return AgnesVisualProvider()
    return StubVisualProvider()
