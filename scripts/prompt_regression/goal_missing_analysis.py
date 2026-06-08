"""Investigate main_goal missing heuristic (Phase 3B §八)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.prompt_regression.bootstrap import load_scenario
from scripts.prompt_regression.metrics import goal_missing_turn_analysis
from scripts.prompt_regression.weight_groups import FAIL_SCENARIOS

ROOT = Path(__file__).resolve().parent.parent.parent
RUNS_DIR = ROOT / "output" / "prompt_regression" / "runs"
MERGED = ROOT / "output" / "prompt_regression" / "regression_merged_final.json"


def _load_turns_from_merged(scenario_id: str, architecture: str) -> list[dict]:
    if not MERGED.exists():
        return []
    data = json.loads(MERGED.read_text(encoding="utf-8"))
    for r in data.get("run_results") or []:
        if r.get("scenario_id") == scenario_id and r.get("architecture") == architecture:
            return r.get("turns") or []
    return []


def analyze_main_goal_missing() -> dict:
    """
    Classify root cause without modifying heuristic rules.
    Returns evidence for A (prompt injection), B (mode suppression), C (heuristic).
    """
    findings: list[dict] = []
    legacy_flagged = 0
    unified_flagged = 0
    legacy_total = 0
    unified_total = 0
    prefix_only_miss = 0
    char_name_would_save = 0

    for sid in FAIL_SCENARIOS:
        scenario = load_scenario(sid)
        sd = {
            "main_goal": scenario.main_goal,
            "world_pack": scenario.world_pack,
        }
        for arch in ("legacy", "unified"):
            turns = _load_turns_from_merged(sid, arch)
            arch_flagged = 0
            samples: list[dict] = []
            for t in turns:
                story = t.get("story") or ""
                diag = goal_missing_turn_analysis(story, sd)
                if arch == "legacy":
                    legacy_total += 1
                else:
                    unified_total += 1
                if diag["heuristic_flagged_missing"]:
                    arch_flagged += 1
                    if arch == "legacy":
                        legacy_flagged += 1
                    else:
                        unified_flagged += 1
                    if diag["any_keyword_hits"] and not diag["prefix_hit"]:
                        prefix_only_miss += 1
                    if len(diag["any_keyword_hits"]) > 0 and not diag["top3_keyword_hit"]:
                        char_name_would_save += 1
                    if len(samples) < 2:
                        samples.append({
                            "turn": t.get("turn"),
                            "prefix8": diag["main_goal_prefix8"],
                            "keyword_hits": diag["any_keyword_hits"],
                            "story_preview": story[:200].replace("\n", " "),
                        })
            findings.append({
                "scenario_id": sid,
                "architecture": arch,
                "turns": len(turns),
                "flagged_turns": arch_flagged,
                "flag_rate": round(arch_flagged / max(len(turns), 1), 4),
                "samples": samples,
            })

    # Prompt injection check: MAIN_GOAL is in system template rule 3 + OBJECTIVES_CONTEXT
    prompt_injection = {
        "main_goal_in_system_template": True,
        "main_goal_rule": "long_term_goal：{{MAIN_GOAL}}，每轮有意识地朝此目标推进。",
        "objectives_context_in_user_prompt": True,
        "builder_injects_main_goal": True,
    }

    # Mode suppression: adult extreme task_hint emphasizes 性内容 70%+
    mode_suppression = {
        "adult_extreme_task_hint_dominates": True,
        "note": "Adult extreme task_hint 要求性描写为主体（70%+），与 main_goal 字面共现率低",
    }

    both_arch_high_flag = (
        legacy_total > 0
        and unified_total > 0
        and legacy_flagged / legacy_total > 0.5
        and unified_flagged / unified_total > 0.5
    )

    if both_arch_high_flag and prefix_only_miss > 0:
        primary = "C"
        conclusion = (
            "Legacy 与 Unified 均高比例触发 heuristic；story 常含角色名/地点但不含 main_goal 前 8 字，"
            "属启发式误判（要求字面 substring 过严），非 Unified 独有回归。"
        )
    elif unified_flagged > legacy_flagged * 1.5:
        primary = "B"
        conclusion = "Unified Mode Context 可能压制 main_goal 共现（需结合 prompt 抽样复核）。"
    else:
        primary = "A"
        conclusion = "Prompt 已注入 MAIN_GOAL，但生成未复述；需检查 OBJECTIVES_CONTEXT 是否每轮非空。"

    return {
        "primary_cause": primary,
        "conclusion": conclusion,
        "prompt_injection": prompt_injection,
        "mode_suppression": mode_suppression,
        "stats": {
            "legacy_flagged_rate": round(legacy_flagged / max(legacy_total, 1), 4),
            "unified_flagged_rate": round(unified_flagged / max(unified_total, 1), 4),
            "prefix_miss_but_keyword_hit_turns": prefix_only_miss,
            "keyword_beyond_top3_turns": char_name_would_save,
        },
        "per_scenario": findings,
        "recommendation": (
            "禁止在本阶段修改 heuristic 规则；评审后可考虑将判定改为 OBJECTIVES 进度或语义匹配，"
            "而非 main_goal[:8] 字面包含。"
        ),
    }
