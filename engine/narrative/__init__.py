"""V6.6 Narrative Entry Layer — routing and display only (no generation)."""

# NARRATIVE SYSTEM IS PASSIVE ONLY — read-only metadata for UI/visuals.
# It must NEVER control story, options, or game flow.

from engine.narrative.narrative_entry import build_narrative_node, get_narrative_hub
from engine.narrative.narrative_router import (
    resolve_character_entry,
    resolve_location_entry,
    resolve_visual_event_entry,
)
from engine.narrative.narrative_router import route_choice
from engine.narrative.narrative_state import load_narrative_state, save_narrative_state, set_narrative_mode

__all__ = [
    "build_narrative_node",
    "get_narrative_hub",
    "resolve_character_entry",
    "resolve_location_entry",
    "resolve_visual_event_entry",
    "route_choice",
    "load_narrative_state",
    "save_narrative_state",
    "set_narrative_mode",
]
