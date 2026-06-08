"""
director_runtime.py — V5.2 Director Runtime (Phase B)
======================================================
Turn-time scheduler: promote plans to ACTIVE nodes, advance lifecycle,
and format stronger prompt guidance than Phase A recommendations.
"""

from __future__ import annotations

import logging

import config
from engine.director_state import (
    ACTIVE,
    COOLDOWN,
    FAILED,
    PENDING,
    RESOLVED,
    DirectorEventState,
    activate_event,
    append_lifecycle,
    bump_active_turn,
    empty_director_state,
    get_current_event,
    get_pending_events,
    load_director_state,
    save_director_state,
    set_current_event,
    set_pending_events,
    transition_event,
)
from engine.event_director import (
    DirectorPlan,
    build_director_plans,
    ensure_event_catalog,
    is_on_cooldown,
    load_event_history,
    record_event_history,
    save_event_history,
)

logger = logging.getLogger(__name__)

_RESOLUTION_HINTS = (
    "完成", "结束", "告一段落", "尘埃落定", "真相大白", "和解", "告白成功",
    "表白", "收下", "原谅", "结盟", "突破", "线索", "揭露", "转折",
)


def _event_label(catalog: dict, event_id: str) -> str:
    events = catalog.get("events") or {}
    entry = events.get(event_id) or {}
    return str(entry.get("label") or event_id)


def _plan_to_pending(plan: DirectorPlan, turn: int) -> DirectorEventState:
    return DirectorEventState.from_plan(plan, state=PENDING, turn=turn)


def _cooldown_from_lifecycle(
    state: dict,
    event_id: str,
    current_turn: int,
    catalog: dict,
) -> bool:
    if is_on_cooldown(event_id, load_event_history(), current_turn, catalog):
        return True
    for item in reversed(state.get("lifecycle") or []):
        inst = DirectorEventState.from_dict(item)
        if not inst or inst.event_id != event_id:
            continue
        if inst.state not in (RESOLVED, FAILED, COOLDOWN):
            continue
        cooldown = max(0, int((catalog.get("events", {}).get(event_id, {}) or {}).get("cooldown", 0) or 0))
        if cooldown <= 0:
            return False
        return current_turn - inst.last_turn < cooldown
    return False


def _select_new_plans(
    session: dict,
    world_pack: dict,
    director_state: dict,
    *,
    memory: dict | None = None,
    graph: dict | None = None,
    relationship_memory: dict | None = None,
    relationship_dynamics: dict | None = None,
    plot_state: dict | None = None,
) -> list[DirectorPlan]:
    catalog = ensure_event_catalog()
    turn = int(session.get("turn", 0) or 0)
    plans = build_director_plans(
        session,
        world_pack,
        memory=memory,
        graph=graph,
        relationship_memory=relationship_memory,
        relationship_dynamics=relationship_dynamics,
        plot_state=plot_state,
        catalog=catalog,
    )
    return [
        p for p in plans
        if not _cooldown_from_lifecycle(director_state, p.event_id, turn, catalog)
    ]


def _promote_top_plan(
    director_state: dict,
    plans: list[DirectorPlan],
    turn: int,
) -> tuple[dict, DirectorEventState | None]:
    if not plans:
        return director_state, None

    top = plans[0]
    current = activate_event(DirectorEventState.from_plan(top, state=PENDING, turn=turn), turn)
    pending = [_plan_to_pending(p, turn) for p in plans[1: config.DIRECTOR_MAX_PENDING + 1]]
    director_state = set_current_event(director_state, current)
    director_state = set_pending_events(director_state, pending)
    save_director_state(director_state)
    logger.info(
        "Director activated event=%s turn=%d priority=%d",
        current.event_id, turn, current.priority,
    )
    return director_state, current


def _finalize_event(
    director_state: dict,
    event: DirectorEventState,
    final_state: str,
    turn: int,
    *,
    persist: bool = True,
) -> dict:
    catalog = ensure_event_catalog()
    cooled = transition_event(event, COOLDOWN, turn=turn)
    cooled.state = COOLDOWN
    director_state = append_lifecycle(director_state, cooled)
    director_state = set_current_event(director_state, None)

    history = load_event_history()
    plan = DirectorPlan(
        event_id=event.event_id,
        category=event.category,
        priority=event.priority,
        reason=f"{final_state.lower()}:{event.reason}",
        participants=event.participants,
        tags=event.tags,
    )
    record_event_history(history, [plan], turn, persist=persist)
    save_director_state(director_state, persist=persist)
    logger.info(
        "Director finalized event=%s as %s turn=%d",
        event.event_id, final_state, turn,
    )
    return director_state


def _story_signals_resolution(story: str, event: DirectorEventState, catalog: dict) -> bool:
    text = str(story or "")
    if not text.strip():
        return False
    label = _event_label(catalog, event.event_id)
    keywords = {label, event.event_id.replace("_", "")}
    keywords.update(event.tags or [])
    for kw in keywords:
        if kw and len(kw) >= 2 and kw in text:
            return True
    return any(h in text for h in _RESOLUTION_HINTS)


def prepare_director_prompt(
    session: dict,
    world_pack: dict,
    *,
    memory: dict | None = None,
    graph: dict | None = None,
    relationship_memory: dict | None = None,
    relationship_dynamics: dict | None = None,
    plot_state: dict | None = None,
) -> str:
    """
    Pre-turn hook: ensure an ACTIVE node exists or promote the top plan.
    Returns {{DIRECTOR_PLAN}} prompt block.
    """
    if not config.EVENT_DIRECTOR_ENABLED or not config.DIRECTOR_STATE_MACHINE_ENABLED:
        from engine.event_director import build_and_record_director_plan
        return build_and_record_director_plan(
            session,
            world_pack,
            memory=memory,
            graph=graph,
            relationship_memory=relationship_memory,
            relationship_dynamics=relationship_dynamics,
            plot_state=plot_state,
            persist_history=True,
        )

    catalog = ensure_event_catalog()
    turn = int(session.get("turn", 0) or 0)
    director_state = load_director_state()
    current = get_current_event(director_state)

    if current and current.state == ACTIVE:
        if current.turns_active >= config.DIRECTOR_EVENT_MAX_ACTIVE_TURNS:
            director_state = _finalize_event(director_state, current, FAILED, turn)
            current = None
        else:
            return _format_prompt_block(current, get_pending_events(director_state), catalog)

    if current is None:
        plans = _select_new_plans(
            session,
            world_pack,
            director_state,
            memory=memory,
            graph=graph,
            relationship_memory=relationship_memory,
            relationship_dynamics=relationship_dynamics,
            plot_state=plot_state,
        )
        director_state, current = _promote_top_plan(director_state, plans, turn)

    return _format_prompt_block(current, get_pending_events(director_state), catalog)


def advance_director_after_turn(
    session: dict,
    story: str,
    *,
    persist: bool = True,
) -> dict:
    """Post-turn hook: detect resolution or timeout for ACTIVE event."""
    if not config.EVENT_DIRECTOR_ENABLED or not config.DIRECTOR_STATE_MACHINE_ENABLED:
        return load_director_state()

    turn = int(session.get("turn", 0) or 0)
    director_state = load_director_state()
    current = get_current_event(director_state)
    if not current or current.state != ACTIVE:
        return director_state

    catalog = ensure_event_catalog()
    current = bump_active_turn(current, turn)
    director_state = set_current_event(director_state, current)

    if _story_signals_resolution(story, current, catalog):
        director_state = _finalize_event(director_state, current, RESOLVED, turn, persist=persist)
    elif current.turns_active >= config.DIRECTOR_EVENT_MAX_ACTIVE_TURNS:
        director_state = _finalize_event(director_state, current, FAILED, turn, persist=persist)
    else:
        save_director_state(director_state, persist=persist)

    return director_state


def _format_prompt_block(
    current: DirectorEventState | None,
    pending: list[DirectorEventState],
    catalog: dict,
) -> str:
    lines: list[str] = []

    if current and current.state == ACTIVE:
        label = _event_label(catalog, current.event_id)
        max_turns = config.DIRECTOR_EVENT_MAX_ACTIVE_TURNS
        lines.append("【事件导演 — 当前剧情节点（ACTIVE · 须推进）】")
        lines.append(
            f"正在进行：{label}（{current.category} · 优先级 {current.priority}）"
        )
        lines.append(
            f"状态：ACTIVE · 第 {current.turns_active}/{max_turns} 回合 · 原因：{current.reason}"
        )
        if current.participants:
            lines.append(f"参与者：{' / '.join(current.participants[:6])}")
        lines.append(
            "请在本轮 story 中明确推进或收束该事件；不得完全忽略。"
        )

    if pending:
        lines.append("【候补事件（PENDING）】")
        for item in pending[: config.DIRECTOR_MAX_PENDING]:
            label = _event_label(catalog, item.event_id)
            lines.append(f"- {label}（优先级 {item.priority}）")

    if not lines:
        return ""

    text = "\n".join(lines)
    max_chars = config.EVENT_DIRECTOR_PLAN_MAX_CHARS
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."
    return text


def reset_director_state(*, persist: bool = True) -> dict:
    state = empty_director_state()
    save_director_state(state, persist=persist)
    return state
