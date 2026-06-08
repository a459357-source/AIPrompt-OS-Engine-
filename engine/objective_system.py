"""
objective_system.py — Objective System (V3.2)
==============================================
Player-facing main/side objectives stored in session_state; synced with
plot_director main progress; injected into prompts and exposed via API/UI.
"""

from __future__ import annotations

import copy
import logging
import uuid
from typing import Any

import config

logger = logging.getLogger(__name__)

OBJECTIVE_STATUSES = frozenset({"active", "completed", "failed", "hidden"})
MAIN_OBJECTIVE_ID = "main_001"


def default_objectives(main_goal: str = "") -> dict:
    """Build initial objectives from world main_goal."""
    title = (main_goal or "").strip() or "推进剧情发展，探索角色关系"
    return {
        "main": [{
            "id": MAIN_OBJECTIVE_ID,
            "title": title[:120],
            "progress": 0,
            "status": "active",
        }],
        "side": [],
    }


def _normalize_objectives(raw: dict | None) -> dict:
    """Ensure objectives dict has main/side list structure."""
    if not isinstance(raw, dict):
        return default_objectives()
    main = raw.get("main") if isinstance(raw.get("main"), list) else []
    side = raw.get("side") if isinstance(raw.get("side"), list) else []
    return {"main": main, "side": side}


def _clip_progress(value: int) -> int:
    return max(0, min(100, int(value)))


def _find_objective(objectives: dict, obj_id: str) -> tuple[str, int, dict] | None:
    """Return (scope, index, item) for id or None."""
    for scope in ("main", "side"):
        for idx, item in enumerate(objectives.get(scope) or []):
            if isinstance(item, dict) and str(item.get("id", "")).strip() == obj_id:
                return scope, idx, item
    return None


def ensure_objectives(
    session: dict,
    world_pack: dict | None = None,
    plot_state: dict | None = None,
) -> dict:
    """
    Lazy-init objectives on old saves; sync main progress from plot_director.
    Mutates and returns session.
    """
    if not config.OBJECTIVE_SYSTEM_ENABLED:
        return session

    objectives = session.get("objectives")
    if not objectives or not isinstance(objectives, dict):
        main_goal = ""
        if world_pack is None:
            from engine import io_utils
            world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
        world = world_pack.get("world", {}) if isinstance(world_pack, dict) else {}
        main_goal = str(world.get("main_goal") or "").strip()
        session["objectives"] = default_objectives(main_goal)
        logger.info("Objectives initialized from main_goal=%r", main_goal[:60])

    objectives = _normalize_objectives(session.get("objectives"))
    session["objectives"] = objectives

    if plot_state is None:
        from engine.plot_director import ensure_plot_state
        plot_state = ensure_plot_state(world_pack)

    sync_main_objective_progress(session, plot_state)
    return session


def sync_main_objective_progress(session: dict, plot_state: dict) -> None:
    """Mirror plot_director.main_plot.progress onto the primary main objective."""
    if not config.OBJECTIVE_SYSTEM_ENABLED:
        return

    objectives = _normalize_objectives(session.get("objectives"))
    main_list = objectives.get("main") or []
    if not main_list:
        world_goal = str(
            (plot_state.get("main_plot") or {}).get("name") or ""
        ).strip()
        objectives["main"] = default_objectives(world_goal)["main"]
        main_list = objectives["main"]

    main_plot = plot_state.get("main_plot") or {}
    progress = _clip_progress(int(main_plot.get("progress", 0) or 0))
    plot_name = str(main_plot.get("name") or "").strip()

    primary = main_list[0]
    if isinstance(primary, dict):
        primary["progress"] = progress
        if plot_name and not str(primary.get("title", "")).strip():
            primary["title"] = plot_name[:120]

    session["objectives"] = objectives


def sync_plot_from_main_objective(session: dict, plot_state: dict) -> dict:
    """Push primary main objective progress back to plot_state."""
    objectives = _normalize_objectives(session.get("objectives"))
    main_list = objectives.get("main") or []
    if not main_list or not isinstance(main_list[0], dict):
        return plot_state

    progress = _clip_progress(int(main_list[0].get("progress", 0) or 0))
    state = copy.deepcopy(plot_state)
    main_plot = state.setdefault("main_plot", {})
    main_plot["progress"] = progress
    return state


def apply_objective_updates(session: dict, updates: list | None, turn: int) -> dict:
    """Merge AI objective_updates into session objectives."""
    if not config.OBJECTIVE_SYSTEM_ENABLED or not updates:
        return session

    objectives = copy.deepcopy(_normalize_objectives(session.get("objectives")))
    main_progress_changed = False

    for item in updates:
        if not isinstance(item, dict):
            continue

        action = str(item.get("action") or "").strip().lower()
        if action == "add":
            scope = str(item.get("scope") or "side").strip().lower()
            if scope not in ("main", "side"):
                scope = "side"
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            status = str(item.get("status") or "active").strip().lower()
            if status not in OBJECTIVE_STATUSES:
                status = "active"
            obj_id = str(item.get("id") or f"{scope}_{uuid.uuid4().hex[:6]}")
            new_obj = {
                "id": obj_id,
                "title": title[:120],
                "progress": _clip_progress(int(item.get("progress", 0) or 0)),
                "status": status,
            }
            objectives.setdefault(scope, []).append(new_obj)
            if scope == "main" and "progress" in item:
                main_progress_changed = True
            continue

        obj_id = str(item.get("id") or "").strip()
        if not obj_id:
            continue

        found = _find_objective(objectives, obj_id)
        if not found:
            logger.debug("Objective update: unknown id %r", obj_id)
            continue

        scope, idx, target = found
        if "title" in item:
            title = str(item.get("title") or "").strip()
            if title:
                target["title"] = title[:120]

        if "progress" in item:
            target["progress"] = _clip_progress(int(item.get("progress") or 0))
            if scope == "main":
                main_progress_changed = True
        elif "progress_delta" in item:
            delta = int(item.get("progress_delta") or 0)
            target["progress"] = _clip_progress(
                int(target.get("progress", 0) or 0) + delta
            )
            if scope == "main":
                main_progress_changed = True

        if "status" in item:
            status = str(item.get("status") or "").strip().lower()
            if status in OBJECTIVE_STATUSES:
                target["status"] = status
                if status == "completed":
                    target["progress"] = 100

        objectives[scope][idx] = target

    session["objectives"] = objectives

    if main_progress_changed:
        from engine.plot_director import load_plot_state, save_plot_state
        plot_state = load_plot_state()
        updated_plot = sync_plot_from_main_objective(session, plot_state)
        save_plot_state(updated_plot)
        logger.info(
            "Objective main progress synced to plot_director: %s%%",
            updated_plot.get("main_plot", {}).get("progress"),
        )

    return session


def apply_rule_progress(
    session: dict,
    old_status: str,
    new_status: str,
    turn: int,
) -> dict:
    """Bump active side objectives when story status advances."""
    del turn  # reserved for future turn-based rules
    if not config.OBJECTIVE_SYSTEM_ENABLED:
        return session

    if old_status == new_status:
        return session

    try:
        old_idx = config.STATUS_ORDER.index(old_status)
        new_idx = config.STATUS_ORDER.index(new_status)
    except ValueError:
        return session

    if new_idx <= old_idx:
        return session

    delta = config.OBJECTIVE_RULE_PROGRESS_DELTA
    objectives = copy.deepcopy(_normalize_objectives(session.get("objectives")))
    changed = False
    for item in objectives.get("side") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("status", "")).strip().lower() != "active":
            continue
        item["progress"] = _clip_progress(int(item.get("progress", 0) or 0) + delta)
        changed = True

    if changed:
        session["objectives"] = objectives
        logger.debug(
            "Rule progress: status %s→%s, side objectives +%d",
            old_status, new_status, delta,
        )
    return session


def _active_items(objectives: dict) -> tuple[list[dict], list[dict]]:
    main_active = [
        o for o in (objectives.get("main") or [])
        if isinstance(o, dict) and str(o.get("status", "")).lower() == "active"
    ]
    side_active = [
        o for o in (objectives.get("side") or [])
        if isinstance(o, dict) and str(o.get("status", "")).lower() == "active"
    ]
    return main_active, side_active


def build_objectives_context(session: dict, world_pack: dict | None = None) -> str:
    """Prompt block for active objectives only."""
    if not config.OBJECTIVE_SYSTEM_ENABLED:
        return ""

    turn = int(session.get("turn", 0) or 0)
    if turn <= 0:
        return ""

    objectives = _normalize_objectives(session.get("objectives"))
    main_active, side_active = _active_items(objectives)
    if not main_active and not side_active:
        return ""

    rel_hints: dict[str, int] = {}
    if config.RELATIONSHIP_ENGINE_ENABLED:
        from engine import io_utils
        from engine.relationship_core import read_api_for_objective

        if world_pack is None:
            world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
        rel_hints = read_api_for_objective(session, world_pack)

    lines = ["【当前目标】（每轮须让玩家感受到朝目标前进；可输出 objective_updates 更新进度）"]
    for obj in main_active[:1]:
        title = str(obj.get("title", "")).strip()
        oid = str(obj.get("id", "")).strip()
        progress = int(obj.get("progress", 0) or 0)
        if oid in rel_hints:
            progress = max(progress, rel_hints[oid])
        lines.append(f"主线：{title}（进度 {progress}%）")

    side_limit = config.OBJECTIVE_MAX_SIDE_ACTIVE
    for obj in side_active[:side_limit]:
        title = str(obj.get("title", "")).strip()
        oid = str(obj.get("id", "")).strip()
        progress = int(obj.get("progress", 0) or 0)
        if oid in rel_hints:
            progress = max(progress, rel_hints[oid])
        lines.append(f"支线：{title}（进度 {progress}%）")

    extra = len(side_active) - side_limit
    if extra > 0:
        lines.append(f"（另有 {extra} 条活跃支线未列出）")

    return "\n".join(lines)


def visible_for_game(session: dict) -> dict:
    """Active objectives for Game UI (compact)."""
    if not config.OBJECTIVE_SYSTEM_ENABLED:
        return {"main": [], "side": []}

    objectives = _normalize_objectives(session.get("objectives"))
    main_active, side_active = _active_items(objectives)
    game_side_limit = min(3, config.OBJECTIVE_MAX_SIDE_ACTIVE)
    side_shown = side_active[:game_side_limit]
    extra = max(0, len(side_active) - game_side_limit)

    def _serialize(items: list[dict]) -> list[dict]:
        out: list[dict] = []
        for o in items:
            if not isinstance(o, dict):
                continue
            out.append({
                "id": str(o.get("id", "")),
                "title": str(o.get("title", ""))[:120],
                "progress": _clip_progress(int(o.get("progress", 0) or 0)),
                "status": str(o.get("status", "active")),
            })
        return out

    return {
        "main": _serialize(main_active[:1]),
        "side": _serialize(side_shown),
        "side_extra": extra,
    }


def dashboard_payload(session: dict) -> dict:
    """Full objectives for Dashboard read-only task manager."""
    if not config.OBJECTIVE_SYSTEM_ENABLED:
        return {"main": [], "side": [], "completed": [], "failed": [], "hidden": []}

    objectives = _normalize_objectives(session.get("objectives"))

    def _bucket(scope: str, status: str | None = None) -> list[dict]:
        items: list[dict] = []
        for o in objectives.get(scope) or []:
            if not isinstance(o, dict):
                continue
            st = str(o.get("status", "active")).lower()
            if status is None or st == status:
                items.append({
                    "id": str(o.get("id", "")),
                    "title": str(o.get("title", ""))[:120],
                    "progress": _clip_progress(int(o.get("progress", 0) or 0)),
                    "status": st,
                    "scope": scope,
                })
        return items

    completed: list[dict] = []
    failed: list[dict] = []
    hidden: list[dict] = []
    for scope in ("main", "side"):
        for o in objectives.get(scope) or []:
            if not isinstance(o, dict):
                continue
            st = str(o.get("status", "active")).lower()
            entry = {
                "id": str(o.get("id", "")),
                "title": str(o.get("title", ""))[:120],
                "progress": _clip_progress(int(o.get("progress", 0) or 0)),
                "status": st,
                "scope": scope,
            }
            if st == "completed":
                completed.append(entry)
            elif st == "failed":
                failed.append(entry)
            elif st == "hidden":
                hidden.append(entry)

    return {
        "main": _bucket("main", "active"),
        "side": _bucket("side", "active"),
        "completed": completed,
        "failed": failed,
        "hidden": hidden,
    }


def process_turn_objectives(
    session: dict,
    ai_response: dict,
    old_status: str,
    world_pack: dict | None = None,
) -> dict:
    """
    Full per-turn objective pipeline: ensure, AI updates, rule progress, plot sync.
    """
    if not config.OBJECTIVE_SYSTEM_ENABLED:
        return session

    from engine.plot_director import ensure_plot_state

    plot_state = ensure_plot_state(world_pack)
    ensure_objectives(session, world_pack, plot_state)

    updates = ai_response.get("objective_updates")
    if isinstance(updates, list) and updates:
        apply_objective_updates(session, updates, int(session.get("turn", 0) or 0))

    new_status = str(session.get("status", old_status))
    apply_rule_progress(session, old_status, new_status, int(session.get("turn", 0) or 0))

    plot_state = ensure_plot_state(world_pack)
    sync_main_objective_progress(session, plot_state)

    if config.RELATIONSHIP_ENGINE_ENABLED:
        from engine.relationship_core import ensure_graph, sync_objectives_from_graph

        graph = ensure_graph(world_pack, session=session)
        sync_objectives_from_graph(session, graph, world_pack)

    return session
