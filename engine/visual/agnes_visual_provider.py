"""
agnes_visual_provider.py — V6 Agnes VisualProvider
===================================================
Agnes Image API (apihub.agnes-ai.com) backend.
Response format: {"data":[{"url":"https://..."}]} — URL download.
"""

from __future__ import annotations

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
        self._model = getattr(config, "AGNES_IMAGE_MODEL", "agnes-image-2.1-flash")
        if not self._api_key:
            raise AgnesNotConfiguredError(
                "Agnes API key missing. Set agnes_api_key in data/apikey.json."
            )

    @property
    def provider_name(self) -> str:
        return "agnes"

    def generate_character(
        self, *, prompt: str, asset_id: str, size: str = "1024x1024",
    ) -> bytes:
        return self._generate_image(prompt, size)

    def generate_location(
        self, *, prompt: str, asset_id: str, size: str = "1536x1024",
    ) -> bytes:
        return self._generate_image(prompt, size)

    def generate_faction(
        self, *, prompt: str, asset_id: str, size: str = "1536x1024",
    ) -> bytes:
        return self._generate_image(prompt, size)

    def generate_event(
        self, *, prompt: str, asset_id: str, size: str = "1024x1024",
    ) -> bytes:
        return self._generate_image(prompt, size)

    def _generate_image(self, prompt: str, size: str) -> bytes:
        return self._call_agnes_api(prompt=prompt, size=size)

    def _call_agnes_api(self, *, prompt: str, size: str) -> bytes:
        url = f"{self._api_base}/images/generations"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "prompt": prompt,
            "size": size,
            "n": 1,
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
            logger.error("Agnes API HTTP %s: %s", resp.status_code, resp.text[:400])
            raise AgnesAPIError(f"Agnes HTTP {resp.status_code}")

        try:
            data = resp.json()
        except json.JSONDecodeError as exc:
            raise AgnesAPIError("Agnes returned non-JSON response") from exc

        return self._extract_image_bytes(data)

    def _extract_image_bytes(self, data: dict[str, Any]) -> bytes:
        # Agnes returns {"data": [{"url": "https://..."}]}
        items = data.get("data")
        if isinstance(items, list) and items:
            item = items[0]
            if isinstance(item, dict):
                image_url = item.get("url") or item.get("b64_json") or item.get("image_base64")
                if not image_url:
                    raise AgnesAPIError("Agnes response item missing url")
                # b64_json fallback
                if isinstance(image_url, str) and image_url.startswith("http"):
                    return self._download_url(image_url)
                if isinstance(image_url, str) and len(image_url) > 100:
                    import base64
                    return base64.b64decode(image_url)

        raise AgnesAPIError("Agnes response missing image data")

    def _download_url(self, url: str) -> bytes:
        try:
            resp = requests.get(url, timeout=config.AGNES_IMAGE_TIMEOUT_SEC)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:
            raise AgnesAPIError(f"Agnes image download failed: {exc}") from exc
