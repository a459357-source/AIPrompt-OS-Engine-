"""
visual_context.py — V6.0 visual prompt builder (world facts only)
"""

from __future__ import annotations


def _clip(text: str, limit: int = 400) -> str:
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def build_character_prompt(name: str, world_pack: dict) -> str:
    """Build portrait prompt from world character facts — no mode layer."""
    world = world_pack.get("world", world_pack) if isinstance(world_pack, dict) else {}
    chars = world.get("characters") or []
    profile: dict = {}
    for ch in chars:
        if isinstance(ch, dict) and str(ch.get("name", "")).strip() == name:
            profile = ch
            break

    parts = [
        "anime character portrait",
        "full body standing pose",
        "clean background",
        "high detail character design",
        f"character: {name}",
    ]
    for key in ("gender", "age", "hair_color", "eye_color", "race", "outfit", "role"):
        val = profile.get(key)
        if val:
            parts.append(f"{key}: {val}")
    tags = profile.get("personality_tags") or profile.get("tags") or []
    if isinstance(tags, list) and tags:
        parts.append("tags: " + ", ".join(str(t) for t in tags[:6]))
    note = profile.get("note") or profile.get("description") or ""
    if note:
        parts.append(_clip(str(note), 120))
    return ", ".join(parts)


def build_scene_prompt(scene_key: str, context: dict) -> str:
    scene = _clip(context.get("scene") or scene_key, 80)
    location = _clip(context.get("location") or "", 60)
    summary = _clip(context.get("story_summary") or "", 160)
    parts = [
        "cinematic story scene illustration",
        "dramatic lighting",
        "no text",
        f"scene: {scene}",
    ]
    if location:
        parts.append(f"location: {location}")
    if summary:
        parts.append(f"context: {summary}")
    return ", ".join(parts)


def build_world_map_prompt(world_pack: dict) -> str:
    world = world_pack.get("world", world_pack) if isinstance(world_pack, dict) else {}
    title = _clip(str(world.get("title") or world.get("name") or "fantasy world"), 80)
    regions = world.get("regions") or world.get("locations") or []
    region_names: list[str] = []
    if isinstance(regions, list):
        for r in regions[:12]:
            if isinstance(r, dict):
                region_names.append(str(r.get("name") or r.get("id") or ""))
            elif isinstance(r, str):
                region_names.append(r)
    elif isinstance(regions, dict):
        region_names = list(regions.keys())[:12]

    parts = [
        "fantasy world map",
        "top-down illustrated map",
        "labeled regions",
        f"world: {title}",
    ]
    if region_names:
        parts.append("regions: " + ", ".join(n for n in region_names if n))
    main_goal = _clip(str(world.get("main_goal") or ""), 100)
    if main_goal:
        parts.append(f"theme: {main_goal}")
    return ", ".join(parts)


def build_location_prompt(world_pack: dict) -> str:
    """Location / world map prompt."""
    return build_world_map_prompt(world_pack)


def build_event_prompt(event_key: str, context: dict) -> str:
    """Event scene illustration prompt."""
    return build_scene_prompt(event_key, context)


def build_faction_map_prompt(faction_name: str, memory: dict) -> str:
    factions = memory.get("factions") or {}
    data = factions.get(faction_name) if isinstance(factions, dict) else None
    if not isinstance(data, dict):
        data = {}

    parts = [
        "political faction territory map",
        "highlight controlled regions",
        f"faction: {faction_name}",
    ]
    ftype = data.get("type")
    if ftype:
        parts.append(f"type: {ftype}")
    goals = data.get("goals") or []
    if isinstance(goals, list) and goals:
        parts.append("goals: " + ", ".join(str(g) for g in goals[:4]))
    territories = data.get("controlledTerritories") or data.get("territories") or []
    if isinstance(territories, list) and territories:
        parts.append("territories: " + ", ".join(str(t) for t in territories[:8]))
    return ", ".join(parts)
