"""
visual_provider.py — V6 VisualProvider abstract interface
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from engine.visual.visual_cache import STUB_PNG_BYTES


class VisualProvider(ABC):
    """Shared visual generation interface. Provider must not access registry."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @abstractmethod
    def generate_character(
        self, *, prompt: str, asset_id: str, size: str = "1024x1024",
    ) -> bytes:
        ...

    @abstractmethod
    def generate_location(
        self, *, prompt: str, asset_id: str, size: str = "1536x1024",
    ) -> bytes:
        ...

    @abstractmethod
    def generate_faction(
        self, *, prompt: str, asset_id: str, size: str = "1536x1024",
    ) -> bytes:
        ...

    @abstractmethod
    def generate_event(
        self, *, prompt: str, asset_id: str, size: str = "1536x1024",
    ) -> bytes:
        ...


class StubVisualProvider(VisualProvider):
    """Default backend — deterministic placeholder bytes, no network."""

    @property
    def provider_name(self) -> str:
        return "stub"

    def generate_character(
        self, *, prompt: str, asset_id: str, size: str = "1024x1024",
    ) -> bytes:
        return STUB_PNG_BYTES

    def generate_location(
        self, *, prompt: str, asset_id: str, size: str = "1536x1024",
    ) -> bytes:
        return STUB_PNG_BYTES

    def generate_faction(
        self, *, prompt: str, asset_id: str, size: str = "1536x1024",
    ) -> bytes:
        return STUB_PNG_BYTES

    def generate_event(
        self, *, prompt: str, asset_id: str, size: str = "1536x1024",
    ) -> bytes:
        return STUB_PNG_BYTES


class MockVisualProvider(VisualProvider):
    """Test double — embeds asset_id in PNG stub for assertions."""

    @property
    def provider_name(self) -> str:
        return "mock"

    def _payload(self, asset_id: str) -> bytes:
        return STUB_PNG_BYTES + asset_id.encode("utf-8")[:32]

    def generate_character(
        self, *, prompt: str, asset_id: str, size: str = "1024x1024",
    ) -> bytes:
        return self._payload(asset_id)

    def generate_location(
        self, *, prompt: str, asset_id: str, size: str = "1536x1024",
    ) -> bytes:
        return self._payload(asset_id)

    def generate_faction(
        self, *, prompt: str, asset_id: str, size: str = "1536x1024",
    ) -> bytes:
        return self._payload(asset_id)

    def generate_event(
        self, *, prompt: str, asset_id: str, size: str = "1536x1024",
    ) -> bytes:
        return self._payload(asset_id)
