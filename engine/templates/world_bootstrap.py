"""
world_bootstrap.py — V6 One-click World Bootstrap (IP seeding runtime)
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Any

import config
from engine import io_utils
from engine.relationship_core import RelationshipEdge, load_graph, save_graph, set_edge
from engine.templates.style_bible import STYLE_BIBLE_V1
from engine.templates.template_registry import load_content_templates, save_content_templates
from engine.templates.world_content_pack import (
    _format_prompt,
    apply_dataset_import,
    build_narrative_nodes_from_bootstrap,
    load_world_content_pack,
    normalize_character,
    normalize_event,
    normalize_faction,
    normalize_location,
    validate_style_consistency,
    validate_world_dataset,
)

logger = logging.getLogger(__name__)

DEFAULT_BOOTSTRAP_INPUT = {
    "world_name": "PROJECT_V6_WORLD",
    "genre": "dark imperial fantasy / grounded cinematic fantasy",
    "tone": "cold, restrained, political tension",
    "scale": "medium (20~30 entities total)",
}

DEFAULT_BOOTSTRAP_PLAN = {
    "characters": 10,
    "locations": 5,
    "factions": 2,
    "events": 8,
}

_RELATION_TYPE_MAP: dict[str, dict[str, float]] = {
    "ally": {"trust": 72, "affection": 58, "respect": 60, "hostility": 8},
    "rival": {"trust": 32, "affection": 28, "respect": 55, "hostility": 62},
    "subordinate": {"trust": 58, "respect": 72, "dependence": 68, "hostility": 5},
    "hidden conflict": {"trust": 38, "affection": 35, "respect": 45, "hostility": 48},
    "mentor": {"trust": 65, "respect": 78, "affection": 45, "dependence": 30},
    "enemy": {"trust": 18, "hostility": 78, "respect": 25, "affection": 10},
    "political": {"trust": 48, "respect": 62, "hostility": 22, "affection": 30},
}


def bootstrap_plan() -> dict[str, int]:
    pack = load_world_content_pack()
    plan = pack.get("bootstrap_plan") if isinstance(pack.get("bootstrap_plan"), dict) else {}
    merged = dict(DEFAULT_BOOTSTRAP_PLAN)
    for key in merged:
        if key in plan:
            merged[key] = max(1, int(plan[key] or merged[key]))
    return merged


def normalize_bootstrap_input(raw: dict | None) -> dict[str, str]:
    src = raw if isinstance(raw, dict) else {}
    base = dict(DEFAULT_BOOTSTRAP_INPUT)
    for key in base:
        if src.get(key):
            base[key] = str(src[key]).strip()
    return base


def build_world_seed(bootstrap_input: dict | None = None) -> dict[str, Any]:
    """STEP 1 — deterministic world seed from minimal config."""
    inp = normalize_bootstrap_input(bootstrap_input)
    tone = inp["tone"]
    return {
        "name": inp["world_name"],
        "genre": inp["genre"],
        "tone": tone,
        "core_theme": "power under constraint",
        "visual_bible_anchor": list(STYLE_BIBLE_V1.get("global") or [])[:3] + [
            "low saturation realism",
            "architectural grounded fantasy",
        ],
        "dominant_material_system": ["stone", "steel", "dark wood"],
        "emotional_signature": tone.split(",")[0].strip() if tone else "cold tension",
    }


def build_bootstrap_prompt(
    bootstrap_input: dict | None = None,
    plan: dict[str, int] | None = None,
) -> str:
    """One-click execution prompt for Cursor / Agent / DeepSeek."""
    pack = load_world_content_pack()
    prompts = pack.get("prompts") if isinstance(pack.get("prompts"), dict) else {}
    template = str(prompts.get("bootstrap") or "").strip()
    if not template:
        raise ValueError("world_content_pack missing bootstrap prompt")

    inp = normalize_bootstrap_input(bootstrap_input)
    merged_plan = bootstrap_plan()
    if isinstance(plan, dict):
        for key in merged_plan:
            if key in plan:
                merged_plan[key] = max(1, int(plan[key] or merged_plan[key]))

    seed = build_world_seed(inp)
    return _format_prompt(
        template,
        world_seed_json=json.dumps(seed, ensure_ascii=False, indent=2),
        world_name=inp["world_name"],
        genre=inp["genre"],
        tone=inp["tone"],
        scale=inp["scale"],
        count_characters=merged_plan["characters"],
        count_locations=merged_plan["locations"],
        count_factions=merged_plan["factions"],
        count_events=merged_plan["events"],
    )


def normalize_relationship(item: dict) -> dict[str, Any]:
    raw = item if isinstance(item, dict) else {}
    strength = raw.get("strength", 0.5)
    try:
        strength_f = max(0.0, min(1.0, float(strength)))
    except (TypeError, ValueError):
        strength_f = 0.5
    return {
        "from": str(raw.get("from") or raw.get("source") or "").strip(),
        "to": str(raw.get("to") or raw.get("target") or "").strip(),
        "type": str(raw.get("type") or raw.get("relation_type") or "neutral").strip().lower(),
        "strength": round(strength_f, 3),
        "status": str(raw.get("status") or "").strip(),
    }


def normalize_bootstrap_dataset(raw: dict | None) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    world = data.get("world") if isinstance(data.get("world"), dict) else build_world_seed()
    return {
        "world": world,
        "characters": [normalize_character(x) for x in (data.get("characters") or []) if isinstance(x, dict)],
        "locations": [normalize_location(x) for x in (data.get("locations") or []) if isinstance(x, dict)],
        "factions": [normalize_faction(x) for x in (data.get("factions") or []) if isinstance(x, dict)],
        "events": [normalize_event(x) for x in (data.get("events") or []) if isinstance(x, dict)],
        "relationships": [
            normalize_relationship(x) for x in (data.get("relationships") or []) if isinstance(x, dict)
        ],
    }


def validate_relationship_batch(
    items: list[dict],
    *,
    characters: list[dict],
) -> list[str]:
    errors: list[str] = []
    names = {normalize_character(c).get("name", "").lower() for c in characters if isinstance(c, dict)}
    names.discard("")

    for idx, raw in enumerate(items):
        rel = normalize_relationship(raw)
        if not rel["from"] or not rel["to"]:
            errors.append(f"relationship[{idx}] missing from/to")
            continue
        if rel["from"].lower() not in names:
            errors.append(f"relationship[{idx}] unknown from: {rel['from']}")
        if rel["to"].lower() not in names:
            errors.append(f"relationship[{idx}] unknown to: {rel['to']}")
        if rel["from"].lower() == rel["to"].lower():
            errors.append(f"relationship[{idx}] self-loop")
    return errors


def validate_faction_binding(characters: list[dict], factions: list[dict]) -> list[str]:
    errors: list[str] = []
    fac_names = {normalize_faction(f).get("name", "").lower() for f in factions if isinstance(f, dict)}
    fac_names.discard("")

    bound: dict[str, int] = {name: 0 for name in fac_names}
    for raw in characters:
        ch = normalize_character(raw)
        fac = str(ch.get("faction") or "").strip().lower()
        if fac and fac in bound:
            bound[fac] += 1

    for fac in fac_names:
        if bound.get(fac, 0) < 1:
            errors.append(f"faction unbound: {fac}")

    for raw in factions:
        fac = normalize_faction(raw)
        if not str(fac.get("hidden_goal") or "").strip():
            errors.append(f"faction missing hidden_goal: {fac.get('name')}")
    return errors


def validate_conflict_density(characters: list[dict], events: list[dict]) -> list[str]:
    errors: list[str] = []
    for idx, raw in enumerate(characters):
        ch = normalize_character(raw)
        if not ch.get("conflict_vector"):
            errors.append(f"character[{idx}] missing conflict_vector")
    for idx, raw in enumerate(events):
        ev = normalize_event(raw)
        if not str(ev.get("conflict") or "").strip():
            errors.append(f"event[{idx}] missing tension source (conflict)")
    return errors


def validate_no_orphan_characters(
    characters: list[dict],
    events: list[dict],
    relationships: list[dict],
) -> list[str]:
    warnings: list[str] = []
    names = {normalize_character(c).get("name", "") for c in characters if isinstance(c, dict)}
    names.discard("")
    linked: set[str] = set()

    for raw in events:
        ev = normalize_event(raw)
        for p in ev.get("participants") or []:
            linked.add(str(p).strip())

    for raw in relationships:
        rel = normalize_relationship(raw)
        linked.add(rel["from"])
        linked.add(rel["to"])

    for name in names:
        if name and name not in linked:
            warnings.append(f"orphan character (no event/relationship): {name}")
    return warnings


def validate_bootstrap_dataset(raw: dict | None) -> dict[str, Any]:
    """STEP 7 — full bootstrap validation pass."""
    dataset = normalize_bootstrap_dataset(raw)
    entity_report = validate_world_dataset(dataset)
    errors = list(entity_report.get("errors") or [])
    warnings = list(entity_report.get("warnings") or [])

    errors.extend(validate_relationship_batch(dataset["relationships"], characters=dataset["characters"]))
    errors.extend(validate_faction_binding(dataset["characters"], dataset["factions"]))
    errors.extend(validate_conflict_density(dataset["characters"], dataset["events"]))
    warnings.extend(
        validate_no_orphan_characters(
            dataset["characters"], dataset["events"], dataset["relationships"],
        ),
    )

    if not dataset.get("world"):
        errors.append("missing world seed")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "dataset": dataset,
    }


def _metrics_from_rel_type(rel_type: str, strength: float) -> dict[str, float]:
    key = rel_type.strip().lower()
    for pattern, metrics in _RELATION_TYPE_MAP.items():
        if pattern in key:
            base = dict(metrics)
            scale = 0.6 + 0.4 * strength
            return {k: round(min(100.0, v * scale), 1) for k, v in base.items()}
    return {
        "trust": round(40 + 30 * strength, 1),
        "affection": round(35 + 25 * strength, 1),
        "respect": round(45 + 20 * strength, 1),
        "hostility": round(20 + 20 * (1 - strength), 1),
    }


def apply_relationship_graph(relationships: list[dict], *, persist: bool = True) -> dict:
    graph = load_graph()
    for raw in relationships:
        rel = normalize_relationship(raw)
        if not rel["from"] or not rel["to"]:
            continue
        metrics = _metrics_from_rel_type(rel["type"], rel["strength"])
        edge = RelationshipEdge(
            source=rel["from"],
            target=rel["to"],
            trust=metrics.get("trust", 50),
            affection=metrics.get("affection", 50),
            respect=metrics.get("respect", 50),
            dependence=metrics.get("dependence", 0),
            hostility=metrics.get("hostility", 0),
            last_update_turn=0,
            flags=[f"bootstrap:{rel['status']}"] if rel.get("status") else [],
        )
        rt = rel["type"].replace(" ", "_").split("/")[0].strip()
        if rt in {"ally", "rival", "enemy", "mentor", "political"}:
            edge.relation_type = rt
        set_edge(graph, edge)

    if persist:
        save_graph(graph)
    return graph


def apply_bootstrap_import(
    raw: dict | None,
    *,
    persist: bool = True,
    merge_entities: bool = True,
) -> dict[str, Any]:
    """Import bootstrap dataset into world_pack, templates, relationships, bootstrap snapshot."""
    report = validate_bootstrap_dataset(raw)
    if not report["valid"]:
        return {**report, "imported": False}

    dataset = report["dataset"]
    entity_result = apply_dataset_import(
        dataset,
        persist=persist and merge_entities,
        merge_world_pack=merge_entities,
        merge_templates=merge_entities,
    )
    if not entity_result.get("imported"):
        return {**report, "imported": False, "entity_errors": entity_result.get("errors")}

    result: dict[str, Any] = {
        "imported": True,
        "warnings": report["warnings"] + list(entity_result.get("warnings") or []),
        "errors": [],
        "dataset": dataset,
    }

    if persist:
        world_path = config.WORLD_PACK_PATH
        world = io_utils.read_yaml(world_path) if world_path.is_file() else {"world": {}}
        if not isinstance(world, dict):
            world = {"world": {}}
        block = world.setdefault("world", {})
        seed = dataset.get("world") or {}
        if seed.get("name"):
            block["title"] = str(seed["name"])
        if seed.get("genre"):
            block["genre"] = str(seed["genre"])
        if seed.get("tone"):
            block["tone"] = str(seed["tone"])
        if seed.get("core_theme"):
            block["main_goal"] = str(seed["core_theme"])
        block["world_bootstrap"] = True
        io_utils.write_yaml(world_path, world)
        result["world_pack_path"] = str(world_path)

        reg = copy.deepcopy(load_content_templates())
        bible = reg.setdefault("style_bible", {})
        if seed.get("emotional_signature"):
            bible["world_tone"] = str(seed["emotional_signature"])
        anchors = seed.get("visual_bible_anchor") or []
        if isinstance(anchors, list) and anchors:
            bible["visual_language"] = [str(x) for x in anchors if str(x).strip()]
        materials = seed.get("dominant_material_system") or []
        if isinstance(materials, list) and materials:
            bible.setdefault("emotion_palette", [])
            bible["material_system"] = [str(x) for x in materials if str(x).strip()]
        save_content_templates(reg)
        result["content_templates_path"] = str(config.CONTENT_TEMPLATES_PATH)

        bootstrap_path = getattr(config, "WORLD_BOOTSTRAP_PATH", config.DATA_DIR / "world_bootstrap.json")
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        io_utils.write_json(bootstrap_path, dataset)
        result["bootstrap_snapshot_path"] = str(bootstrap_path)

        graph = apply_relationship_graph(dataset.get("relationships") or [], persist=True)
        result["relationship_edges"] = len(graph.get("edges") or {})

        write_narrative_routes_patch(dataset)

    return result


def write_narrative_routes_patch(dataset: dict[str, Any]) -> None:
    """P0: 将 bootstrap events 写入 narrative_routes.json."""
    events = dataset.get("events") or []
    if not events:
        return

    generated = build_narrative_nodes_from_bootstrap(events)

    # 合并到现有 narrative_routes.json，保留已有节点
    from engine.narrative.narrative_router import empty_narrative_routes

    existing: dict[str, Any] = empty_narrative_routes()
    if config.NARRATIVE_ROUTES_PATH.exists():
        try:
            existing = io_utils.read_json(config.NARRATIVE_ROUTES_PATH)
            if not isinstance(existing, dict):
                existing = empty_narrative_routes()
        except Exception:
            existing = empty_narrative_routes()

    if isinstance(existing.get("nodes"), dict):
        existing["nodes"].update(generated.get("nodes") or {})
    else:
        existing["nodes"] = generated.get("nodes") or {}

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    io_utils.write_json(config.NARRATIVE_ROUTES_PATH, existing)
    logger.info("narrative_routes.json patched with %d bootstrap nodes", len(generated.get("nodes") or {}))


def generate_bootstrap_dataset(
    bootstrap_input: dict | None = None,
    *,
    plan: dict[str, int] | None = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    """
    Run bootstrap: LLM generate when API key available, else return prompt only.
    """
    prompt = build_bootstrap_prompt(bootstrap_input, plan=plan)
    if not use_llm or not getattr(config, "DEEPSEEK_API_KEY", ""):
        return {"generated": False, "prompt": prompt, "dataset": None}

    from engine.deepseek_client import DeepSeekError, call_deepseek

    system = (
        "You are a V6 world bootstrap engine. Output valid JSON only. "
        "No markdown fences. All entities must interconnect."
    )
    try:
        raw = call_deepseek(
            system,
            prompt,
            temperature=0.85,
            max_tokens=min(8192, int(getattr(config, "MAX_TOKENS", 4096) or 4096)),
            skip_validation=True,
        )
        if not isinstance(raw, dict):
            return {"generated": False, "prompt": prompt, "error": "invalid LLM response"}
        report = validate_bootstrap_dataset(raw)
        return {
            "generated": report["valid"],
            "prompt": prompt,
            "dataset": report["dataset"] if report["valid"] else None,
            "validation": {k: v for k, v in report.items() if k != "dataset"},
        }
    except DeepSeekError as exc:
        return {"generated": False, "prompt": prompt, "error": str(exc)}
