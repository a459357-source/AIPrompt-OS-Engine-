"""
agnes_visual_provider.py — V6.0 Agnes VisualProvider (Phase B)
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import requests

import config
from engine.visual.visual_provider import VisualProvider

logger = logging.getLogger(__name__)


class AgnesNotConfiguredError(RuntimeError):
    """Raised when Agnes provider is selected but credentials are missing."""


class AgnesAPIError(RuntimeError):
    """Raised when Agnes API returns an error response."""


class AgnesVisualProvider(VisualProvider):
    """Agnes image API backend implementing VisualProvider."""

    def __init__(self, *, api_key: str | None = None, api_base: str | None = None) -> None:
        self._api_key = (api_key if api_key is not None else config.get_agnes_api_key()).strip()
        self._api_base = (api_base if api_base is not None else config.get_agnes_api_base()).rstrip("/")
        if not self._api_key:
            raise AgnesNotConfiguredError(
                "Agnes API key missing. Set agnes_api_key in data/apikey.json."
            )

    @property
    def provider_name(self) -> str:
        return "agnes"

    def generate_character_portrait(
        self, *, prompt: str, asset_id: str, size: str = "1024x1024",
    ) -> bytes:
        return self._generate_image(prompt, size, kind="character_portrait")

    def generate_scene_image(
        self, *, prompt: str, asset_id: str, size: str = "1024x1024",
    ) -> bytes:
        return self._generate_image(prompt, size, kind="scene_image")

    def generate_world_map(
        self, *, prompt: str, asset_id: str, size: str = "1536x1024",
    ) -> bytes:
        return self._generate_image(prompt, size, kind="world_map")

    def generate_faction_map(
        self, *, prompt: str, asset_id: str, size: str = "1536x1024",
    ) -> bytes:
        return self._generate_image(prompt, size, kind="faction_map")

    def _generate_image(self, prompt: str, size: str, *, kind: str) -> bytes:
        return self._call_agnes_api(prompt=prompt, size=size, kind=kind)

    def _call_agnes_api(self, *, prompt: str, size: str, kind: str) -> bytes:
        url = f"{self._api_base}/images/generations"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "prompt": prompt,
            "size": size,
            "n": 1,
            "response_format": "b64_json",
            "metadata": {"kind": kind},
        }
        try:
            resp = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=config.AGNES_IMAGE_TIMEOUT_SEC,
            )
        except requests.RequestException as exc:
            logger.error("Agnes API request failed: %s", exc)
            raise AgnesAPIError(f"Agnes request failed: {exc}") from exc

        if resp.status_code != 200:
            logger.error("Agnes API HTTP %s: %s", resp.status_code, resp.text[:300])
            raise AgnesAPIError(f"Agnes HTTP {resp.status_code}")

        try:
            data = resp.json()
        except json.JSONDecodeError as exc:
            raise AgnesAPIError("Agnes returned non-JSON response") from exc

        return self._extract_image_bytes(data)

    def _extract_image_bytes(self, data: dict[str, Any]) -> bytes:
        items = data.get("data")
        if isinstance(items, list) and items:
            item = items[0]
            if isinstance(item, dict):
                b64 = item.get("b64_json") or item.get("image_base64")
                if b64:
                    return base64.b64decode(b64)
                url = item.get("url")
                if url:
                    return self._download_url(str(url))

        b64_top = data.get("b64_json") or data.get("image_base64")
        if b64_top:
            return base64.b64decode(b64_top)

        url_top = data.get("url")
        if url_top:
            return self._download_url(str(url_top))

        raise AgnesAPIError("Agnes response missing image data")

    def _download_url(self, url: str) -> bytes:
        try:
            resp = requests.get(url, timeout=config.AGNES_IMAGE_TIMEOUT_SEC)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:
            raise AgnesAPIError(f"Agnes image download failed: {exc}") from exc
