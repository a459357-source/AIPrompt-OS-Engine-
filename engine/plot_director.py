"""
plot_director.py — Plot Director (V3.1)
========================================
Tracks main-plot progress and narrative hooks; injects soft director advice
into prompts and periodically analyzes recent story via LLM.
"""

from __future__ import annotations

import copy
import json
import logging
import uuid
from typing import Any

import config
from engine import io_utils

logger = logging.getLogger(__name__)

HOOK_KINDS = frozenset({
    "foreshadow",
    "mystery_event",
    "mystery_character",
    "unfinished_task",
})


def default_plot_state(main_goal: str = "") -> dict:
    """Return a fresh plot_state dict."""
    name = (main_goal or "").strip() or "推进剧情发展，探索角色关系"
    return {
        "main_plot": {
            "name": name,
            "progress": 0,
            "stage": 1,
        },
        "unresolved_hooks": [],
        "resolved_hooks": [],
        "last_progress_turn": 0,
        "last_analysis_turn": 0,
    }


def load_plot_state() -> dict:
    """Load plot_state.json; return default if missing."""
    try:
        data = io_utils.read_json(config.PLOT_STATE_PATH)
        if isinstance(data, dict) and "main_plot" in data:
            return data
    except Exception:
        pass
    return default_plot_state()


def save_plot_state(state: dict, *, persist: bool = True) -> None:
    """Persist plot_state to disk."""
    if persist:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        io_utils.write_json(config.PLOT_STATE_PATH, state)


def init_plot_state(world_pack: dict, *, persist: bool = True) -> dict:
    """Initialize plot_state from world_pack.main_goal."""
    world = world_pack.get("world", {}) if isinstance(world_pack, dict) else {}
    main_goal = str(world.get("main_goal") or "").strip()
    state = default_plot_state(main_goal)
    save_plot_state(state, persist=persist)
    logger.info("Plot director initialized: main_plot=%r", state["main_plot"]["name"][:60])
    return state


def ensure_plot_state(world_pack: dict | None = None) -> dict:
    """Load plot_state or lazy-init from world_pack when missing."""
    try:
        if config.PLOT_STATE_PATH.exists():
            state = load_plot_state()
            if state.get("main_plot"):
                return state
    except Exception:
        pass
    if world_pack is None:
        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
    return init_plot_state(world_pack)


def build_director_advice(plot_state: dict, session_state: dict) -> str:
    """
    Rule-based soft advice for prompt injection. Returns empty string when
    nothing noteworthy.
    """
    if not config.PLOT_DIRECTOR_ENABLED:
        return ""

    turn = int(session_state.get("turn", 0) or 0)
    if turn <= 0:
        return ""

    main_plot = plot_state.get("main_plot") or {}
    progress = int(main_plot.get("progress", 0) or 0)
    plot_name = str(main_plot.get("name") or "主线").strip()
    last_progress = int(plot_state.get("last_progress_turn", 0) or 0)
    stall = turn - last_progress if last_progress >= 0 else turn
    open_hooks: list = plot_state.get("unresolved_hooks") or []

    lines: list[str] = []
    triggered = False

    if stall >= config.PLOT_DIRECTOR_STALL_THRESHOLD:
        triggered = True
        lines.append(
            f"- 主线「{plot_name[:80]}」已 {stall} 回合未推进"
            f"（上次推进：第 {last_progress} 回合），本轮可适当朝主线迈进一步。"
        )

    if len(open_hooks) >= 4:
        triggered = True
        titles = [str(h.get("title", "")).strip() for h in open_hooks if isinstance(h, dict)]
        titles = [t for t in titles if t][:5]
        if titles:
            lines.append(
                f"- 开放伏笔（{len(open_hooks)}）：{'、'.join(titles)}；"
                "若场景合适，可解释或推进其中一条。"
            )

    oldest_stale = _oldest_open_hook_age(open_hooks, turn)
    if oldest_stale >= config.PLOT_DIRECTOR_OLD_HOOK_TURNS:
        triggered = True
        lines.append(
            f"- 部分伏笔已悬挂 {oldest_stale} 回合以上，避免无限调查循环，"
            "本轮宜给出阶段性解释或推进。"
        )

    if progress < 20 and turn > 15:
        triggered = True
        lines.append(
            f"- 主线进度偏低（{progress}%），可在不打断当前场景的前提下"
            "向长期目标靠近。"
        )

    if config.RELATIONSHIP_ENGINE_ENABLED:
        from engine import io_utils
        from engine.relationship_core import (
            build_relationship_director_hint,
            consume_pending_events_for_director,
            ensure_graph,
            read_api_for_plot,
            save_graph,
        )

        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
        rel_graph = ensure_graph(world_pack, session=session_state)
        rel_hint = build_relationship_director_hint(rel_graph)
        if rel_hint:
            triggered = True
            lines.append(f"- {rel_hint}")
            consume_pending_events_for_director(rel_graph)
            save_graph(rel_graph, persist=True)

        plot_mem = read_api_for_plot(session_state, world_pack)
        if plot_mem:
            triggered = True
            for line in plot_mem.splitlines():
                if line.strip():
                    lines.append(f"- {line.strip()}")

    if not triggered:
        return ""

    header = (
        "【剧情导演建议】（弱约束，仅供参考，不得生硬打断当前场景）"
    )
    return header + "\n" + "\n".join(lines)


def _oldest_open_hook_age(open_hooks: list, current_turn: int) -> int:
    ages: list[int] = []
    for h in open_hooks:
        if not isinstance(h, dict):
            continue
        created = int(h.get("created_turn", 0) or 0)
        if created > 0:
            ages.append(current_turn - created)
    return max(ages) if ages else 0


def apply_analysis_result(plot_state: dict, analysis: dict, turn: int) -> dict:
    """Merge LLM analysis JSON into plot_state."""
    state = copy.deepcopy(plot_state)
    main_plot = state.setdefault("main_plot", default_plot_state()["main_plot"])

    delta = int(analysis.get("progress_delta", 0) or 0)
    progress = int(main_plot.get("progress", 0) or 0)
    main_plot["progress"] = max(0, min(100, progress + delta))

    stage = analysis.get("stage")
    if isinstance(stage, int) and 1 <= stage <= 5:
        main_plot["stage"] = stage

    if analysis.get("progress_made"):
        state["last_progress_turn"] = turn

    state["last_analysis_turn"] = turn

    resolved_titles = {
        str(t).strip() for t in (analysis.get("resolved_titles") or []) if str(t).strip()
    }
    if resolved_titles:
        still_open: list[dict] = []
        for hook in state.get("unresolved_hooks") or []:
            if not isinstance(hook, dict):
                continue
            title = str(hook.get("title", "")).strip()
            if title in resolved_titles:
                resolved = copy.deepcopy(hook)
                resolved["status"] = "resolved"
                resolved["resolved_turn"] = turn
                state.setdefault("resolved_hooks", []).append(resolved)
            else:
                still_open.append(hook)
        state["unresolved_hooks"] = still_open

    new_hooks = analysis.get("new_hooks") or []
    if isinstance(new_hooks, list):
        for item in new_hooks:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            kind = str(item.get("kind") or "foreshadow").strip()
            if kind not in HOOK_KINDS:
                kind = "foreshadow"
            if _hook_title_exists(state, title):
                continue
            open_hooks: list = state.setdefault("unresolved_hooks", [])
            if len(open_hooks) >= config.PLOT_DIRECTOR_MAX_OPEN_HOOKS:
                logger.warning(
                    "Plot director: open hooks at cap (%d), skipping %r",
                    config.PLOT_DIRECTOR_MAX_OPEN_HOOKS,
                    title,
                )
                continue
            open_hooks.append({
                "id": str(uuid.uuid4())[:8],
                "title": title,
                "kind": kind,
                "created_turn": turn,
                "status": "open",
            })

    return state


def _hook_title_exists(state: dict, title: str) -> bool:
    title = title.strip()
    for hook in (state.get("unresolved_hooks") or []) + (state.get("resolved_hooks") or []):
        if isinstance(hook, dict) and str(hook.get("title", "")).strip() == title:
            return True
    return False


def _recent_history_text(session_state: dict, n: int = 5) -> str:
    history = session_state.get("history") or []
    chunk = history[-n:] if history else []
    parts: list[str] = []
    for entry in chunk:
        if not isinstance(entry, dict):
            continue
        t = entry.get("turn", "?")
        scene = entry.get("scene", "")
        story = str(entry.get("story") or entry.get("summary") or "")[:400]
        choice = entry.get("choice", "")
        parts.append(f"T{t} 场景={scene} 选择={choice}\n{story}")
    return "\n---\n".join(parts)


def _hooks_summary(state: dict) -> str:
    open_hooks = state.get("unresolved_hooks") or []
    if not open_hooks:
        return "（无开放伏笔）"
    lines = []
    for h in open_hooks[:10]:
        if not isinstance(h, dict):
            continue
        lines.append(
            f"- {h.get('title', '?')} ({h.get('kind', 'foreshadow')}, "
            f"turn {h.get('created_turn', '?')})"
        )
    return "\n".join(lines)


def analyze_plot_with_llm(
    plot_state: dict,
    session_state: dict,
    world_pack: dict,
) -> dict | None:
    """Call LLM to analyze recent plot progress and hooks."""
    from engine.deepseek_client import call_deepseek, DeepSeekError

    world = world_pack.get("world", {}) if isinstance(world_pack, dict) else {}
    main_goal = str(world.get("main_goal") or plot_state.get("main_plot", {}).get("name") or "")
    turn = int(session_state.get("turn", 0) or 0)
    recent = _recent_history_text(session_state, config.PLOT_DIRECTOR_ANALYSIS_INTERVAL)
    main_plot = plot_state.get("main_plot") or {}

    system = (
        "你是 Galgame 剧情导演分析师。根据最近回合正文，评估主线推进与伏笔状态。"
        "只输出合法 JSON，不要其他文字。字段："
        "progress_delta(int 0-15), stage(int 1-5), progress_made(bool), "
        "new_hooks([{title, kind}]), resolved_titles([string]), summary(string)。"
        f"kind 只能是 {', '.join(sorted(HOOK_KINDS))}。"
        "progress_made 表示本轮剧情实质朝主线目标前进。"
        "new_hooks 仅记录新出现的未解伏笔，不要重复已有。"
        "resolved_titles 列出本轮已解释或收束的伏笔标题。"
    )
    user = (
        f"主线目标：{main_goal}\n"
        f"当前进度：{main_plot.get('progress', 0)}% stage={main_plot.get('stage', 1)}\n"
        f"上次推进回合：{plot_state.get('last_progress_turn', 0)}\n"
        f"当前回合：{turn}\n"
        f"开放伏笔：\n{_hooks_summary(plot_state)}\n\n"
        f"最近剧情：\n{recent or '（无历史）'}\n\n"
        "TASK: 分析最近剧情，输出 JSON。"
    )
    try:
        result = call_deepseek(system, user, skip_validation=True, stream=False)
    except DeepSeekError as exc:
        logger.warning("Plot director LLM analysis failed: %s", exc)
        return None

    if not isinstance(result, dict):
        return None
    return result


def maybe_analyze_plot(
    plot_state: dict,
    session_state: dict,
    memory: dict,
    world_pack: dict,
) -> dict:
    """
    Run LLM analysis when turn hits the interval; return updated plot_state.
    On failure, returns the input state unchanged (except last_analysis_turn skip).
    """
    del memory  # reserved for future context enrichment
    if not config.PLOT_DIRECTOR_ENABLED:
        return plot_state

    turn = int(session_state.get("turn", 0) or 0)
    if turn <= 0 or turn % config.PLOT_DIRECTOR_ANALYSIS_INTERVAL != 0:
        return plot_state

    analysis = analyze_plot_with_llm(plot_state, session_state, world_pack)
    if not analysis:
        return plot_state

    updated = apply_analysis_result(plot_state, analysis, turn)
    summary = str(analysis.get("summary") or "")[:120]
    logger.info(
        "Plot director analyzed turn=%d progress=%s hooks_open=%d summary=%s",
        turn,
        updated.get("main_plot", {}).get("progress"),
        len(updated.get("unresolved_hooks") or []),
        summary,
    )
    return updated


def dashboard_payload(plot_state: dict, session_state: dict, world_pack: dict) -> dict:
    """Serialize plot director data for Dashboard API."""
    turn = int(session_state.get("turn", 0) or 0)
    last_progress = int(plot_state.get("last_progress_turn", 0) or 0)
    stall = max(0, turn - last_progress) if turn > 0 else 0
    world = world_pack.get("world", {}) if isinstance(world_pack, dict) else {}
    main_goal = str(world.get("main_goal") or "").strip()

    return {
        "main_goal": main_goal,
        "main_plot": plot_state.get("main_plot") or {},
        "unresolved_hooks": plot_state.get("unresolved_hooks") or [],
        "resolved_hooks": (plot_state.get("resolved_hooks") or [])[-10:],
        "last_progress_turn": last_progress,
        "last_analysis_turn": int(plot_state.get("last_analysis_turn", 0) or 0),
        "stall_turns": stall,
    }
