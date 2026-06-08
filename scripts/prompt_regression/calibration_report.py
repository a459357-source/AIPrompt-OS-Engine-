"""Generate PROMPT_WEIGHT_CALIBRATION_REPORT.md."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def write_calibration_report(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ev = data.get("evaluation") or {}
    verdict = ev.get("verdict", "UNKNOWN")
    goal = data.get("main_goal_analysis") or {}
    groups = data.get("group_results") or []
    legacy = data.get("legacy_baselines") or {}
    rec = data.get("recommended") or {}

    lines = [
        "# PROMPT_WEIGHT_CALIBRATION_REPORT",
        "",
        "Phase 3B — Prompt Weight Calibration（V4.1）",
        "",
        f"**校准结论：{verdict}**",
        "",
        "## 1. 背景",
        "",
        "Phase 3A 判定 **Architecture PASS / Weight Calibration FAIL**。",
        "本阶段仅在 Unified Prompt 上校准 Mode Context 权重（World / Plot / Relationship），禁止回滚双 Prompt。",
        "",
        f"| 代码 Story 默认 | world {data.get('code_defaults', {}).get('story', {}).get('world')}% / plot {data.get('code_defaults', {}).get('story', {}).get('plot')}% / rel {data.get('code_defaults', {}).get('story', {}).get('relationship')}% |",
        f"| 代码 Adult 默认 | world {data.get('code_defaults', {}).get('adult', {}).get('world')}% / plot {data.get('code_defaults', {}).get('adult', {}).get('plot')}% / rel {data.get('code_defaults', {}).get('adult', {}).get('relationship')}% |",
        "",
        "## 2. 实验组（A–D）",
        "",
        "| 组 | World | Plot | Relationship | 说明 |",
        "|---|---:|---:|---:|---|",
    ]
    for gid, g in (data.get("weight_groups") or {}).items():
        lines.append(
            f"| {gid} | {g['world']}% | {g['plot']}% | {g['relationship']}% | {g.get('label', '')} |"
        )

    lines.extend([
        "",
        "## 3. Legacy 基线（Phase 3A，05/08/09）",
        "",
        "| 场景 | relationship_activity_rate | objective_progress_rate |",
        "|---|---:|---:|",
    ])
    for sid, b in legacy.items():
        lines.append(
            f"| {sid} | {b.get('relationship_activity_rate', 0)} | {b.get('objective_progress_rate', 0)} |"
        )

    lines.extend([
        "",
        "## 4. 四组权重结果",
        "",
        "| 组 | 场景 | rel_rate | obj_rate | brain | recovery | cost USD |",
        "|---|---|---:|---:|---:|---:|---:|",
    ])
    for row in groups:
        lines.append(
            f"| {row.get('group_id')} | {row.get('scenario_id')} | "
            f"{row.get('relationship_activity_rate', 0)} | {row.get('objective_progress_rate', 0)} | "
            f"{row.get('brain_consistency_score', 0)} | {row.get('relationship_recovery_score', 0)} | "
            f"{row.get('estimated_cost', 0)} |"
        )

    lines.extend([
        "",
        "## 5. Relationship Recovery Score（相对 Legacy）",
        "",
        "目标：≥ 0.95（恢复至 Legacy 的 95% 以上）",
        "",
        "| 组 | 平均 recovery | 最低场景 |",
        "|---|---:|---|",
    ])
    for gid, agg in (data.get("group_summary") or {}).items():
        lines.append(
            f"| {gid} | {agg.get('avg_recovery', 0)} | {agg.get('min_scenario', '—')} ({agg.get('min_recovery', 0)}) |"
        )

    lines.extend([
        "",
        "## 6. Main Goal 缺失原因分析",
        "",
        f"**主因分类：{goal.get('primary_cause', '?')}**",
        "",
        goal.get("conclusion", ""),
        "",
        f"- Legacy 触发率：{goal.get('stats', {}).get('legacy_flagged_rate', 0)}",
        f"- Unified 触发率：{goal.get('stats', {}).get('unified_flagged_rate', 0)}",
        f"- 含关键词但不含 main_goal 前 8 字：{goal.get('stats', {}).get('prefix_miss_but_keyword_hit_turns', 0)} 回合",
        "",
        goal.get("recommendation", ""),
        "",
        "## 7. 推荐权重",
        "",
        f"**推荐组：{rec.get('group_id', '—')}** — {rec.get('label', '')}",
        "",
        f"- World {rec.get('world', '?')}% / Plot {rec.get('plot', '?')}% / Relationship {rec.get('relationship', '?')}%",
        f"- 理由：{rec.get('reason', '')}",
        "",
        "## 8. 是否修改 PromptStrategy",
        "",
        rec.get("prompt_strategy_change", ""),
        "",
        "## 9. 通过条件核对",
        "",
    ])
    for check in ev.get("checks") or []:
        lines.append(f"- {check}")
    lines.extend([
        "",
        "## 10. Phase 3B 后建议",
        "",
    ])
    if verdict == "PASS":
        lines.append("校准通过，可提交 V4.1 评审；通过后允许继续 Shared System 开发。")
    else:
        lines.append("校准未通过，**禁止**进入 V5.1 / V6.0 / V6.5；须调整权重或 PromptStrategy 后重测。")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
