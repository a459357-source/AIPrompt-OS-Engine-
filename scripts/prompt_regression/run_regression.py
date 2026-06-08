#!/usr/bin/env python3
"""Phase 3A: Prompt Unified vs Legacy Extreme regression runner."""
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

from scripts.prompt_regression.bootstrap import (
    IsolatedRun,
    Scenario,
    isolated_run,
    load_all_scenarios,
    load_scenario,
)
from scripts.prompt_regression.choice_policy import pick_choice
from scripts.prompt_regression.metrics import (
    aggregate_turn_records,
    compare_architectures,
    context_usage_hit,
    count_api_usage_lines,
    detect_brain_conflict,
    evaluate_pass_fail,
    event_progress_delta,
    load_api_usage_tail,
    objective_progress_delta,
    relationship_activity_delta,
    snapshot_runtime,
)
from scripts.prompt_regression.report_generator import write_report

OUTPUT_DIR = ROOT / "output" / "prompt_regression"
ARCHITECTURES = ("legacy", "unified")


def _scenario_dict(scenario: Scenario) -> dict:
    return {
        "id": scenario.id,
        "category": scenario.category,
        "label": scenario.label,
        "seed": scenario.seed,
        "main_goal": scenario.main_goal,
        "world_pack": scenario.world_pack,
    }


def _checkpoint_path(run: IsolatedRun) -> Path:
    return run.run_dir / "checkpoint.json"


def _load_checkpoint(run: IsolatedRun) -> dict | None:
    path = _checkpoint_path(run)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _save_checkpoint(run: IsolatedRun, data: dict) -> None:
    run.run_dir.mkdir(parents=True, exist_ok=True)
    _checkpoint_path(run).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_scenario_arch(
    scenario: Scenario,
    architecture: str,
    *,
    turns: int,
    resume: bool,
    dry_run: bool,
) -> dict:
    with isolated_run(scenario, architecture) as ctx:
        checkpoint = _load_checkpoint(ctx) if resume else None
        start_iter = 1
        turn_rows: list[dict] = []

        if checkpoint and checkpoint.get("complete"):
            if int(checkpoint.get("turns_requested", 0)) == turns:
                return checkpoint

        if checkpoint and checkpoint.get("turns") and int(checkpoint.get("turns_requested", 0)) == turns:
            turn_rows = list(checkpoint["turns"])
            start_iter = len(turn_rows) + 1
            if start_iter > turns:
                return checkpoint

        if dry_run:
            scenario_data = _scenario_dict(scenario)
            return {
                "scenario_id": scenario.id,
                "category": scenario.category,
                "label": scenario.label,
                "architecture": architecture,
                "dry_run": True,
                "turns_ok": 0,
                "turns": [],
                "aggregate": aggregate_turn_records([], scenario_data),
                "complete": True,
            }

        world_chars = scenario.world_pack.get("world", {}).get("characters") or []
        scenario_data = _scenario_dict(scenario)
        fail: str | None = None

        for i in range(start_iter, turns + 1):
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

            row = {
                "iter": i,
                "turn": int(result.get("turn", cur_turn)),
                "choice": choice_label,
                "story": story,
                "story_preview": story[:240].replace("\n", " "),
                "story_chars": len(story),
                "options": options,
                "latency_sec": elapsed,
                "prompt_tokens": usage["prompt_tokens"],
                "completion_tokens": usage["completion_tokens"],
                "objective_progress": objective_progress_delta(before, after),
                "event_progress": event_progress_delta(before, after),
                "relationship_delta": relationship_activity_delta(before, after, options),
                "brain_conflict": detect_brain_conflict(story, world_chars),
                "context_usage": context_usage_hit(story, scenario_data, after.get("world_flags")),
            }
            turn_rows.append(row)
            _save_checkpoint(ctx, {
                "scenario_id": scenario.id,
                "architecture": architecture,
                "turns_requested": turns,
                "turns": turn_rows,
                "complete": False,
            })
            print(
                f"[{scenario.id}/{architecture}] {i}/{turns} T{row['turn']} "
                f"story={row['story_chars']} obj={row['objective_progress']} "
                f"rel={row['relationship_delta']:.3f} {elapsed}s"
            )

        agg = aggregate_turn_records(turn_rows, scenario_data)
        out = {
            "scenario_id": scenario.id,
            "category": scenario.category,
            "label": scenario.label,
            "architecture": architecture,
            "turns_requested": turns,
            "turns_ok": len(turn_rows),
            "failure": fail,
            "turns": turn_rows,
            "aggregate": agg,
            "complete": fail is None and len(turn_rows) == turns,
        }
        _save_checkpoint(ctx, out)
        return out


def build_full_report(
    run_results: list[dict],
    *,
    turns: int,
    started_at: str,
    finished_at: str,
) -> dict:
    by_key: dict[tuple[str, str], dict] = {}
    for r in run_results:
        by_key[(r["scenario_id"], r["architecture"])] = r

    scenario_ids = sorted({r["scenario_id"] for r in run_results})
    comparisons: list[dict] = []
    for sid in scenario_ids:
        legacy = (by_key.get((sid, "legacy")) or {}).get("aggregate") or {}
        unified = (by_key.get((sid, "unified")) or {}).get("aggregate") or {}
        comparisons.append({
            "scenario_id": sid,
            "category": (by_key.get((sid, "legacy")) or by_key.get((sid, "unified")) or {}).get("category"),
            "label": (by_key.get((sid, "legacy")) or by_key.get((sid, "unified")) or {}).get("label"),
            "legacy": legacy,
            "unified": unified,
            "delta_pct": compare_architectures(legacy, unified),
        })

    def _sum_agg(arch: str, key: str) -> float:
        vals = [
            float((by_key.get((sid, arch)) or {}).get("aggregate", {}).get(key, 0) or 0)
            for sid in scenario_ids
            if (by_key.get((sid, arch)) or {}).get("turns_ok", 0) > 0
        ]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    summary_legacy = {k: _sum_agg("legacy", k) for k in (
        "avg_story_length", "objective_progress_rate", "relationship_activity_rate",
        "brain_consistency_score", "context_usage_score", "estimated_cost",
        "avg_prompt_tokens", "avg_completion_tokens", "avg_latency",
    )}
    summary_unified = {k: _sum_agg("unified", k) for k in summary_legacy}

    evaluation = evaluate_pass_fail(comparisons)

    successes: list[dict] = []
    failures: list[dict] = []
    for c in comparisons:
        d = c["delta_pct"]
        if d.get("objective_progress_rate", 0) >= -5 and d.get("relationship_activity_rate", 0) >= -5:
            successes.append(c)
        elif d.get("objective_progress_rate", 0) < -10 or d.get("relationship_activity_rate", 0) < -10:
            failures.append(c)

    return {
        "phase": "3A",
        "started_at": started_at,
        "finished_at": finished_at,
        "model": "deepseek-chat",
        "turns_per_scenario": turns,
        "architectures": list(ARCHITECTURES),
        "scenario_count": len(scenario_ids),
        "run_results": run_results,
        "comparisons": comparisons,
        "summary_legacy": summary_legacy,
        "summary_unified": summary_unified,
        "summary_delta_pct": compare_architectures(summary_legacy, summary_unified),
        "evaluation": evaluation,
        "case_studies": {
            "successes": successes[:3],
            "failures": failures[:3],
        },
        "notes": [
            "Story Mode vs Adult Mode 权重对比未在本阶段执行（全部 extreme adult 设置）。",
            "brain/context 分数为启发式自动化指标，建议人工复核 story 原文。",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3A Prompt Unified regression")
    parser.add_argument("--turns", type=int, default=10, help="Turns per scenario per architecture")
    parser.add_argument("--scenario", type=str, default="", help="Run single scenario id")
    parser.add_argument("--arch", choices=["legacy", "unified", "both"], default="both")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--dry-run", action="store_true", help="Bootstrap only, no API")
    parser.add_argument("--fresh", action="store_true", help="Remove prior run checkpoints under output/prompt_regression/runs")
    parser.add_argument("--report-only", type=str, default="", help="Regenerate MD from JSON path")
    args = parser.parse_args()

    # Regression harness: adult extreme scenarios (config test bypass, scripts only)
    os.environ["PROMPTOS_SKIP_ADULT_UNLOCK"] = "1"

    if args.report_only:
        data = json.loads(Path(args.report_only).read_text(encoding="utf-8"))
        md_path = ROOT / "docs" / "architecture" / "PROMPT_UNIFIED_REGRESSION_REPORT.md"
        write_report(data, md_path)
        print(f"[report] {md_path}")
        return 0

    if args.fresh:
        import shutil
        runs_root = OUTPUT_DIR / "runs"
        if runs_root.exists():
            shutil.rmtree(runs_root)
            print(f"[fresh] removed {runs_root}")

    if not args.dry_run:
        config.reload_api_key()
        if not (config.DEEPSEEK_API_KEY or "").strip():
            print("[FAIL] DEEPSEEK_API_KEY / data/apikey.json 未配置，无法运行真实 API 回归")
            return 1

    scenarios = [load_scenario(args.scenario)] if args.scenario else load_all_scenarios()
    archs = list(ARCHITECTURES) if args.arch == "both" else [args.arch]

    started_at = datetime.datetime.now().isoformat(timespec="seconds")
    run_results: list[dict] = []

    for scenario in scenarios:
        for arch in archs:
            print(f"\n=== {scenario.label} ({scenario.id}) / {arch} ===")
            result = run_scenario_arch(
                scenario,
                arch,
                turns=args.turns,
                resume=args.resume,
                dry_run=args.dry_run,
            )
            run_results.append(result)

    finished_at = datetime.datetime.now().isoformat(timespec="seconds")
    report = build_full_report(run_results, turns=args.turns, started_at=started_at, finished_at=finished_at)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = OUTPUT_DIR / f"regression_{ts}.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[json] {json_path}")

    md_path = ROOT / "docs" / "architecture" / "PROMPT_UNIFIED_REGRESSION_REPORT.md"
    write_report(report, md_path)
    print(f"[report] {md_path}")
    print(f"[verdict] {report['evaluation']['verdict']}")

    failed_runs = [r for r in run_results if r.get("failure") or not r.get("complete", True)]
    return 0 if not failed_runs and report["evaluation"]["verdict"] == "PASS" else (
        1 if failed_runs else (0 if report["evaluation"]["verdict"] == "PASS" else 1)
    )


if __name__ == "__main__":
    raise SystemExit(main())
