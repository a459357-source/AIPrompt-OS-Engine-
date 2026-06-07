"""
context_router.py — V3 Context Router
======================================
Score and select context items by relevance to the current session
instead of concatenating all long-term memory blocks.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import config
from engine.memory import _attitude_label, _faction_action_hints, _trust_label
from engine.memory_names import filter_context_character_names
from engine.world_driver import generate_plot_hooks

logger = logging.getLogger(__name__)

_KIND_HEADER = {
    "npc": "【角色关系记忆】",
    "faction": "【势力状态】",
    "faction_scope": "【势力掌控范围 — AI必须据此生成具体行动】",
    "artifact": "【关键物品】",
    "event": "【世界事件】",
    "attitude": "【势力间态度】",
    "world_flag": "【全局事件】",
    "world_state": "【势力动向】",
    "world_faction": "【主要势力】",
}

_TIER_PRIORITY = {"主角": 0, "核心": 1, "重要": 2, "背景": 3}


@dataclass
class ContextItem:
    id: str
    kind: str
    score: int = 0
    text: str = ""
    priority: int = 5
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class RouterInputs:
    scene: str
    status: str
    main_goal: str
    main_goal_keywords: set[str]
    active_characters: set[str]
    active_factions: set[str]
    world_events: list[dict]
    recent_context: str
    current_turn: int
    regions: list[str]


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "_", (name or "").strip()).strip("_")
    return s or "unknown"


def _clip(text: str, limit: int) -> str:
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _extract_keywords(text: str) -> set[str]:
    text = str(text or "").strip()
    if not text:
        return set()
    parts = re.split(r"[\s,，。；;：:、！!？?\n]+", text)
    keywords: set[str] = set()
    for part in parts:
        part = part.strip()
        if len(part) >= 2:
            keywords.add(part)
        for i in range(len(part) - 1):
            gram = part[i : i + 2]
            if len(gram) >= 2:
                keywords.add(gram)
    return keywords


def _scene_matches(scene: str, target: str) -> bool:
    scene = (scene or "").strip()
    target = (target or "").strip()
    if not scene or not target or len(target) < 2:
        return False
    return target in scene or scene in target


def _character_factions(world_pack: dict) -> dict[str, set[str]]:
    """Map character name → faction names from world_pack."""
    out: dict[str, set[str]] = {}
    world = world_pack.get("world", world_pack) if world_pack else {}
    for ch in world.get("characters", []) or []:
        if not isinstance(ch, dict):
            continue
        name = str(ch.get("name", "")).strip()
        if not name:
            continue
        facs: set[str] = set()
        for mem in ch.get("factionMemberships") or []:
            if isinstance(mem, dict):
                fn = str(mem.get("faction", "")).strip()
                if fn:
                    facs.add(fn)
        primary = str(ch.get("faction", "")).strip()
        if primary:
            facs.add(primary)
        if facs:
            out[name] = facs
    return out


def _build_recent_context(session_state: dict) -> str:
    chunks: list[str] = []
    history = session_state.get("history", []) or []
    for entry in history[-config.HOT_CONTEXT_TURNS :]:
        if not isinstance(entry, dict):
            continue
        chunks.append(str(entry.get("scene", "")))
        chunks.append(str(entry.get("story") or entry.get("summary", ""))[:200])
        chunks.append(str(entry.get("choice", "")))
    try:
        from engine.memory_layers import load_chapter_summaries

        for item in load_chapter_summaries()[-2:]:
            chunks.append(str(item.get("summary", "")))
    except Exception:
        pass
    return "\n".join(c for c in chunks if c)


def build_router_inputs(
    session_state: dict,
    memory: dict,
    world_pack: dict,
    *,
    regions: list[str] | None = None,
) -> RouterInputs:
    world = world_pack.get("world", world_pack) if world_pack else {}
    main_goal = str(world.get("main_goal", "") or "").strip()
    scene = str(session_state.get("scene", "") or "").strip()

    active: set[str] = set()
    for ch in (session_state.get("characters") or {}).values():
        if isinstance(ch, dict):
            n = str(ch.get("name", "")).strip()
            if n:
                active.add(n)

    char_factions = _character_factions(world_pack)
    active_factions: set[str] = set()
    for name in active:
        active_factions.update(char_factions.get(name, set()))

    if regions is None:
        regions = []
        try:
            from engine import io_utils

            if config.WORLD_SUMMARY_PATH.exists():
                data = io_utils.read_json(config.WORLD_SUMMARY_PATH, use_cache=True)
                regions = list(data.get("regions") or [])[:12]
        except Exception:
            pass

    return RouterInputs(
        scene=scene,
        status=str(session_state.get("status", "SETUP") or ""),
        main_goal=main_goal,
        main_goal_keywords=_extract_keywords(main_goal),
        active_characters=active,
        active_factions=active_factions,
        world_events=list(memory.get("world_events") or []),
        recent_context=_build_recent_context(session_state),
        current_turn=int(session_state.get("turn", 0) or 0),
        regions=regions,
    )


def _npc_priority(name: str, data: dict, world_pack: dict) -> int:
    tier = str(data.get("tier", "") or "")
    if tier in _TIER_PRIORITY:
        return _TIER_PRIORITY[tier]
    world = world_pack.get("world", world_pack) if world_pack else {}
    for ch in world.get("characters", []) or []:
        if isinstance(ch, dict) and ch.get("name") == name and ch.get("is_main"):
            return _TIER_PRIORITY["主角"]
    return 5


def _format_npc_item(name: str, data: dict) -> str:
    trust = data.get("trust", 0.5)
    rel = data.get("relationship", "")
    flags = data.get("flags", [])
    metric_history = data.get("metric_history", {})
    trust_label = _trust_label(trust)
    line = f"  {name}: 信任度 {trust:.0%}（{trust_label}）, 关系: {rel or '无'}"
    for metric_key, hist in (metric_history or {}).items():
        if metric_key != "trust" and hist:
            line += f", {metric_key}: {hist[-1][1]:.0%}"
    if flags:
        line += f"\n    已触发事件: {', '.join(flags)}"
    return line


def _format_faction_status_item(fname: str, fdata: dict) -> str:
    rep = fdata.get("reputation", 0.5)
    label = _attitude_label(rep)
    ftype = fdata.get("type", "other")
    goals = fdata.get("goals", [])
    resources = fdata.get("resources", [])
    influence = fdata.get("influence", 50)
    flags = fdata.get("flags", [])
    lines = [f"  {fname}（{ftype}）: 声望 {rep:.0%}（{label}）, 影响力 {influence}"]
    if goals:
        lines.append(f"    目标: {'; '.join(goals[:3])}")
    if resources:
        lines.append(f"    资源: {', '.join(resources[:5])}")
    if flags:
        lines.append(f"    事件: {', '.join(flags)}")
    return "\n".join(lines)


def _format_faction_scope_item(name: str, data: dict) -> str:
    ftype = data.get("type", "other")
    goals = data.get("goals", [])
    territories = data.get("controlledTerritories", [])
    orgs = data.get("subordinateOrganizations", [])
    assets = data.get("keyAssets", [])
    power = data.get("power", {})
    rel_player = data.get("relation_to_player", "neutral")

    lines = [f"\n  [{name}] 类型:{ftype} 对主角:{rel_player}"]
    if goals:
        lines.append(f"    目标: {'; '.join(goals[:3])}")
    if territories:
        lines.append(f"    控制区域: {', '.join(territories)}")
    if orgs:
        lines.append(f"    下属机构: {', '.join(orgs)}")
    if assets:
        lines.append(f"    关键资产: {', '.join(assets)}")
    if power:
        lines.append(
            f"    实力: 军事{power.get('military', 0)} "
            f"经济{power.get('economic', 0)} "
            f"政治{power.get('political', 0)} "
            f"科技{power.get('technology', 0)}"
        )
    hints = _faction_action_hints(ftype, territories, orgs, assets)
    if hints:
        lines.append(f"    可执行行动: {', '.join(hints[:5])}")
    return "\n".join(lines)


def _searchable_text(*parts: Any) -> str:
    return " ".join(str(p) for p in parts if p)


def collect_context_items(
    memory: dict,
    session_state: dict,
    world_pack: dict,
) -> list[ContextItem]:
    """Split memory blocks into atomic routable items."""
    items: list[ContextItem] = []
    allowed = filter_context_character_names(memory, world_pack, session_state)
    chars = memory.get("characters", {})

    for name, data in chars.items():
        if name not in allowed or not isinstance(data, dict):
            continue
        items.append(
            ContextItem(
                id=f"npc_{_slug(name)}",
                kind="npc",
                text=_format_npc_item(name, data),
                priority=_npc_priority(name, data, world_pack),
                meta={
                    "character_name": name,
                    "last_appearance_turn": int(data.get("last_appearance_turn", 0) or 0),
                    "search_text": _searchable_text(name, data.get("relationship"), data.get("flags")),
                },
            )
        )

    factions = memory.get("factions", {})
    for fname, fdata in factions.items():
        if not isinstance(fdata, dict):
            continue
        territories = list(fdata.get("controlledTerritories") or [])
        orgs = list(fdata.get("subordinateOrganizations") or [])
        goals = list(fdata.get("goals") or [])
        items.append(
            ContextItem(
                id=f"faction_{_slug(fname)}",
                kind="faction",
                text=_format_faction_status_item(fname, fdata),
                priority=4,
                meta={
                    "faction_name": fname,
                    "territories": territories,
                    "orgs": orgs,
                    "goals": goals,
                    "search_text": _searchable_text(fname, goals, territories, orgs, fdata.get("resources")),
                },
            )
        )
        items.append(
            ContextItem(
                id=f"faction_scope_{_slug(fname)}",
                kind="faction_scope",
                text=_format_faction_scope_item(fname, fdata),
                priority=4,
                meta={
                    "faction_name": fname,
                    "territories": territories,
                    "orgs": orgs,
                    "goals": goals,
                    "search_text": _searchable_text(fname, goals, territories, orgs, fdata.get("keyAssets")),
                },
            )
        )

    attitudes = memory.get("faction_attitudes", {})
    for a, targets in sorted(attitudes.items()):
        for b, data in sorted((targets or {}).items()):
            if not isinstance(data, dict):
                continue
            att = data.get("attitude", 0.5)
            if abs(att - 0.5) < 0.15:
                continue
            label = _attitude_label(att)
            flags = data.get("flags", [])
            flag_str = f" ({', '.join(flags)})" if flags else ""
            items.append(
                ContextItem(
                    id=f"attitude_{_slug(a)}_{_slug(b)}",
                    kind="attitude",
                    text=f"  {a} → {b}: {label} ({att:.0%}){flag_str}",
                    priority=6,
                    meta={
                        "faction_a": a,
                        "faction_b": b,
                        "search_text": _searchable_text(a, b),
                    },
                )
            )

    arts = memory.get("artifacts", {})
    for name, data in arts.items():
        if not isinstance(data, dict) or data.get("status", "active") != "active":
            continue
        owner_type = data.get("ownerType", "none")
        owner_id = data.get("ownerId", "")
        importance = data.get("importance", 50)
        abilities = data.get("abilities", [])
        tags = data.get("tags", [])
        text = (
            f"  [{name}] 重要性:{importance} 持有者:{owner_type}:{owner_id} "
            f"状态:{data.get('status', 'active')}"
        )
        if abilities:
            text += f"\n    能力: {'; '.join(abilities[:3])}"
        if tags:
            text += f"\n    标签: {', '.join(tags)}"
        items.append(
            ContextItem(
                id=f"artifact_{_slug(name)}",
                kind="artifact",
                text=text,
                priority=5,
                meta={
                    "artifact_name": name,
                    "owner_id": str(owner_id),
                    "related_characters": list(data.get("relatedCharacters") or []),
                    "related_factions": list(data.get("relatedFactions") or []),
                    "search_text": _searchable_text(name, abilities, tags, owner_id),
                },
            )
        )

    for evt in memory.get("world_events") or []:
        if not isinstance(evt, dict):
            continue
        status = evt.get("status", "")
        if status not in ("active", "pending"):
            continue
        title = evt.get("title", "?")
        desc = str(evt.get("description", ""))[:80]
        factions = evt.get("related_factions") or []
        chars_rel = evt.get("related_characters") or []
        prefix = "⚡" if status == "active" else "🔮"
        trigger = evt.get("trigger_turn", "?")
        line = f"  {prefix} {title}"
        if status == "pending":
            line = f"  {prefix} [T{trigger}] {title}"
        extra_lines = [line]
        if desc:
            extra_lines.append(f"    {desc}")
        extra = ""
        if factions:
            extra += f" 涉及势力: {', '.join(factions)}"
        if chars_rel:
            extra += f" 涉及角色: {', '.join(chars_rel)}"
        if extra:
            extra_lines.append(f"    {extra.strip()}")
        items.append(
            ContextItem(
                id=f"event_{evt.get('id', _slug(title))}",
                kind="event",
                text="\n".join(extra_lines),
                priority=3 if status == "active" else 4,
                meta={
                    "related_factions": list(factions),
                    "related_characters": list(chars_rel),
                    "search_text": _searchable_text(title, desc, factions, chars_rel),
                },
            )
        )

    for flag in memory.get("world_flags") or []:
        items.append(
            ContextItem(
                id=f"world_flag_{_slug(str(flag))}",
                kind="world_flag",
                text=f"  • {flag}",
                priority=7,
                meta={"search_text": str(flag)},
            )
        )

    turn = int(session_state.get("turn", 0) or 0)
    hooks = generate_plot_hooks(memory, turn)
    faction_names = list((memory.get("factions") or {}).keys())
    for i, hook in enumerate(hooks[:3]):
        matched_faction = ""
        for fname in faction_names:
            if fname and fname in hook:
                matched_faction = fname
                break
        fdata = (memory.get("factions") or {}).get(matched_faction, {}) if matched_faction else {}
        items.append(
            ContextItem(
                id=f"world_state_{_slug(matched_faction or str(i))}",
                kind="world_state",
                text=f"  • {hook}",
                priority=5,
                meta={
                    "search_text": hook,
                    "faction_name": matched_faction,
                    "territories": list(fdata.get("controlledTerritories") or []),
                    "orgs": list(fdata.get("subordinateOrganizations") or []),
                    "goals": list(fdata.get("goals") or []),
                },
            )
        )

    return items


def _keywords_overlap(keywords: set[str], text: str) -> bool:
    if not keywords or not text:
        return False
    text_keywords = _extract_keywords(text)
    return bool(keywords & text_keywords)


def is_recent_character(name: str, last_turn: int, inputs: RouterInputs) -> bool:
    """True if character appeared recently or is named in recent context."""
    if inputs.current_turn <= 0:
        return False
    if last_turn > 0 and inputs.current_turn - last_turn <= config.CONTEXT_ROUTER_RECENT_TURNS:
        return True
    return name in inputs.recent_context


def _is_recent_character(name: str, last_turn: int, inputs: RouterInputs) -> bool:
    return is_recent_character(name, last_turn, inputs)


def _is_long_absent(name: str, last_turn: int, inputs: RouterInputs) -> bool:
    if last_turn <= 0 or inputs.current_turn <= 0:
        return False
    return inputs.current_turn - last_turn > config.CONTEXT_ROUTER_ABSENT_TURNS


def _faction_scene_score(faction_name: str, meta: dict, inputs: RouterInputs) -> int:
    score = 0
    if faction_name in inputs.active_factions:
        score += 60
    for terr in meta.get("territories") or []:
        if _scene_matches(inputs.scene, str(terr)):
            score += 60
            break
    for org in meta.get("orgs") or []:
        if _scene_matches(inputs.scene, str(org)):
            score += 60
            break
    if len(faction_name) >= 2 and faction_name in inputs.scene:
        score += 60
    for region in inputs.regions:
        if _scene_matches(inputs.scene, region) and (
            _scene_matches(str(region), faction_name)
            or any(_scene_matches(str(region), str(t)) for t in (meta.get("territories") or []))
        ):
            score += 60
            break
    return score


def score_context_items(items: list[ContextItem], inputs: RouterInputs) -> list[ContextItem]:
    """Apply V3 scoring rules to each item (mutates score in place)."""
    for item in items:
        score = 0
        meta = item.meta or {}

        if item.kind == "npc":
            name = meta.get("character_name", "")
            if name in inputs.active_characters:
                score += 100
            last_turn = int(meta.get("last_appearance_turn", 0) or 0)
            if _is_recent_character(name, last_turn, inputs):
                score += 50
            if _is_long_absent(name, last_turn, inputs) and name not in inputs.active_characters:
                score -= 50
            search = meta.get("search_text", "")
            if _keywords_overlap(inputs.main_goal_keywords, search):
                score += 80

        elif item.kind in ("faction", "faction_scope", "world_faction"):
            fname = meta.get("faction_name", "")
            score += _faction_scene_score(fname, meta, inputs)
            search = meta.get("search_text", "")
            if _keywords_overlap(inputs.main_goal_keywords, search):
                score += 80

        elif item.kind == "attitude":
            for key in ("faction_a", "faction_b"):
                fn = meta.get(key, "")
                if fn in inputs.active_factions:
                    score += 60
                if len(fn) >= 2 and fn in inputs.scene:
                    score += 60

        elif item.kind == "artifact":
            owner = str(meta.get("owner_id", ""))
            if owner in inputs.active_characters:
                score += 100
            for cn in meta.get("related_characters") or []:
                if cn in inputs.active_characters:
                    score += 100
            for fn in meta.get("related_factions") or []:
                if fn in inputs.active_factions:
                    score += 60
            if _keywords_overlap(inputs.main_goal_keywords, meta.get("search_text", "")):
                score += 80

        elif item.kind == "event":
            rel_chars = set(meta.get("related_characters") or [])
            rel_facs = set(meta.get("related_factions") or [])
            if rel_chars & inputs.active_characters or rel_facs & inputs.active_factions:
                score += 80
            for fn in rel_facs:
                score += _faction_scene_score(fn, {"territories": [], "orgs": []}, inputs)
            if _keywords_overlap(inputs.main_goal_keywords, meta.get("search_text", "")):
                score += 80

        elif item.kind == "world_state":
            fname = meta.get("faction_name", "")
            if fname:
                score += _faction_scene_score(fname, meta, inputs)
            hook = meta.get("search_text", "")
            for name in inputs.active_characters | inputs.active_factions:
                if name and name in hook:
                    score += 50
            if _keywords_overlap(inputs.main_goal_keywords, hook):
                score += 80

        elif item.kind == "world_flag":
            if _keywords_overlap(inputs.main_goal_keywords, meta.get("search_text", "")):
                score += 80

        item.score = score
    return items


def select_context_items(
    items: list[ContextItem],
    max_items: int,
    *,
    min_items: int | None = None,
) -> list[ContextItem]:
    """Top-N by score; drop unrelated (score <= 0) when relevant items exist."""
    ranked = sorted(items, key=lambda x: (-x.score, x.priority, x.id))
    positive = [x for x in ranked if x.score > 0]
    pool = positive if positive else ranked
    selected = pool[:max_items]
    if min_items and len(selected) < min_items:
        selected = pool[: min(min_items, len(pool))]
    return selected


_BACKFILL_SKIP_KINDS = frozenset({"faction", "faction_scope", "world_faction"})


def _backfill_to_baseline(
    selected: list[ContextItem],
    items: list[ContextItem],
    max_items: int,
    baseline_chars: int,
) -> list[ContextItem]:
    """Pad selection toward 90% of legacy length without restoring irrelevant factions."""
    if baseline_chars <= 0:
        return selected
    target = int(baseline_chars * 0.9)
    pool = list(selected)
    seen = {x.id for x in pool}
    ranked = sorted(items, key=lambda x: (-x.score, x.priority, x.id))

    while len(_render_items(pool)) < target and len(pool) < max_items:
        added = False
        for item in ranked:
            if item.id in seen:
                continue
            if item.score <= 0:
                continue
            pool.append(item)
            seen.add(item.id)
            added = True
            break
        if not added:
            break
    return pool[:max_items]


def _render_items(items: list[ContextItem]) -> str:
    if not items:
        return ""
    by_kind: dict[str, list[str]] = {}
    for item in items:
        by_kind.setdefault(item.kind, []).append(item.text)

    parts: list[str] = []
    order = (
        "npc", "faction", "attitude", "artifact", "event",
        "world_flag", "world_state", "faction_scope", "world_faction",
    )
    for kind in order:
        texts = by_kind.get(kind)
        if not texts:
            continue
        header = _KIND_HEADER.get(kind, "")
        if header:
            parts.append(header)
        parts.extend(texts)
        if kind == "faction_scope":
            parts.append(
                "  【AI规则】生成势力行动时必须：1) 行动范围不超过控制区域 "
                "2) 执行者来自下属机构 3) 手段基于关键资产 4) 规模匹配实力评分"
            )
        if kind == "artifact":
            parts.append("  【AI规则】物品可转移、可争夺、可遗失——围绕物品状态变化生成剧情冲突。")

    return "\n".join(parts)


def route_context_for_prompt(
    memory: dict,
    session_state: dict,
    world_pack: dict,
    *,
    max_items: int | None = None,
    baseline_chars: int | None = None,
) -> str:
    """Collect, score, select, and render long-term memory context."""
    cap = max_items if max_items is not None else config.MAX_CONTEXT_ITEMS
    inputs = build_router_inputs(session_state, memory, world_pack)
    items = collect_context_items(memory, session_state, world_pack)
    score_context_items(items, inputs)
    selected = select_context_items(items, cap)
    if baseline_chars:
        selected = _backfill_to_baseline(selected, items, cap, baseline_chars)

    top_ids = [it.id for it in selected[:5]]
    logger.info(
        "Context router selected %d/%d items (top=%s)",
        len(selected),
        len(items),
        top_ids,
    )
    return _render_items(selected)


def collect_world_faction_items(
    factions: list[dict],
    world_pack: dict,
) -> list[ContextItem]:
    items: list[ContextItem] = []
    for fac in factions:
        if not isinstance(fac, dict):
            continue
        name = str(fac.get("name", "?")).strip() or "?"
        desc = _clip(fac.get("description") or fac.get("goal") or "", 80)
        items.append(
            ContextItem(
                id=f"world_faction_{_slug(name)}",
                kind="world_faction",
                text=f"  - {name}: {desc}",
                priority=4,
                meta={
                    "faction_name": name,
                    "territories": list(fac.get("controlledTerritories") or []),
                    "orgs": list(fac.get("subordinateOrganizations") or []),
                    "goals": list(fac.get("goals") or []),
                    "search_text": _searchable_text(name, desc, fac.get("goals")),
                    "faction_data": fac,
                },
            )
        )
    return items


def route_world_summary_factions(
    factions: list[dict],
    session_state: dict,
    memory: dict,
    world_pack: dict,
    *,
    regions: list[str] | None = None,
) -> list[dict]:
    """Return top-scored faction dicts for the WORLD summary section."""
    if not factions:
        return []
    inputs = build_router_inputs(session_state, memory, world_pack, regions=regions)
    items = collect_world_faction_items(factions, world_pack)
    score_context_items(items, inputs)
    selected = select_context_items(items, config.MAX_WORLD_FACTION_ITEMS)
    out: list[dict] = []
    for item in selected:
        fac = item.meta.get("faction_data")
        if isinstance(fac, dict):
            out.append(fac)
    return out
