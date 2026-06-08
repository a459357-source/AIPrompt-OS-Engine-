"""
template_models.py — structured IP templates for four V6 entity types
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CharacterTemplate:
    name: str = ""
    archetype: str = ""
    role_in_world: str = ""
    visual_identity_hint: str = ""
    personality_axis: list[str] = field(default_factory=list)
    conflict_vector: str = ""
    signature_trait: str = ""
    visual_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LocationTemplate:
    name: str = ""
    type: str = ""
    function_in_world: str = ""
    atmosphere: str = ""
    dominant_materials: str = ""
    visual_keywords: list[str] = field(default_factory=list)
    story_usage: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FactionTemplate:
    name: str = ""
    ideology: str = ""
    power_structure: str = ""
    public_image: str = ""
    hidden_goal: str = ""
    key_figures: list[str] = field(default_factory=list)
    visual_identity: str = ""
    visual_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EventTemplate:
    title: str = ""
    type: str = ""
    trigger: str = ""
    participants: list[str] = field(default_factory=list)
    conflict: str = ""
    outcome_state: str = ""
    visual_focus: str = ""
    emotion_tone: str = ""
    visual_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


ENTITY_TEMPLATE_KEYS = {
    "character": "characters",
    "location": "locations",
    "faction": "factions",
    "event": "events",
}
