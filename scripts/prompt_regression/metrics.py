"""Regression metrics (pure functions, no API)."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from engine.memory import parse_option_metric_deltas

REL_METRICS = frozenset({
    "trust", "affection", "respect", "dependence", "hostility", "attraction",
})

PRICING = {"deepseek-chat": (0.14, 0.28)}


def snapshot_runtime(session: dict, memory: dict, plot_state: dict) -> dict:
    """Capture comparable state for delta computation."""
    metrics: dict[str, dict[str, float]] = {}
    for name, entry in (memory.get("characters") or {}).items():
        if not isinstance(entry, dict):
            continue
        row: dict[str, float] = {}
        for m in REL_METRICS:
            if m in entry and isinstance(entry[m], (int, float)):
                row[m] = float(entry[m])
        if row:
            metrics[str(name)] = row

    objectives = session.get("objectives") or {}
    main_progress = 0
    for item in objectives.get("main") or []:
        if isinstance(item, dict):
            main_progress = max(main_progress, int(item.get("progress", 0) or 0))
    for item in objectives.get("side") or []:
        if isinstance(item, dict) and str(item.get("status", "")) == "active":
            main_progress = max(main_progress, int(item.get("progress", 0) or 0))

    return {
        "turn": int(session.get("turn", 0) or 0),
        "main_objective_progress": main_progress,
        "objectives_json": copy.deepcopy(objectives),
        "main_plot_progress": int((plot_state.get("main_plot") or {}).get("progress", 0) or 0),
        "unresolved_hooks": len(plot_state.get("unresolved_hooks") or []),
        "world_events_count": len(memory.get("world_events") or []),
        "world_flags": list(memory.get("world_flags") or []),
        "memory_metrics": metrics,
        "force_event_pending": bool(session.get("force_event_pending", False)),
    }


def objective_progress_delta(before: dict, after: dict) -> bool:
    """True if any objective progress increased."""
    if after.get("main_objective_progress", 0) > before.get("main_objective_progress", 0):
        return True
    if after.get("main_plot_progress", 0) > before.get("main_plot_progress", 0):
        return True
    return False


def event_progress_delta(before: dict, after: dict) -> bool:
    if after.get("world_events_count", 0) > before.get("world_events_count", 0):
        return True
    if after.get("unresolved_hooks", 0) > before.get("unresolved_hooks", 0):
        return True
    if after.get("force_event_pending") and not before.get("force_event_pending"):
        return True
    wf_after = set(after.get("world_flags") or [])
    wf_before = set(before.get("world_flags") or [])
    return bool(wf_after - wf_before)


def relationship_activity_delta(before: dict, after: dict, options: list[str]) -> float:
    """Sum of absolute metric changes (memory + parsed option hints)."""
    total = 0.0
    b_metrics = before.get("memory_metrics") or {}
    a_metrics = after.get("memory_metrics") or {}
    names = set(b_metrics) | set(a_metrics)
    for name in names:
        b_row = b_metrics.get(name) or {}
        a_row = a_metrics.get(name) or {}
        for m in REL_METRICS:
            bv = b_row.get(m, a_row.get(m, 0.0))
            av = a_row.get(m, bv)
            total += abs(float(av) - float(bv))

    for _, metric, delta in parse_option_metric_deltas(options or []):
        if metric in REL_METRICS:
            total += abs(float(delta))

    return round(total, 4)


def _world_keywords(scenario: dict) -> list[str]:
    world = scenario.get("world_pack", {}).get("world", scenario.get("world_pack", {}))
    kws: list[str] = []
    for key in ("main_goal", "setting", "title"):
        val = str(world.get(key, "")).strip()
        if len(val) >= 2:
            kws.append(val[:40])
    for loc in world.get("locations") or []:
        if isinstance(loc, dict):
            name = str(loc.get("name", "")).strip()
            if name:
                kws.append(name)
    for ch in world.get("characters") or []:
        if isinstance(ch, dict):
            name = str(ch.get("name", "")).strip()
            if name:
                kws.append(name)
    return kws


def context_usage_hit(story: str, scenario: dict, memory_flags: list[str]) -> bool:
    text = story or ""
    if not text.strip():
        return False
    for kw in _world_keywords({"world_pack": scenario.get("world_pack", scenario)}):
        if kw and kw in text:
            return True
    for flag in memory_flags or []:
        frag = str(flag)[:12]
        if len(frag) >= 2 and frag in text:
            return True
    return False


def detect_brain_conflict(story: str, characters: list[dict]) -> bool:
    """
    Heuristic: story violates NPC taboo/fear keywords.
    Returns True if conflict detected.
    """
    text = story or ""
    if not text.strip():
        return False
    for ch in characters:
        if not isinstance(ch, dict) or ch.get("is_main") or ch.get("isMain"):
            continue
        pers = ch.get("personality") or {}
        taboo = str(pers.get("taboo", "")).strip()
        fear = str(pers.get("fear", "")).strip()
        name = str(ch.get("name", "")).strip()
        if not name or name not in text:
            continue
        for field, label in ((taboo, "taboo"), (fear, "fear")):
            if not field or len(field) < 2:
                continue
            tokens = [t for t in re.split(r"[，,、/\s]+", field) if len(t) >= 2]
            for tok in tokens:
                if tok in text:
                    return True
    return False


def option_repeat_rate(all_options: list[list[str]]) -> float:
    """Average pairwise Jaccard similarity across consecutive turns."""
    if len(all_options) < 2:
        return 0.0

    def norm_set(opts: list[str]) -> set[str]:
        return {re.sub(r"\s+", "", (o or "")[:60]).lower() for o in opts if o}

    sims: list[float] = []
    prev = norm_set(all_options[0])
    for opts in all_options[1:]:
        cur = norm_set(opts)
        if not prev and not cur:
            sims.append(0.0)
        else:
            union = prev | cur
            sims.append(len(prev & cur) / len(union) if union else 0.0)
        prev = cur
    return round(sum(sims) / len(sims), 4) if sims else 0.0


def option_quality_score(all_options: list[list[str]], repeat_rate: float) -> float:
    if not all_options:
        return 1.0
    flat = [o for turn in all_options for o in turn]
    if not flat:
        return 0.0
    bad = sum(1 for o in flat if len((o or "").strip()) < 4)
    bad_rate = bad / len(flat)
    return round(max(0.0, 1.0 - repeat_rate - bad_rate), 4)


def aggregate_turn_records(turns: list[dict], scenario: dict) -> dict:
    """Compute run-level metrics from per-turn records."""
    n = len(turns)
    if n == 0:
        return _empty_aggregate()

    story_lens = [len(t.get("story") or "") for t in turns]
    obj_hits = sum(1 for t in turns if t.get("objective_progress"))
    evt_hits = sum(1 for t in turns if t.get("event_progress"))
    rel_deltas = [float(t.get("relationship_delta") or 0) for t in turns]
    brain_conflicts = sum(1 for t in turns if t.get("brain_conflict"))
    ctx_hits = sum(1 for t in turns if t.get("context_usage"))
    all_options = [t.get("options") or [] for t in turns]

    repeat_rate = option_repeat_rate(all_options)
    latencies = [float(t.get("latency_sec") or 0) for t in turns]
    prompt_toks = [int(t.get("prompt_tokens") or 0) for t in turns]
    comp_toks = [int(t.get("completion_tokens") or 0) for t in turns]

    cost = 0.0
    price_in, price_out = PRICING.get("deepseek-chat", (0.14, 0.28))
    cost = (
        sum(prompt_toks) / 1_000_000 * price_in
        + sum(comp_toks) / 1_000_000 * price_out
    )

    main_goal = str(scenario.get("main_goal", "")).strip()
    goal_absent_streak = 0
    max_goal_absent = 0
    for t in turns:
        story = t.get("story") or ""
        if main_goal and main_goal[:8] not in story and not any(
            kw in story for kw in _world_keywords(scenario)[:3]
        ):
            goal_absent_streak += 1
            max_goal_absent = max(max_goal_absent, goal_absent_streak)
        else:
            goal_absent_streak = 0

    return {
        "turns_ok": n,
        "avg_story_length": round(sum(story_lens) / n, 1),
        "objective_progress_rate": round(obj_hits / n, 4),
        "event_progress_rate": round(evt_hits / n, 4),
        "relationship_activity_rate": round(sum(rel_deltas) / n, 4),
        "brain_consistency_score": round(1.0 - brain_conflicts / n, 4),
        "option_repeat_rate": repeat_rate,
        "option_quality_score": option_quality_score(all_options, repeat_rate),
        "context_usage_score": round(ctx_hits / n, 4),
        "avg_prompt_tokens": round(sum(prompt_toks) / n, 1),
        "avg_completion_tokens": round(sum(comp_toks) / n, 1),
        "avg_latency": round(sum(latencies) / n, 2),
        "estimated_cost": round(cost, 4),
        "brain_conflict_turns": brain_conflicts,
        "max_goal_absent_streak": max_goal_absent,
    }


def _empty_aggregate() -> dict:
    return {
        "turns_ok": 0,
        "avg_story_length": 0.0,
        "objective_progress_rate": 0.0,
        "event_progress_rate": 0.0,
        "relationship_activity_rate": 0.0,
        "brain_consistency_score": 1.0,
        "option_repeat_rate": 0.0,
        "option_quality_score": 0.0,
        "context_usage_score": 0.0,
        "avg_prompt_tokens": 0.0,
        "avg_completion_tokens": 0.0,
        "avg_latency": 0.0,
        "estimated_cost": 0.0,
        "brain_conflict_turns": 0,
        "max_goal_absent_streak": 0,
    }


def compare_architectures(legacy: dict, unified: dict) -> dict:
    """Per-metric delta_pct: unified vs legacy."""
    keys = [
        "avg_story_length",
        "objective_progress_rate",
        "event_progress_rate",
        "relationship_activity_rate",
        "brain_consistency_score",
        "option_quality_score",
        "context_usage_score",
        "avg_prompt_tokens",
        "avg_completion_tokens",
        "estimated_cost",
        "avg_latency",
    ]
    out: dict[str, float] = {}
    for k in keys:
        lv = float(legacy.get(k) or 0)
        uv = float(unified.get(k) or 0)
        denom = max(abs(lv), 1e-6)
        out[k] = round((uv - lv) / denom * 100, 2)
    return out


def evaluate_pass_fail(
    comparisons: list[dict],
    *,
    pass_decline_pct: float = 10.0,
    fail_decline_pct: float = 20.0,
    cost_increase_fail_pct: float = 5.0,
) -> dict:
    """
    Aggregate scenario comparisons into PASS/FAIL.

    comparisons: list of {scenario_id, legacy, unified, delta_pct}
    """
    alerts: list[str] = []
    fail_reasons: list[str] = []

    core_keys = ("objective_progress_rate", "relationship_activity_rate", "brain_consistency_score")
    cost_deltas: list[float] = []
    goal_forget_scenarios = 0

    for row in comparisons:
        sid = row.get("scenario_id", "?")
        delta = row.get("delta_pct") or {}
        legacy = row.get("legacy") or {}
        unified = row.get("unified") or {}

        for k in core_keys:
            d = float(delta.get(k, 0))
            if d < -fail_decline_pct:
                fail_reasons.append(f"{sid}: {k} 下降 {abs(d):.1f}% (>20%)")
            elif d < -pass_decline_pct:
                alerts.append(f"{sid}: {k} 下降 {abs(d):.1f}% (警告阈值 10%)")

        cost_deltas.append(float(delta.get("estimated_cost", 0)))
        if int(unified.get("max_goal_absent_streak", 0) or 0) >= 5:
            goal_forget_scenarios += 1

    avg_cost_delta = sum(cost_deltas) / len(cost_deltas) if cost_deltas else 0.0
    if avg_cost_delta > cost_increase_fail_pct:
        alerts.append(f"Token 成本平均上升 {avg_cost_delta:.1f}%")

    if goal_forget_scenarios >= 2:
        fail_reasons.append(f"{goal_forget_scenarios} 个场景 main_goal 连续 5 回合缺席")

    if fail_reasons:
        verdict = "FAIL"
    elif any("警告" in a or "下降" in a for a in alerts) and avg_cost_delta > cost_increase_fail_pct:
        verdict = "FAIL"
    elif fail_reasons:
        verdict = "FAIL"
    else:
        verdict = "PASS"

    # Strict fail on any >20% core decline
    if fail_reasons:
        verdict = "FAIL"
    elif not fail_reasons:
        verdict = "PASS"

    return {
        "verdict": verdict,
        "alerts": alerts,
        "fail_reasons": fail_reasons,
        "avg_cost_delta_pct": round(avg_cost_delta, 2),
        "goal_forget_scenarios": goal_forget_scenarios,
    }


def load_api_usage_tail(path: Path, after_line: int) -> dict:
    """Read api_usage lines after after_line index; return last entry stats."""
    if not path.exists():
        return {"prompt_tokens": 0, "completion_tokens": 0, "line": after_line}
    lines = path.read_text(encoding="utf-8").splitlines()
    new_lines = lines[after_line:]
    if not new_lines:
        return {"prompt_tokens": 0, "completion_tokens": 0, "line": after_line}
    try:
        entry = json.loads(new_lines[-1])
    except json.JSONDecodeError:
        return {"prompt_tokens": 0, "completion_tokens": 0, "line": len(lines)}
    return {
        "prompt_tokens": int(entry.get("prompt_tokens", 0)),
        "completion_tokens": int(entry.get("completion_tokens", 0)),
        "line": len(lines),
    }


def count_api_usage_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip())


def relationship_recovery_score(
    candidate_rate: float,
    legacy_rate: float,
    *,
    epsilon: float = 1e-6,
) -> float:
    """
    Recovery ratio vs Legacy baseline (Phase 3B).
    1.0 = matched Legacy; >1.0 = exceeded Legacy.
    """
    denom = max(float(legacy_rate), epsilon)
    return round(float(candidate_rate) / denom, 4)


def goal_missing_turn_analysis(story: str, scenario: dict) -> dict:
    """Per-turn breakdown for main_goal missing heuristic (diagnostic only)."""
    main_goal = str(scenario.get("main_goal", "")).strip()
    kws = _world_keywords(scenario)
    prefix_hit = bool(main_goal and main_goal[:8] in (story or ""))
    kw_hits = [kw for kw in kws if kw and kw in (story or "")]
    top3_hit = any(kw in (story or "") for kw in kws[:3])
    flagged = bool(
        main_goal
        and not prefix_hit
        and not top3_hit
    )
    return {
        "main_goal_prefix8": main_goal[:8] if main_goal else "",
        "prefix_hit": prefix_hit,
        "top3_keyword_hit": top3_hit,
        "any_keyword_hits": kw_hits[:5],
        "heuristic_flagged_missing": flagged,
    }
