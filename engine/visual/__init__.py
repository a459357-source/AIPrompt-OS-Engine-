"""V6 Visual Narrative System — Shared visual asset layer."""

from engine.visual.asset_manager import (
    get_or_request_character_portrait,
    get_or_request_faction_map,
    get_or_request_scene_image,
    get_or_request_world_map,
    reset_visual_assets,
)
from engine.visual.visual_runtime import get_visual

__all__ = [
    "get_visual",
    "get_or_request_character_portrait",
    "get_or_request_scene_image",
    "get_or_request_world_map",
    "get_or_request_faction_map",
    "reset_visual_assets",
]
