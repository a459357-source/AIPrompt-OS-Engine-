"""
template_resolver.py — infer + lock IP templates from world data
"""

from __future__ import annotations

import logging
from typing import Any

import config
from engine.event_director import ensure_event_catalog
from engine.templates.archetype_defaults import (
    EVENT_TONES,
    FACTION_IDEOLOGIES,
    LOCATION_TYPES,
    archetype_bundle,
    infer_character_archetype,
)
from engine.templates.template_models import (
    CharacterTemplate,
    EventTemplate,
    FactionTemplate,
    LocationTemplate,
)
from engine.templates.template_registry import get_entity_template, set_entity_template

logger = logging.getLogger(__name__)


def resolve_content_template(
    entity_type: str,
    entity_id: str,
    context: dict | None = None,
    *,
    persist: bool = True,
) -> dict[str, Any]:
    """Return locked template for entity; infer and store on first access."""
    if not getattr(config, "CONTENT_TEMPLATE_SYSTEM_ENABLED", True):
        return {}

    et = str(entity_type or "").strip().lower()
    eid = str(entity_id or "").strip()
    existing = get_entity_template(et, eid)
    if existing:
        return existing

    ctx = context if isinstance(context, dict) else {}
    if et == "character":
        template = _infer_character_template(eid, ctx)
    elif et == "location":
        template = _infer_location_template(eid, ctx)
    elif et == "faction":
        template = _infer_faction_template(eid, ctx)
    elif et == "event":
        template = _infer_event_template(eid, ctx)
    else:
        return {}

    stored = set_entity_template(et, eid, template.to_dict())
    logger.info("Content template created %s:%s archetype=%s", et, eid, stored.get("archetype") or stored.get("type"))
    return stored


def _infer_character_template(name: str, context: dict) -> CharacterTemplate:
    world_pack = context.get("world_pack") if isinstance(context.get("world_pack"), dict) else {}
    world = world_pack.get("world", world_pack) if isinstance(world_pack, dict) else {}
    profile: dict = {}
    for ch in world.get("characters") or []:
        if isinstance(ch, dict) and str(ch.get("name", "")).strip() == name:
            profile = ch
            break

    archetype = str(profile.get("archetype") or infer_character_archetype(profile))
    bundle = archetype_bundle(archetype)

    role = str(profile.get("role") or profile.get("role_in_world") or "")
    tags = profile.get("personality_tags") or profile.get("tags") or []
    axis = bundle.get("personality_axis") or []
    if isinstance(tags, list) and tags:
        axis = list(dict.fromkeys([*axis, *[str(t) for t in tags[:4]]]))

    keywords = list(bundle.get("visual_keywords") or [])
    hair = profile.get("hair_color")
    outfit = profile.get("outfit")
    if hair:
        keywords.append(f"{hair} hair motif")
    if outfit:
        keywords.append(str(outfit))

    return CharacterTemplate(
        name=name,
        archetype=archetype if archetype != "default" else infer_character_archetype(profile),
        role_in_world=role or "叙事核心角色",
        visual_identity_hint=str(profile.get("visual_identity_hint") or profile.get("note") or "")[:120],
        personality_axis=axis,
        conflict_vector=str(profile.get("conflict_vector") or bundle.get("conflict_vector") or ""),
        signature_trait=str(profile.get("signature_trait") or (tags[0] if isinstance(tags, list) and tags else "")),
        visual_keywords=keywords,
    )


def _infer_location_template(entity_id: str, context: dict) -> LocationTemplate:
    world_pack = context.get("world_pack") if isinstance(context.get("world_pack"), dict) else {}
    world = world_pack.get("world", world_pack) if isinstance(world_pack, dict) else {}
    title = str(world.get("title") or world.get("name") or entity_id)
    loc_type = str(world.get("location_type") or world.get("world_type") or "default")
    bundle = LOCATION_TYPES.get(loc_type, LOCATION_TYPES["default"])
    materials = str(world.get("dominant_materials") or "stone, wood, silk banners")
    return LocationTemplate(
        name=title,
        type=loc_type if loc_type != "default" else "fantasy realm",
        function_in_world=str(bundle.get("function_in_world") or "叙事舞台"),
        atmosphere=str(bundle.get("atmosphere") or "史诗氛围"),
        dominant_materials=materials,
        visual_keywords=list(bundle.get("visual_keywords") or []),
        story_usage=str(world.get("main_goal") or "")[:100],
    )


def _infer_faction_template(name: str, context: dict) -> FactionTemplate:
    memory = context.get("memory") if isinstance(context.get("memory"), dict) else {}
    factions = memory.get("factions") if isinstance(memory, dict) else {}
    data = factions.get(name) if isinstance(factions, dict) else {}
    if not isinstance(data, dict):
        data = {}
    ftype = str(data.get("type") or "default")
    bundle = FACTION_IDEOLOGIES.get(ftype, FACTION_IDEOLOGIES["default"])
    goals = data.get("goals") or []
    hidden = str(data.get("hidden_goal") or bundle.get("hidden_goal") or "")
    if isinstance(goals, list) and goals and not hidden:
        hidden = str(goals[0])
    return FactionTemplate(
        name=name,
        ideology=str(data.get("ideology") or ftype),
        power_structure=str(data.get("power_structure") or "层级指挥"),
        public_image=str(data.get("public_image") or bundle.get("public_image") or ""),
        hidden_goal=hidden,
        key_figures=[str(x) for x in (data.get("key_figures") or []) if str(x).strip()][:6],
        visual_identity=str(data.get("visual_identity") or f"{name} faction emblem"),
        visual_keywords=list(bundle.get("visual_keywords") or []),
    )


def _infer_event_template(event_id: str, context: dict) -> EventTemplate:
    ctx = context if isinstance(context, dict) else {}
    catalog = ensure_event_catalog()
    entry = (catalog.get("events") or {}).get(event_id) if event_id in (catalog.get("events") or {}) else {}
    category = str((entry or {}).get("category") or ctx.get("event_category") or "default")
    bundle = EVENT_TONES.get(category, EVENT_TONES["default"])
    scene = str(ctx.get("scene") or (entry or {}).get("label") or event_id)
    participants = [str(x) for x in (ctx.get("participants") or []) if str(x).strip()]
    return EventTemplate(
        title=scene[:80],
        type=category,
        trigger=str(ctx.get("trigger") or event_id),
        participants=participants,
        conflict=str(ctx.get("conflict") or "立场冲突"),
        outcome_state=str(ctx.get("outcome_state") or "待定"),
        visual_focus=str(ctx.get("visual_focus") or scene[:60]),
        emotion_tone=str(ctx.get("emotion_tone") or bundle.get("emotion_tone") or ""),
        visual_keywords=list(bundle.get("visual_keywords") or []),
    )
