"""V6.0 Visual Narrative System — Shared visual asset layer."""

from engine.visual.asset_manager import (
    get_or_request_character_portrait,
    get_or_request_faction_map,
    get_or_request_scene_image,
    get_or_request_world_map,
    reset_visual_assets,
)

__all__ = [
    "get_or_request_character_portrait",
    "get_or_request_scene_image",
    "get_or_request_world_map",
    "get_or_request_faction_map",
    "reset_visual_assets",
]
