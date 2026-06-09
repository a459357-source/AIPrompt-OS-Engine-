"""
identity_prompt_builder.py — V6.1 identity-weighted prompt construction
"""

from __future__ import annotations

from typing import Any

import config
from engine.visual.visual_identity import VisualIdentity

# Context keys allowed to modify non-appearance aspects (characters only).
_CHARACTER_MODIFIER_KEYS = frozenset({
    "background",
    "lighting",
    "pose",
    "mood",
    "camera",
})


def build_identity_prompt(identity: VisualIdentity, context: dict | None = None) -> str:
    """
    Merge identity anchor with context. Identity weight > context.
    Characters: context may only decorate pose/background/lighting.
    """
    ctx = context if isinstance(context, dict) else {}
    parts: list[str] = []

    for key in sorted(identity.style_anchor.keys()):
        val = identity.style_anchor[key]
        if val:
            parts.append(f"{key}: {val}")

    for key in sorted(identity.canonical_traits.keys()):
        val = identity.canonical_traits[key]
        if val:
            parts.append(f"{key}: {val}")

    parts.extend(identity.locked_descriptors)
    parts.append(f"entity: {identity.entity_id}")
    parts.append(f"seed: {identity.seed}")

    if identity.entity_type == "character":
        for key in sorted(_CHARACTER_MODIFIER_KEYS):
            val = ctx.get(key)
            if val:
                parts.append(f"modifier_{key}: {val}")
    elif identity.entity_type == "event":
        for key in ("scene", "location", "story_summary"):
            val = ctx.get(key)
            if val:
                parts.append(f"context_{key}: {str(val)[:160]}")
    elif identity.entity_type == "faction":
        mem = ctx.get("memory") if isinstance(ctx.get("memory"), dict) else {}
        factions = mem.get("factions") if isinstance(mem, dict) else {}
        data = factions.get(identity.entity_id) if isinstance(factions, dict) else None
        if isinstance(data, dict):
            goals = data.get("goals") or []
            if isinstance(goals, list) and goals:
                parts.append("goals: " + ", ".join(str(g) for g in goals[:4]))
    elif identity.entity_type == "location":
        world_pack = ctx.get("world_pack") if isinstance(ctx.get("world_pack"), dict) else {}
        world = world_pack.get("world", world_pack) if isinstance(world_pack, dict) else {}
        regions = world.get("regions") or world.get("locations") or []
        names: list[str] = []
        if isinstance(regions, list):
            for r in regions[:12]:
                if isinstance(r, dict):
                    names.append(str(r.get("name") or r.get("id") or ""))
                elif isinstance(r, str):
                    names.append(r)
        if names:
            parts.append("regions: " + ", ".join(n for n in names if n))

    core = ", ".join(parts)
    merged = core
    if getattr(config, "CONTENT_TEMPLATE_SYSTEM_ENABLED", True):
        from engine.templates.template_prompt import augment_identity_prompt
        from engine.templates.template_resolver import resolve_content_template

        template = resolve_content_template(identity.entity_type, identity.entity_id, ctx)
        merged = augment_identity_prompt(core, template, identity)

    if getattr(config, "STYLE_BIBLE_V1_ENABLED", True):
        from engine.templates.style_bible import apply_style_bible

        return apply_style_bible(merged, identity.entity_type)
    return merged


def extract_character_traits(entity_id: str, context: dict) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Extract locked appearance traits from world_pack character profile."""
    world_pack = context.get("world_pack") if isinstance(context.get("world_pack"), dict) else {}
    world = world_pack.get("world", world_pack) if isinstance(world_pack, dict) else {}
    chars = world.get("characters") or []
    profile: dict = {}
    for ch in chars:
        if isinstance(ch, dict) and str(ch.get("name", "")).strip() == entity_id:
            profile = ch
            break

    style_anchor = {
        "render_style": "anime character portrait",
        "pose": "head and shoulders, upper body portrait, face clearly visible",
        "framing": "close-up shot, face centered",
        "detail": "high detail character design, facial features prominent",
    }
    canonical: dict[str, Any] = {}
    locked: list[str] = []

    # Use world_pack appearance as the primary visual descriptor
    appearance = str(profile.get("appearance") or "").strip()
    if appearance:
        canonical["appearance"] = appearance[:120]
        locked.append(f"appearance: {appearance[:120]}")

    # Extract distinct visual traits from appearance text
    for trait_key in ("hair_color", "eye_color", "outfit", "build"):
        val = profile.get(trait_key)
        if val:
            canonical[trait_key] = str(val)[:60]
            locked.append(f"{trait_key}: {val}")

    # Use character background to set scene atmosphere
    bg_story = str(profile.get("background") or "").strip()
    if bg_story:
        canonical["background_context"] = bg_story[:100]

    role_tags = profile.get("role_tags") or []
    if isinstance(role_tags, list) and role_tags:
        role_str = ", ".join(str(t) for t in role_tags[:4])
        canonical["role"] = role_str
        locked.append(f"role: {role_str}")

    # Build distinct background from character story
    if bg_story:
        locked.append(f"background: environment reflecting {bg_story[:80]}")
    elif appearance:
        locked.append("background: studio portrait, moody cinematic lighting")
    else:
        locked.append("background: clean soft gradient")

    tags = profile.get("personality_tags") or profile.get("tags") or []
    if isinstance(tags, list) and tags:
        tag_str = ", ".join(str(t) for t in tags[:6])
        canonical["personality_tags"] = tag_str
        locked.append(f"personality_tags: {tag_str}")

    locked.append(f"character: {entity_id}")
    return canonical, style_anchor, locked


def extract_location_traits(entity_id: str, context: dict) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    world_pack = context.get("world_pack") if isinstance(context.get("world_pack"), dict) else {}
    world = world_pack.get("world", world_pack) if isinstance(world_pack, dict) else {}
    title = str(world.get("title") or world.get("name") or entity_id)
    style_anchor = {
        "render_style": "fantasy world map",
        "view": "top-down illustrated map",
        "labels": "labeled regions",
    }
    canonical = {"world_title": title}
    locked = [f"world: {title}"]
    theme = str(world.get("main_goal") or "").strip()
    if theme:
        canonical["theme"] = theme[:100]
        locked.append(f"theme: {theme[:100]}")
    return canonical, style_anchor, locked


def extract_faction_traits(entity_id: str, context: dict) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    memory = context.get("memory") if isinstance(context.get("memory"), dict) else {}
    factions = memory.get("factions") if isinstance(memory, dict) else {}
    data = factions.get(entity_id) if isinstance(factions, dict) else {}
    if not isinstance(data, dict):
        data = {}
    style_anchor = {
        "render_style": "political faction territory map",
        "highlight": "controlled regions",
    }
    canonical: dict[str, Any] = {"faction_name": entity_id}
    locked = [f"faction: {entity_id}"]
    ftype = data.get("type")
    if ftype:
        canonical["type"] = ftype
        locked.append(f"type: {ftype}")
    territories = data.get("controlledTerritories") or data.get("territories") or []
    if isinstance(territories, list) and territories:
        tstr = ", ".join(str(t) for t in territories[:8])
        canonical["territories"] = tstr
        locked.append(f"territories: {tstr}")
    return canonical, style_anchor, locked


def extract_event_traits(entity_id: str, context: dict) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    ctx = context if isinstance(context, dict) else {}
    scene = str(ctx.get("scene") or entity_id).strip()
    style_anchor = {
        "render_style": "cinematic story scene illustration",
        "lighting": "dramatic lighting",
        "constraint": "no text",
    }
    canonical = {"scene_key": entity_id, "scene_label": scene[:80]}
    locked = [f"scene: {scene[:80]}"]
    location = str(ctx.get("location") or "").strip()
    if location:
        canonical["location"] = location[:60]
        locked.append(f"location: {location[:60]}")
    return canonical, style_anchor, locked
