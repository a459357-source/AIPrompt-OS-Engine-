"""
event_director.py — V5.2 Event Director Engine (Phase A)
=========================================================
Shared system that decides what the world should try to happen next.
Does not write story text — outputs DirectorPlan suggestions only.
"""

from __future__ import annotations

import copy
import logging
import shutil
from dataclasses import asdict, dataclass, field
from typing import Any

import config
from engine import io_utils

logger = logging.getLogger(__name__)

_ROMANCE_TYPES = frozenset({"romance", "confession", "gift"})
_CONFLICT_TYPES = frozenset({"argument", "conflict", "betrayal"})


@dataclass
class DirectorPlan:
    event_id: str
    category: str
    priority: int
    reason: str
    participants: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def empty_event_history() -> dict:
    return {"version": 1, "records": []}


def ensure_event_catalog() -> dict:
    """Load event catalog; copy default template into data/ if missing."""
    if not config.EVENT_CATALOG_PATH.exists() and config.EVENT_CATALOG_DEFAULT_PATH.exists():
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config.EVENT_CATALOG_DEFAULT_PATH, config.EVENT_CATALOG_PATH)
    try:
        data = io_utils.read_json(config.EVENT_CATALOG_PATH)
        if isinstance(data, dict) and isinstance(data.get("events"), dict):
            return data
    except Exception:
        pass
    if config.EVENT_CATALOG_DEFAULT_PATH.exists():
        return io_utils.read_json(config.EVENT_CATALOG_DEFAULT_PATH)
    return {"version": 1, "events": {}}


def load_event_history() -> dict:
    try:
        data = io_utils.read_json(config.EVENT_HISTORY_PATH)
        if isinstance(data, dict) and isinstance(data.get("records"), list):
            return data
    except Exception:
        pass
    return empty_event_history()


def save_event_history(history: dict, *, persist: bool = True) -> None:
    if not persist:
        return
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    io_utils.write_json(config.EVENT_HISTORY_PATH, history)


def _catalog_entry(catalog: dict, event_id: str) -> dict:
    events = catalog.get("events") or {}
    entry = events.get(event_id) or {}
    return entry if isinstance(entry, dict) else {}


def _event_label(catalog: dict, event_id: str) -> str:
    return str(_catalog_entry(catalog, event_id).get("label") or event_id)


def _event_cooldown(catalog: dict, event_id: str) -> int:
    return max(0, int(_catalog_entry(catalog, event_id).get("cooldown", 0) or 0))


def is_on_cooldown(
    event_id: str,
    history: dict,
    current_turn: int,
    catalog: dict | None = None,
) -> bool:
    catalog = catalog or ensure_event_catalog()
    cooldown = _event_cooldown(catalog, event_id)
    if cooldown <= 0:
        return False
    for rec in reversed(history.get("records") or []):
        if not isinstance(rec, dict):
            continue
        if str(rec.get("event_id", "")) != event_id:
            continue
        last_turn = int(rec.get("turn", 0) or 0)
        return current_turn - last_turn < cooldown
    return False


def record_event_history(
    history: dict,
    plans: list[DirectorPlan],
    turn: int,
    *,
    persist: bool = True,
) -> dict:
    """Append emitted plans to history for cooldown tracking."""
    history = copy.deepcopy(history) if history else empty_event_history()
    records = history.setdefault("records", [])
    for plan in plans:
        records.append({
            "event_id": plan.event_id,
            "turn": turn,
            "priority": plan.priority,
            "reason": plan.reason,
            "category": plan.category,
        })
    if len(records) > 200:
        history["records"] = records[-200:]
    save_event_history(history, persist=persist)
    return history


def _make_plan(
    catalog: dict,
    event_id: str,
    priority: int,
    reason: str,
    participants: list[str] | None = None,
) -> DirectorPlan | None:
    entry = _catalog_entry(catalog, event_id)
    if not entry:
        return None
    tags = entry.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    return DirectorPlan(
        event_id=event_id,
        category=str(entry.get("category", "unknown")),
        priority=max(0, min(100, int(priority))),
        reason=reason,
        participants=list(participants or []),
        tags=[str(t) for t in tags],
    )


def _dedupe_plans(plans: list[DirectorPlan]) -> list[DirectorPlan]:
    seen: set[str] = set()
    out: list[DirectorPlan] = []
    for plan in sorted(plans, key=lambda p: p.priority, reverse=True):
        if plan.event_id in seen:
            continue
        seen.add(plan.event_id)
        out.append(plan)
    return out


def _score_relationship_plans(
    catalog: dict,
    session: dict,
    world_pack: dict,
    graph: dict | None,
    memory_store: dict | None,
    dynamics_store: dict | None,
) -> list[DirectorPlan]:
    if not config.RELATIONSHIP_ENGINE_ENABLED:
        return []

    from engine.relationship_core import ensure_graph, get_edge, resolve_player_name
    from engine.relationship_dynamics import get_dynamics
    from engine.relationship_memory import get_edge_events
    from engine.relationship_recall import ensure_dynamics_store, ensure_memory_store

    store = ensure_memory_store(memory_store)
    dyn_store = ensure_dynamics_store(dynamics_store)
    graph = graph or ensure_graph(world_pack, session=session)
    player = resolve_player_name(world_pack, session)
    plans: list[DirectorPlan] = []

    prefix = f"{player}→"
    targets: list[str] = []
    for key in (graph.get("edges") or {}):
        if key.startswith(prefix):
            target = key[len(prefix):].strip()
            if target and target not in targets:
                targets.append(target)
    for key in (store.get("edges") or {}):
        if key.startswith(prefix):
            target = key[len(prefix):].strip()
            if target and target not in targets:
                targets.append(target)
    for node in (graph.get("nodes") or {}):
        if node != player and node not in targets and get_edge(graph, player, node):
            targets.append(node)

    for target in targets:
        edge = get_edge(graph, player, target)
        dyn = get_dynamics(dyn_store, player, target)
        events = get_edge_events(store, player, target)
        recent = events[-5:] if events else []
        romance_count = sum(1 for e in recent if str(e.get("type", "")) in _ROMANCE_TYPES)
        conflict_count = sum(1 for e in recent if str(e.get("type", "")) in _CONFLICT_TYPES)
        participants = [player, target]

        if edge and edge.trust >= 80:
            plan = _make_plan(catalog, "midnight_talk", 85, "trust_over_80", participants)
            if plan:
                plans.append(plan)

        if dyn.momentum >= 20:
            plan = _make_plan(catalog, "midnight_talk", 82, "momentum_high", participants)
            if plan:
                plans.append(plan)
        elif dyn.momentum >= 15:
            plan = _make_plan(catalog, "gift_exchange", 75, "momentum_rising", participants)
            if plan:
                plans.append(plan)

        if dyn.bond_level >= 4:
            plan = _make_plan(catalog, "gift_exchange", 78, "bond_level_high", participants)
            if plan:
                plans.append(plan)

        if romance_count >= 2 and edge and edge.affection >= 60:
            plan = _make_plan(catalog, "confession", 80, "romance_warming", participants)
            if plan:
                plans.append(plan)

        if dyn.conflict_level >= 3 or conflict_count >= 3:
            plan = _make_plan(catalog, "jealousy", 88, "conflict_escalation", participants)
            if plan:
                plans.append(plan)
        elif dyn.conflict_level >= 2 or conflict_count >= 2:
            plan = _make_plan(catalog, "reconciliation", 72, "conflict_needs_repair", participants)
            if plan:
                plans.append(plan)

    for tri in (dyn_store.get("triangles") or [])[:2]:
        if not isinstance(tri, dict):
            continue
        nodes = [str(n) for n in (tri.get("nodes") or []) if str(n).strip()]
        if len(nodes) >= 3:
            plan = _make_plan(
                catalog,
                "romance_triangle",
                90,
                "triangle_tension",
                nodes[:3],
            )
            if plan:
                plans.append(plan)

    return plans


def _score_objective_plans(
    catalog: dict,
    session: dict,
    world_pack: dict,
    plot_state: dict | None = None,
) -> list[DirectorPlan]:
    if not config.OBJECTIVE_SYSTEM_ENABLED:
        return []

    from engine.objective_system import ensure_objectives

    ensure_objectives(session, world_pack, plot_state=plot_state)
    objectives = session.get("objectives") or {}
    plans: list[DirectorPlan] = []

    def _scan(scope: str) -> None:
        for item in objectives.get(scope) or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("status", "active")) not in ("active", "hidden"):
                continue
            progress = int(item.get("progress", 0) or 0)
            title = str(item.get("title", "")).strip() or "当前目标"
            if progress >= 80:
                plan = _make_plan(catalog, "reveal_truth", 88, f"objective_{progress}pct", [title])
                if plan:
                    plans.append(plan)
            elif progress >= 65:
                plan = _make_plan(catalog, "breakthrough", 75, f"objective_{progress}pct", [title])
                if plan:
                    plans.append(plan)
            elif progress >= 45:
                plan = _make_plan(catalog, "clue_found", 65, f"objective_{progress}pct", [title])
                if plan:
                    plans.append(plan)

    _scan("main")
    _scan("side")
    return plans


def _score_plot_plans(
    catalog: dict,
    session: dict,
    world_pack: dict,
    plot_state: dict | None,
) -> list[DirectorPlan]:
    if not config.PLOT_DIRECTOR_ENABLED:
        return []

    from engine.plot_director import ensure_plot_state

    plot_state = plot_state or ensure_plot_state(world_pack)
    turn = int(session.get("turn", 0) or 0)
    main_plot = plot_state.get("main_plot") or {}
    progress = int(main_plot.get("progress", 0) or 0)
    stage = int(main_plot.get("stage", 1) or 1)
    last_progress = int(plot_state.get("last_progress_turn", 0) or 0)
    stall = turn - last_progress if turn > 0 else 0
    unresolved = plot_state.get("unresolved_hooks") or []
    plans: list[DirectorPlan] = []
    plot_name = str(main_plot.get("name", "")).strip() or "主线"

    if stage >= 2 and progress >= 30:
        plan = _make_plan(catalog, "act_transition", 70, f"act_{stage}_progress_{progress}", [plot_name])
        if plan:
            plans.append(plan)

    if progress >= 75:
        plan = _make_plan(catalog, "major_twist", 82, "plot_progress_high", [plot_name])
        if plan:
            plans.append(plan)
    elif stall >= config.PLOT_DIRECTOR_STALL_THRESHOLD:
        plan = _make_plan(catalog, "major_twist", 75, "plot_stall", [plot_name])
        if plan:
            plans.append(plan)

    if len(unresolved) >= 4:
        plan = _make_plan(catalog, "boss_intro", 68, "many_open_hooks", [plot_name])
        if plan:
            plans.append(plan)

    mystery_hooks = [
        h for h in unresolved
        if isinstance(h, dict)
        and str(h.get("kind", "")) in ("mystery_event", "mystery_character")
    ]
    if mystery_hooks:
        plan = _make_plan(catalog, "assassination", 70, "mystery_hook_active", [plot_name])
        if plan:
            plans.append(plan)

    return plans


def _score_world_plans(
    catalog: dict,
    memory: dict,
    session: dict,
) -> list[DirectorPlan]:
    turn = int(session.get("turn", 0) or 0)
    factions = memory.get("factions") or {}
    attitudes = memory.get("faction_attitudes") or {}
    if not factions:
        return []

    plans: list[DirectorPlan] = []
    hostile_pairs = 0
    military_hostile = False
    government_active = False

    for name, data in factions.items():
        if not isinstance(data, dict):
            continue
        ftype = str(data.get("type", "")).lower()
        goals = data.get("goals") or []
        rel_player = str(data.get("relation_to_player", "neutral")).lower()
        if ftype in ("government", "political", "noble") and goals:
            government_active = True
        if rel_player in ("hostile", "enemy"):
            military_hostile = military_hostile or ftype in ("military", "army", "rebel")

        targets = attitudes.get(name) or {}
        for _target, att_data in targets.items():
            att = float((att_data or {}).get("attitude", 0.5) or 0.5)
            if att <= 0.25:
                hostile_pairs += 1

    if hostile_pairs >= 2 or military_hostile:
        plan = _make_plan(catalog, "war", 78, "faction_hostility", ["世界局势"])
        if plan:
            plans.append(plan)

    if military_hostile:
        plan = _make_plan(catalog, "rebellion", 80, "military_tension", ["世界局势"])
        if plan:
            plans.append(plan)

    if government_active and turn >= 5:
        plan = _make_plan(catalog, "political_pressure", 65, "faction_political_action", ["世界局势"])
        if plan:
            plans.append(plan)

    from engine.world_driver import generate_plot_hooks
    hooks = generate_plot_hooks(memory, turn)
    if hooks and any(k in hooks[0] for k in ("刺杀", "暗杀", "密谋", "叛乱", "战争")):
        event_id = "assassination" if any(k in hooks[0] for k in ("刺杀", "暗杀")) else "rebellion"
        plan = _make_plan(catalog, event_id, 72, "world_hook_signal", ["世界局势"])
        if plan:
            plans.append(plan)

    return plans


def build_director_plans(
    session: dict,
    world_pack: dict,
    *,
    memory: dict | None = None,
    graph: dict | None = None,
    relationship_memory: dict | None = None,
    relationship_dynamics: dict | None = None,
    plot_state: dict | None = None,
    event_history: dict | None = None,
    catalog: dict | None = None,
) -> list[DirectorPlan]:
    """
    Score events from relationship / objective / plot / world sources.
    Returns up to EVENT_DIRECTOR_MAX_PLANS plans after cooldown filter.
    """
    if not config.EVENT_DIRECTOR_ENABLED:
        return []

    catalog = catalog or ensure_event_catalog()
    history = event_history if event_history is not None else load_event_history()
    turn = int(session.get("turn", 0) or 0)

    if memory is None:
        from engine.memory import load_memory
        memory = load_memory()

    candidates: list[DirectorPlan] = []
    candidates.extend(_score_relationship_plans(
        catalog, session, world_pack, graph, relationship_memory, relationship_dynamics,
    ))
    candidates.extend(_score_objective_plans(catalog, session, world_pack, plot_state))
    candidates.extend(_score_plot_plans(catalog, session, world_pack, plot_state))
    candidates.extend(_score_world_plans(catalog, memory, session))

    candidates = _dedupe_plans(candidates)
    filtered = [
        p for p in candidates
        if not is_on_cooldown(p.event_id, history, turn, catalog)
    ]
    filtered.sort(key=lambda p: p.priority, reverse=True)
    return filtered[: config.EVENT_DIRECTOR_MAX_PLANS]


def format_director_plan(
    plans: list[DirectorPlan],
    catalog: dict | None = None,
) -> str:
    """Format TOP plans for {{DIRECTOR_PLAN}} injection (≤300 tokens budget)."""
    if not plans:
        return ""

    catalog = catalog or ensure_event_catalog()
    lines = ["【事件导演 — Director Plan（优先参考，非强制）】", "当前推荐事件："]
    for plan in plans:
        label = _event_label(catalog, plan.event_id)
        lines.append(f"- {label}（{plan.category} · 优先级 {plan.priority}）— {plan.reason}")

    parts: list[str] = []
    for plan in plans:
        if plan.participants:
            parts.extend(plan.participants)
    if parts:
        unique = []
        seen: set[str] = set()
        for name in parts:
            if name not in seen:
                seen.add(name)
                unique.append(name)
        lines.append(f"参与者：{' / '.join(unique[:6])}")

    text = "\n".join(lines)
    max_chars = config.EVENT_DIRECTOR_PLAN_MAX_CHARS
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."
    return text


def build_and_record_director_plan(
    session: dict,
    world_pack: dict,
    *,
    memory: dict | None = None,
    graph: dict | None = None,
    relationship_memory: dict | None = None,
    relationship_dynamics: dict | None = None,
    plot_state: dict | None = None,
    persist_history: bool = True,
) -> str:
    """Build plans, record history for cooldown, return prompt block."""
    if not config.EVENT_DIRECTOR_ENABLED:
        return ""

    catalog = ensure_event_catalog()
    history = load_event_history()
    turn = int(session.get("turn", 0) or 0)
    plans = build_director_plans(
        session,
        world_pack,
        memory=memory,
        graph=graph,
        relationship_memory=relationship_memory,
        relationship_dynamics=relationship_dynamics,
        plot_state=plot_state,
        event_history=history,
        catalog=catalog,
    )
    if plans:
        record_event_history(history, plans, turn, persist=persist_history)
    return format_director_plan(plans, catalog)
