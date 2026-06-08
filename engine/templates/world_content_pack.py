"""
world_content_pack.py — V6 IP content batch generation template pack
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import config
from engine import io_utils
from engine.templates.style_bible import STYLE_BIBLE_V1
from engine.templates.template_registry import get_style_bible, load_content_templates, save_content_templates
from engine.visual.style_drift import DRIFT_MARKERS

_PACK_CACHE: dict | None = None

DEFAULT_BATCH_PLAN = {
    "characters": 10,
    "locations": 5,
    "events": 8,
    "factions": 2,
}

_REQUIRED_CHARACTER_FIELDS = (
    "name", "archetype", "role", "faction", "conflict_vector", "visual_keywords",
)
_REQUIRED_LOCATION_FIELDS = (
    "name", "type", "function_in_world", "atmosphere", "visual_keywords",
)
_REQUIRED_EVENT_FIELDS = (
    "title", "type", "participants", "conflict", "emotion_tone",
)
_REQUIRED_FACTION_FIELDS = (
    "name", "ideology", "visual_identity",
)


def _pack_path() -> Path:
    return Path(getattr(config, "WORLD_CONTENT_PACK_PATH", config.CONTENT_TEMPLATES_DEFAULT_PATH.parent / "world_content_pack.yaml"))


def load_world_content_pack(*, force: bool = False) -> dict:
    global _PACK_CACHE  # noqa: PLW0603
    if _PACK_CACHE is not None and not force:
        return _PACK_CACHE
    path = _pack_path()
    if not path.is_file():
        _PACK_CACHE = {"version": 1, "prompts": {}, "default_batch_plan": DEFAULT_BATCH_PLAN}
        return _PACK_CACHE
    data = io_utils.read_yaml(path)
    _PACK_CACHE = data if isinstance(data, dict) else {}
    return _PACK_CACHE


def default_batch_plan() -> dict[str, int]:
    pack = load_world_content_pack()
    plan = pack.get("default_batch_plan") if isinstance(pack.get("default_batch_plan"), dict) else {}
    merged = dict(DEFAULT_BATCH_PLAN)
    for key in DEFAULT_BATCH_PLAN:
        if key in plan:
            merged[key] = max(1, int(plan[key] or DEFAULT_BATCH_PLAN[key]))
    return merged


def style_constraints_text() -> str:
    pack = load_world_content_pack()
    style = pack.get("style_constraints") if isinstance(pack.get("style_constraints"), dict) else {}
    bible = get_style_bible()
    lines: list[str] = []
    for bucket in ("global", "tone", "composition", "material"):
        for token in STYLE_BIBLE_V1.get(bucket) or []:
            lines.append(f"- {token}")
    for token in style.get("visual") or []:
        t = str(token).strip()
        if t and t not in lines:
            lines.append(f"- {t}")
    if bible.get("world_tone"):
        lines.append(f"- world_tone: {bible['world_tone']}")
    for token in bible.get("visual_language") or []:
        lines.append(f"- {token}")
    forbidden = style.get("forbidden") or list(DRIFT_MARKERS[:8])
    if forbidden:
        lines.append("Forbidden drift markers: " + ", ".join(str(x) for x in forbidden))
    return "\n".join(lines)


def _format_prompt(template: str, **kwargs: Any) -> str:
    """Replace only known placeholders — templates embed JSON `{` braces."""
    out = str(template or "")
    for key, val in kwargs.items():
        out = out.replace("{" + key + "}", str(val))
    return out.strip()


def build_entity_prompt(
    entity_type: str,
    count: int,
    *,
    context: dict | None = None,
) -> str:
    """Build AI-ready prompt for one entity bucket."""
    pack = load_world_content_pack()
    prompts = pack.get("prompts") if isinstance(pack.get("prompts"), dict) else {}
    et = str(entity_type or "").strip().lower()
    template = str(prompts.get(et) or "").strip()
    if not template:
        raise ValueError(f"unknown world content entity_type: {entity_type!r}")

    ctx = context if isinstance(context, dict) else {}
    chars = _name_list(ctx.get("characters") or [])
    locs = _name_list(ctx.get("locations") or [])
    facs = _name_list(ctx.get("factions") or [])

    return _format_prompt(
        template,
        count=max(1, int(count or 1)),
        character_names=", ".join(chars) or "(none yet)",
        location_names=", ".join(locs) or "(none yet)",
        faction_names=", ".join(facs) or "(none yet)",
        style_constraints=style_constraints_text(),
    )


def build_full_dataset_prompt(
    plan: dict[str, int] | None = None,
    *,
    context: dict | None = None,
) -> str:
    """One-shot prompt for full IP dataset generation."""
    pack = load_world_content_pack()
    prompts = pack.get("prompts") if isinstance(pack.get("prompts"), dict) else {}
    template = str(prompts.get("full_dataset") or "").strip()
    if not template:
        raise ValueError("world_content_pack missing full_dataset prompt")

    merged = default_batch_plan()
    if isinstance(plan, dict):
        for key in merged:
            if key in plan:
                merged[key] = max(1, int(plan[key] or merged[key]))

    return _format_prompt(
        template,
        count_characters=merged["characters"],
        count_locations=merged["locations"],
        count_events=merged["events"],
        count_factions=merged["factions"],
        style_constraints=style_constraints_text(),
    )


def _name_list(items: Any) -> list[str]:
    names: list[str] = []
    if not isinstance(items, list):
        return names
    for item in items:
        if isinstance(item, dict):
            n = str(item.get("name") or item.get("title") or "").strip()
            if n:
                names.append(n)
        elif isinstance(item, str) and item.strip():
            names.append(item.strip())
    return names


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str) and value.strip():
        return [x.strip() for x in re.split(r"[,;|/]+", value) if x.strip()]
    return []


def normalize_character(item: dict) -> dict[str, Any]:
    raw = item if isinstance(item, dict) else {}
    return {
        "entity_type": "character",
        "name": str(raw.get("name") or "").strip(),
        "archetype": str(raw.get("archetype") or "").strip(),
        "role": str(raw.get("role") or raw.get("role_in_world") or "").strip(),
        "faction": str(raw.get("faction") or "").strip(),
        "visual_identity_hint": str(raw.get("visual_identity_hint") or "").strip(),
        "personality_axis": _as_list(raw.get("personality_axis")),
        "conflict_vector": str(raw.get("conflict_vector") or "").strip(),
        "signature_trait": str(raw.get("signature_trait") or "").strip(),
        "visual_keywords": _as_list(raw.get("visual_keywords")),
        "scene_usage": str(raw.get("scene_usage") or "").strip(),
    }


def normalize_location(item: dict) -> dict[str, Any]:
    raw = item if isinstance(item, dict) else {}
    materials = raw.get("dominant_materials")
    if isinstance(materials, list):
        mat_str = ", ".join(str(x) for x in materials if str(x).strip())
    else:
        mat_str = str(materials or "").strip()
    return {
        "entity_type": "location",
        "name": str(raw.get("name") or "").strip(),
        "type": str(raw.get("type") or "").strip(),
        "function_in_world": str(raw.get("function_in_world") or "").strip(),
        "dominant_materials": _as_list(materials) if isinstance(materials, list) else _as_list(mat_str),
        "atmosphere": str(raw.get("atmosphere") or "").strip(),
        "visual_keywords": _as_list(raw.get("visual_keywords")),
        "story_role": str(raw.get("story_role") or raw.get("story_usage") or "").strip(),
    }


def normalize_event(item: dict) -> dict[str, Any]:
    raw = item if isinstance(item, dict) else {}
    return {
        "entity_type": "event",
        "title": str(raw.get("title") or raw.get("name") or "").strip(),
        "type": str(raw.get("type") or "").strip(),
        "trigger": str(raw.get("trigger") or "").strip(),
        "participants": _as_list(raw.get("participants")),
        "location": str(raw.get("location") or raw.get("scene_location") or "").strip(),
        "conflict": str(raw.get("conflict") or "").strip(),
        "outcome_state": str(raw.get("outcome_state") or "").strip(),
        "visual_focus": str(raw.get("visual_focus") or "").strip(),
        "emotion_tone": str(raw.get("emotion_tone") or "").strip(),
        "scene_prompt_hint": str(raw.get("scene_prompt_hint") or "").strip(),
        "visual_keywords": _as_list(raw.get("visual_keywords")),
    }


def normalize_faction(item: dict) -> dict[str, Any]:
    raw = item if isinstance(item, dict) else {}
    return {
        "entity_type": "faction",
        "name": str(raw.get("name") or "").strip(),
        "ideology": str(raw.get("ideology") or "").strip(),
        "structure": str(raw.get("structure") or raw.get("power_structure") or "").strip(),
        "public_face": str(raw.get("public_face") or raw.get("public_image") or "").strip(),
        "hidden_goal": str(raw.get("hidden_goal") or "").strip(),
        "visual_identity": str(raw.get("visual_identity") or "").strip(),
        "key_symbols": _as_list(raw.get("key_symbols") or raw.get("visual_keywords")),
    }


def _collect_keywords(dataset: dict) -> list[str]:
    words: list[str] = []
    for bucket in ("characters", "locations", "events", "factions"):
        for item in dataset.get(bucket) or []:
            if not isinstance(item, dict):
                continue
            words.extend(_as_list(item.get("visual_keywords")))
            words.extend(_as_list(item.get("key_symbols")))
            for field in ("visual_identity_hint", "visual_identity", "scene_prompt_hint", "atmosphere"):
                val = str(item.get(field) or "").lower()
                if val:
                    words.append(val)
    return words


def validate_style_consistency(dataset: dict) -> list[str]:
    """IP consistency — no style drift markers in generated content."""
    errors: list[str] = []
    pack = load_world_content_pack()
    forbidden = {
        str(x).lower()
        for x in (pack.get("style_constraints") or {}).get("forbidden") or DRIFT_MARKERS
    }
    blob = " ".join(_collect_keywords(dataset)).lower()
    for marker in forbidden:
        if marker and marker in blob:
            errors.append(f"style drift marker detected: {marker}")
    return errors


def validate_character_batch(items: list[dict]) -> list[str]:
    errors: list[str] = []
    archetypes: set[str] = set()
    conflicts: set[str] = set()
    for idx, raw in enumerate(items):
        item = normalize_character(raw)
        for field in _REQUIRED_CHARACTER_FIELDS:
            if not item.get(field) and field != "visual_keywords":
                errors.append(f"character[{idx}] missing {field}")
            if field == "visual_keywords" and not item.get("visual_keywords"):
                errors.append(f"character[{idx}] missing visual_keywords")
        arch = item.get("archetype", "").lower()
        if arch:
            if arch in archetypes:
                errors.append(f"character[{idx}] duplicate archetype: {item['archetype']}")
            archetypes.add(arch)
        conflict = item.get("conflict_vector", "").lower()
        if conflict:
            if conflict in conflicts:
                errors.append(f"character[{idx}] duplicate conflict_vector")
            conflicts.add(conflict)
        if not item.get("faction"):
            errors.append(f"character[{idx}] missing faction assignment")
    return errors


def validate_location_batch(items: list[dict]) -> list[str]:
    errors: list[str] = []
    for idx, raw in enumerate(items):
        item = normalize_location(raw)
        for field in _REQUIRED_LOCATION_FIELDS:
            if field == "visual_keywords":
                if not item.get("visual_keywords"):
                    errors.append(f"location[{idx}] missing visual_keywords")
            elif not item.get(field):
                errors.append(f"location[{idx}] missing {field}")
        if not item.get("function_in_world"):
            errors.append(f"location[{idx}] must have function_in_world")
    return errors


def validate_faction_batch(items: list[dict]) -> list[str]:
    errors: list[str] = []
    ideologies: set[str] = set()
    for idx, raw in enumerate(items):
        item = normalize_faction(raw)
        for field in _REQUIRED_FACTION_FIELDS:
            if not item.get(field):
                errors.append(f"faction[{idx}] missing {field}")
        ideology = item.get("ideology", "").lower()
        if ideology:
            if ideology in ideologies:
                errors.append(f"faction[{idx}] duplicate ideology")
            ideologies.add(ideology)
    return errors


def validate_event_batch(
    items: list[dict],
    *,
    characters: list[dict] | None = None,
    locations: list[dict] | None = None,
) -> list[str]:
    errors: list[str] = []
    char_names = {normalize_character(c).get("name", "").lower() for c in (characters or []) if isinstance(c, dict)}
    loc_names = {normalize_location(l).get("name", "").lower() for l in (locations or []) if isinstance(l, dict)}
    conflicts: set[str] = set()

    for idx, raw in enumerate(items):
        item = normalize_event(raw)
        for field in _REQUIRED_EVENT_FIELDS:
            if field == "participants":
                if not item.get("participants"):
                    errors.append(f"event[{idx}] must bind >=1 participant")
            elif not item.get(field):
                errors.append(f"event[{idx}] missing {field}")

        loc = item.get("location", "").lower()
        if not loc:
            errors.append(f"event[{idx}] must bind a location")
        elif loc_names and loc not in loc_names:
            errors.append(f"event[{idx}] location not in dataset: {item.get('location')}")

        if char_names:
            matched = any(p.lower() in char_names for p in item.get("participants") or [])
            if not matched:
                errors.append(f"event[{idx}] participants not in character set")

        ctype = item.get("type", "").lower()
        if ctype:
            if ctype in conflicts:
                errors.append(f"event[{idx}] duplicate event type")
            conflicts.add(ctype)
    return errors


def normalize_world_dataset(raw: dict | None) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    return {
        "characters": [normalize_character(x) for x in (data.get("characters") or []) if isinstance(x, dict)],
        "locations": [normalize_location(x) for x in (data.get("locations") or []) if isinstance(x, dict)],
        "events": [normalize_event(x) for x in (data.get("events") or []) if isinstance(x, dict)],
        "factions": [normalize_faction(x) for x in (data.get("factions") or []) if isinstance(x, dict)],
    }


def validate_world_dataset(raw: dict | None) -> dict[str, Any]:
    """Validate full IP dataset; returns {valid, errors, warnings, dataset}."""
    dataset = normalize_world_dataset(raw)
    errors: list[str] = []
    errors.extend(validate_character_batch(dataset["characters"]))
    errors.extend(validate_location_batch(dataset["locations"]))
    errors.extend(validate_faction_batch(dataset["factions"]))
    errors.extend(
        validate_event_batch(
            dataset["events"],
            characters=dataset["characters"],
            locations=dataset["locations"],
        ),
    )
    errors.extend(validate_style_consistency(dataset))

    warnings: list[str] = []
    plan = default_batch_plan()
    if len(dataset["characters"]) < plan["characters"]:
        warnings.append(f"characters count {len(dataset['characters'])} < plan {plan['characters']}")
    if len(dataset["locations"]) < plan["locations"]:
        warnings.append(f"locations count {len(dataset['locations'])} < plan {plan['locations']}")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "dataset": dataset,
    }


def dataset_to_world_pack_updates(dataset: dict) -> dict[str, Any]:
    """Map validated dataset into world_pack.world fields (identity-ready)."""
    ds = normalize_world_dataset(dataset)
    characters = []
    for ch in ds["characters"]:
        characters.append({
            "name": ch["name"],
            "role": ch["role"],
            "archetype": ch["archetype"],
            "faction": ch["faction"],
            "conflict_vector": ch["conflict_vector"],
            "signature_trait": ch["signature_trait"],
            "visual_identity_hint": ch["visual_identity_hint"],
            "personality_tags": ch["personality_axis"],
            "note": ch["visual_identity_hint"] or ch["signature_trait"],
        })

    locations = []
    for loc in ds["locations"]:
        materials = ", ".join(loc["dominant_materials"]) if loc["dominant_materials"] else ""
        locations.append({
            "name": loc["name"],
            "type": loc["type"],
            "desc": f"{loc['function_in_world']} — {loc['atmosphere']}",
            "function_in_world": loc["function_in_world"],
            "atmosphere": loc["atmosphere"],
            "dominant_materials": materials,
            "story_role": loc["story_role"],
            "visual_keywords": loc["visual_keywords"],
        })

    faction_names = [f["name"] for f in ds["factions"] if f.get("name")]
    return {
        "characters": characters,
        "locations": locations,
        "factions": faction_names,
    }


def dataset_to_content_template_updates(dataset: dict) -> dict[str, dict]:
    """Map dataset entries into content_templates buckets."""
    ds = normalize_world_dataset(dataset)
    out: dict[str, dict] = {"characters": {}, "locations": {}, "factions": {}, "events": {}}

    for ch in ds["characters"]:
        if not ch.get("name"):
            continue
        out["characters"][ch["name"]] = {
            "name": ch["name"],
            "archetype": ch["archetype"],
            "role_in_world": ch["role"],
            "visual_identity_hint": ch["visual_identity_hint"],
            "personality_axis": ch["personality_axis"],
            "conflict_vector": ch["conflict_vector"],
            "signature_trait": ch["signature_trait"],
            "visual_keywords": ch["visual_keywords"],
            "faction": ch["faction"],
            "scene_usage": ch["scene_usage"],
        }

    for loc in ds["locations"]:
        if not loc.get("name"):
            continue
        out["locations"][loc["name"]] = {
            "name": loc["name"],
            "type": loc["type"],
            "function_in_world": loc["function_in_world"],
            "atmosphere": loc["atmosphere"],
            "dominant_materials": ", ".join(loc["dominant_materials"]),
            "visual_keywords": loc["visual_keywords"],
            "story_usage": loc["story_role"],
        }

    for fac in ds["factions"]:
        if not fac.get("name"):
            continue
        out["factions"][fac["name"]] = {
            "name": fac["name"],
            "ideology": fac["ideology"],
            "power_structure": fac["structure"],
            "public_image": fac["public_face"],
            "hidden_goal": fac["hidden_goal"],
            "visual_identity": fac["visual_identity"],
            "visual_keywords": fac["key_symbols"],
        }

    for ev in ds["events"]:
        key = ev.get("title") or ev.get("trigger")
        if not key:
            continue
        out["events"][str(key)] = {
            "title": ev["title"],
            "type": ev["type"],
            "trigger": ev["trigger"],
            "participants": ev["participants"],
            "conflict": ev["conflict"],
            "outcome_state": ev["outcome_state"],
            "visual_focus": ev["visual_focus"],
            "emotion_tone": ev["emotion_tone"],
            "visual_keywords": ev.get("visual_keywords") or [],
            "location": ev.get("location"),
            "scene_prompt_hint": ev.get("scene_prompt_hint"),
        }
    return out


def apply_dataset_import(
    raw: dict | None,
    *,
    persist: bool = True,
    merge_world_pack: bool = True,
    merge_templates: bool = True,
) -> dict[str, Any]:
    """Import validated dataset into world_pack + content_templates."""
    report = validate_world_dataset(raw)
    if not report["valid"]:
        return {**report, "imported": False}

    dataset = report["dataset"]
    result: dict[str, Any] = {"imported": True, "warnings": report["warnings"], "errors": []}

    if merge_world_pack and persist:
        world_path = config.WORLD_PACK_PATH
        world = io_utils.read_yaml(world_path) if world_path.is_file() else {"world": {}}
        if not isinstance(world, dict):
            world = {"world": {}}
        block = world.setdefault("world", {})
        updates = dataset_to_world_pack_updates(dataset)

        existing_chars = {str(c.get("name", "")).strip() for c in (block.get("characters") or []) if isinstance(c, dict)}
        for ch in updates["characters"]:
            if ch["name"] not in existing_chars:
                block.setdefault("characters", []).append(ch)

        existing_locs = {str(l.get("name", "")).strip() for l in (block.get("locations") or []) if isinstance(l, dict)}
        for loc in updates["locations"]:
            if loc["name"] not in existing_locs:
                block.setdefault("locations", []).append(loc)

        existing_facs = set(str(x) for x in (block.get("factions") or []) if str(x).strip())
        for name in updates["factions"]:
            if name not in existing_facs:
                block.setdefault("factions", []).append(name)

        io_utils.write_yaml(world_path, world)
        result["world_pack_path"] = str(world_path)

    if merge_templates and persist:
        reg = copy.deepcopy(load_content_templates())
        tpl_updates = dataset_to_content_template_updates(dataset)
        for bucket, entries in tpl_updates.items():
            reg.setdefault(bucket, {})
            reg[bucket].update(entries)
        save_content_templates(reg)
        result["content_templates_path"] = str(config.CONTENT_TEMPLATES_PATH)

    result["dataset"] = dataset
    return result


def parse_dataset_json(text: str) -> dict:
    data = json.loads(text)
    if isinstance(data, list):
        return {"characters": data}
    return data if isinstance(data, dict) else {}
