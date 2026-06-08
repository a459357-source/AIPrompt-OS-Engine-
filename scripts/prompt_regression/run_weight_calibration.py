#!/usr/bin/env python3
"""Phase 3B: Prompt weight calibration on FAIL scenarios (05/08/09)."""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import config
from engine import io_utils
from engine.plot_director import load_plot_state
from engine.run import get_last_step_error, step

from scripts.prompt_regression.bootstrap import isolated_run, load_scenario
from scripts.prompt_regression.calibration_report import write_calibration_report
from scripts.prompt_regression.choice_policy import pick_choice
from scripts.prompt_regression.goal_missing_analysis import analyze_main_goal_missing
from scripts.prompt_regression.metrics import (
    aggregate_turn_records,
    context_usage_hit,
    count_api_usage_lines,
    detect_brain_conflict,
    event_progress_delta,
    load_api_usage_tail,
    objective_progress_delta,
    relationship_activity_delta,
    relationship_recovery_score,
    snapshot_runtime,
)
from scripts.prompt_regression.weight_groups import (
    CODE_DEFAULTS,
    FAIL_SCENARIOS,
    WEIGHT_GROUPS,
    group_env_json,
)

OUTPUT_DIR = ROOT / "output" / "prompt_regression" / "calibration"
MERGED_3A = ROOT / "output" / "prompt_regression" / "regression_merged_final.json"
CALIB_BASELINE_UNIFIED = {
    "objective_progress_rate": 0.9,
    "brain_consistency_score": 0.99,
}


def _legacy_baselines() -> dict[str, dict]:
    if not MERGED_3A.exists():
        return {}
    data = json.loads(MERGED_3A.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for r in data.get("run_results") or []:
        if r.get("scenario_id") in FAIL_SCENARIOS and r.get("architecture") == "legacy":
            out[r["scenario_id"]] = dict(r.get("aggregate") or {})
    return out


def _scenario_dict(scenario) -> dict:
    return {
        "id": scenario.id,
        "main_goal": scenario.main_goal,
        "world_pack": scenario.world_pack,
    }


def run_group_scenario(scenario, group_id: str, *, turns: int) -> dict:
    os.environ["PROMPTOS_CALIBRATION_WEIGHTS"] = group_env_json(group_id)
    os.environ.pop("PROMPTOS_USE_LEGACY_EXTREME_TEMPLATE", None)
    os.environ["PROMPTOS_SKIP_ADULT_UNLOCK"] = "1"

    suffix = f"calibration/{scenario.id}_group_{group_id}"
    fail: str | None = None
    turn_rows: list[dict] = []

    try:
        with isolated_run(
            scenario, "unified", base_dir=OUTPUT_DIR.parent / "runs", run_suffix=suffix,
        ) as ctx:
            world_chars = scenario.world_pack.get("world", {}).get("characters") or []
            scenario_data = _scenario_dict(scenario)

            for i in range(1, turns + 1):
                session = io_utils.read_yaml(config.SESSION_STATE_PATH)
                memory = io_utils.read_json(config.MEMORY_PATH)
                plot_state = load_plot_state()
                before = snapshot_runtime(session, memory, plot_state)

                cur_turn = int(session.get("turn", 0) or 0)
                hist = session.get("history") or []
                if not hist and cur_turn == 0:
                    choice = None
                    choice_label = "(opening)"
                else:
                    opts = (hist[-1].get("options") or []) if hist else []
                    letter = pick_choice(
                        scenario.seed,
                        cur_turn,
                        opts,
                        prefer_relationship=scenario.prefer_relationship_choice,
                    )
                    choice = letter
                    idx = ord(letter) - ord("A")
                    preview = opts[idx][:80] if idx < len(opts) else letter
                    choice_label = f"{letter}: {preview}"

                usage_before = count_api_usage_lines(config.API_USAGE_PATH)
                t0 = time.time()
                result = step(choice)
                if result is None:
                    result = step(choice)
                elapsed = round(time.time() - t0, 2)

                if result is None:
                    fail = get_last_step_error() or "step returned None"
                    break

                session_after = io_utils.read_yaml(config.SESSION_STATE_PATH)
                memory_after = io_utils.read_json(config.MEMORY_PATH)
                plot_after = load_plot_state()
                after = snapshot_runtime(session_after, memory_after, plot_after)

                story = result.get("story") or ""
                options = result.get("options") or []
                usage = load_api_usage_tail(config.API_USAGE_PATH, usage_before)

                turn_rows.append({
                    "iter": i,
                    "turn": int(result.get("turn", cur_turn)),
                    "choice": choice_label,
                    "story_chars": len(story),
                    "objective_progress": objective_progress_delta(before, after),
                    "event_progress": event_progress_delta(before, after),
                    "relationship_delta": relationship_activity_delta(before, after, options),
                    "brain_conflict": detect_brain_conflict(story, world_chars),
                    "context_usage": context_usage_hit(story, scenario_data, after.get("world_flags")),
                    "latency_sec": elapsed,
                    "prompt_tokens": usage["prompt_tokens"],
                    "completion_tokens": usage["completion_tokens"],
                })
                print(
                    f"[{group_id}/{scenario.id}] {i}/{turns} "
                    f"rel={turn_rows[-1]['relationship_delta']:.3f} "
                    f"obj={turn_rows[-1]['objective_progress']} {elapsed}s"
                )

            agg = aggregate_turn_records(turn_rows, scenario_data)
            out = {
                "group_id": group_id,
                "scenario_id": scenario.id,
                "label": scenario.label,
                "weights": WEIGHT_GROUPS[group_id],
                "turns_ok": len(turn_rows),
                "failure": fail,
                "aggregate": agg,
                "complete": fail is None and len(turn_rows) == turns,
            }
            (ctx.run_dir / "result.json").write_text(
                json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return out
    finally:
        os.environ.pop("PROMPTOS_CALIBRATION_WEIGHTS", None)


def evaluate_calibration(
    group_results: list[dict],
    legacy_baselines: dict[str, dict],
) -> dict:
    rows: list[dict] = []
    by_group: dict[str, list[dict]] = {}

    for r in group_results:
        sid = r["scenario_id"]
        gid = r["group_id"]
        agg = r.get("aggregate") or {}
        legacy_rel = float((legacy_baselines.get(sid) or {}).get("relationship_activity_rate", 0))
        recovery = relationship_recovery_score(
            float(agg.get("relationship_activity_rate", 0)),
            legacy_rel,
        )
        row = {
            "group_id": gid,
            "scenario_id": sid,
            "relationship_activity_rate": agg.get("relationship_activity_rate", 0),
            "objective_progress_rate": agg.get("objective_progress_rate", 0),
            "brain_consistency_score": agg.get("brain_consistency_score", 0),
            "estimated_cost": agg.get("estimated_cost", 0),
            "relationship_recovery_score": recovery,
        }
        rows.append(row)
        by_group.setdefault(gid, []).append(row)

    group_summary: dict[str, dict] = {}
    for gid, items in by_group.items():
        recoveries = [x["relationship_recovery_score"] for x in items]
        min_i = min(items, key=lambda x: x["relationship_recovery_score"])
        costs = [x["estimated_cost"] for x in items]
        objs = [x["objective_progress_rate"] for x in items]
        brains = [x["brain_consistency_score"] for x in items]
        group_summary[gid] = {
            "avg_recovery": round(sum(recoveries) / len(recoveries), 4),
            "min_recovery": min_i["relationship_recovery_score"],
            "min_scenario": min_i["scenario_id"],
            "avg_objective": round(sum(objs) / len(objs), 4),
            "avg_brain": round(sum(brains) / len(brains), 4),
            "avg_cost": round(sum(costs) / len(costs), 4),
        }

    # Phase 3A unified reference cost ~0.0042/scenario from report
    ref_cost = 0.0042
    best_gid = max(
        group_summary.keys(),
        key=lambda g: (
            group_summary[g]["avg_recovery"],
            group_summary[g]["avg_objective"],
            -group_summary[g]["avg_cost"],
        ),
    )
    best = group_summary[best_gid]
    wg = WEIGHT_GROUPS[best_gid]

    checks: list[str] = []
    pass_rel = best["min_recovery"] >= 0.95
    pass_obj = best["avg_objective"] >= CALIB_BASELINE_UNIFIED["objective_progress_rate"] * 0.8
    pass_brain = best["avg_brain"] >= 0.98
    cost_delta = (best["avg_cost"] - ref_cost) / max(ref_cost, 1e-6) * 100
    pass_cost = cost_delta <= 10.0

    checks.append(
        f"Relationship recovery（最低场景）{'✅' if pass_rel else '❌'} {best['min_recovery']} (需≥0.95)"
    )
    checks.append(
        f"Objective 保持 {'✅' if pass_obj else '❌'} {best['avg_objective']} (需≥{CALIB_BASELINE_UNIFIED['objective_progress_rate']*0.8})"
    )
    checks.append(
        f"Brain consistency {'✅' if pass_brain else '❌'} {best['avg_brain']} (需≥0.98)"
    )
    checks.append(
        f"Cost {'✅' if pass_cost else '❌'} +{cost_delta:.1f}% vs 3A unified (需≤10%)"
    )

    verdict = "PASS" if all([pass_rel, pass_obj, pass_brain, pass_cost]) else "FAIL"

    strategy_change = (
        f"建议将 Adult Mode `_DEFAULT_ADULT_WEIGHTS` 更新为 Group {best_gid} "
        f"({wg['world']}/{wg['plot']}/{wg['relationship']})，或通过 settings 暴露可配置权重；"
        "Story Mode 保持 45/35/20。"
        if verdict == "PASS"
        else "暂不改默认常量；优先完成未达标组的根因分析后重测。"
    )

    return {
        "verdict": verdict,
        "checks": checks,
        "group_summary": group_summary,
        "recommended": {
            "group_id": best_gid,
            "label": wg.get("label", ""),
            "world": wg["world"],
            "plot": wg["plot"],
            "relationship": wg["relationship"],
            "reason": (
                f"平均 recovery {best['avg_recovery']}，最低 {best['min_recovery']}；"
                f"objective {best['avg_objective']}；cost {best['avg_cost']} USD"
            ),
            "prompt_strategy_change": strategy_change,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3B weight calibration")
    parser.add_argument("--turns", type=int, default=10)
    parser.add_argument("--group", choices=list(WEIGHT_GROUPS.keys()), default="")
    parser.add_argument("--scenario", default="")
    parser.add_argument("--analyze-only", action="store_true", help="Only main_goal analysis + report from existing results")
    args = parser.parse_args()

    goal_analysis = analyze_main_goal_missing()
    legacy_baselines = _legacy_baselines()

    if args.analyze_only:
        group_results = []
        for p in sorted(OUTPUT_DIR.parent.glob("runs/calibration/*/result.json")):
            group_results.append(json.loads(p.read_text(encoding="utf-8")))
        if not group_results:
            print("[FAIL] no calibration results found")
            return 1
    else:
        config.reload_api_key()
        if not (config.DEEPSEEK_API_KEY or "").strip():
            print("[FAIL] API key missing")
            return 1

        groups = [args.group] if args.group else list(WEIGHT_GROUPS.keys())
        scenarios = [load_scenario(args.scenario)] if args.scenario else [load_scenario(s) for s in FAIL_SCENARIOS]
        group_results = []
        for gid in groups:
            for sc in scenarios:
                print(f"\n=== Group {gid} / {sc.label} ===")
                group_results.append(run_group_scenario(sc, gid, turns=args.turns))

    evaluation = evaluate_calibration(group_results, legacy_baselines)
    flat_rows = []
    for r in group_results:
        agg = r.get("aggregate") or {}
        sid = r["scenario_id"]
        legacy_rel = float((legacy_baselines.get(sid) or {}).get("relationship_activity_rate", 0))
        flat_rows.append({
            "group_id": r["group_id"],
            "scenario_id": sid,
            "relationship_activity_rate": agg.get("relationship_activity_rate", 0),
            "objective_progress_rate": agg.get("objective_progress_rate", 0),
            "brain_consistency_score": agg.get("brain_consistency_score", 0),
            "estimated_cost": agg.get("estimated_cost", 0),
            "relationship_recovery_score": relationship_recovery_score(
                float(agg.get("relationship_activity_rate", 0)), legacy_rel
            ),
        })

    report_data = {
        "phase": "3B",
        "started_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "weight_groups": WEIGHT_GROUPS,
        "code_defaults": CODE_DEFAULTS,
        "legacy_baselines": legacy_baselines,
        "group_results": flat_rows,
        "group_summary": evaluation["group_summary"],
        "main_goal_analysis": goal_analysis,
        "evaluation": evaluation,
        "recommended": evaluation["recommended"],
        "raw_runs": group_results,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = OUTPUT_DIR / f"calibration_{ts}.json"
    json_path.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")

    md_path = ROOT / "docs" / "architecture" / "PROMPT_WEIGHT_CALIBRATION_REPORT.md"
    write_calibration_report(report_data, md_path)
    print(f"\n[json] {json_path}")
    print(f"[report] {md_path}")
    print(f"[verdict] {evaluation['verdict']}")
    print(f"[main_goal] cause={goal_analysis['primary_cause']}")
    return 0 if evaluation["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
