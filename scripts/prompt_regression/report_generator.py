"""Generate PROMPT_UNIFIED_REGRESSION_REPORT.md from regression JSON."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _pct(v: float) -> str:
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.1f}%"


def _row_metric(label: str, legacy: float, unified: float, delta: float) -> str:
    return f"| {label} | {legacy} | {unified} | {_pct(delta)} |"


def write_report(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ev = data.get("evaluation") or {}
    verdict = ev.get("verdict", "UNKNOWN")
    sl = data.get("summary_legacy") or {}
    su = data.get("summary_unified") or {}
    sd = data.get("summary_delta_pct") or {}

    lines: list[str] = [
        "# PROMPT_UNIFIED_REGRESSION_REPORT",
        "",
        "Phase 3A — Prompt Unified Architecture 回归分析",
        "",
        f"**最终结论：{verdict}**",
        "",
        "## 1. 测试配置",
        "",
        f"| 项 | 值 |",
        f"|---|---|",
        f"| 开始时间 | {data.get('started_at', '—')} |",
        f"| 结束时间 | {data.get('finished_at', '—')} |",
        f"| 模型 | {data.get('model', 'deepseek-chat')} |",
        f"| 每场景回合 | {data.get('turns_per_scenario', 10)} |",
        f"| 场景数 | {data.get('scenario_count', 0)} |",
        f"| 架构对比 | Legacy Extreme (`PROMPTOS_USE_LEGACY_EXTREME_TEMPLATE=1`) vs Unified |",
        f"| API | 真实 DeepSeek（无 Mock/Replay） |",
        "",
        "## 2. 测试场景",
        "",
        "| ID | 类别 | 标签 |",
        "|---|---|---|",
    ]

    for c in data.get("comparisons") or []:
        lines.append(f"| {c.get('scenario_id')} | {c.get('category')} | {c.get('label')} |")

    lines.extend([
        "",
        "## 3. 汇总统计（Legacy vs Unified）",
        "",
        "| 指标 | Legacy | Unified | 变化 |",
        "|---|---:|---:|---:|",
        _row_metric("avg_story_length", sl.get("avg_story_length", 0), su.get("avg_story_length", 0), sd.get("avg_story_length", 0)),
        _row_metric("objective_progress_rate", sl.get("objective_progress_rate", 0), su.get("objective_progress_rate", 0), sd.get("objective_progress_rate", 0)),
        _row_metric("relationship_activity_rate", sl.get("relationship_activity_rate", 0), su.get("relationship_activity_rate", 0), sd.get("relationship_activity_rate", 0)),
        _row_metric("brain_consistency_score", sl.get("brain_consistency_score", 0), su.get("brain_consistency_score", 0), sd.get("brain_consistency_score", 0)),
        _row_metric("context_usage_score", sl.get("context_usage_score", 0), su.get("context_usage_score", 0), sd.get("context_usage_score", 0)),
        _row_metric("avg_prompt_tokens", sl.get("avg_prompt_tokens", 0), su.get("avg_prompt_tokens", 0), sd.get("avg_prompt_tokens", 0)),
        _row_metric("avg_completion_tokens", sl.get("avg_completion_tokens", 0), su.get("avg_completion_tokens", 0), sd.get("avg_completion_tokens", 0)),
        _row_metric("estimated_cost (USD)", sl.get("estimated_cost", 0), su.get("estimated_cost", 0), sd.get("estimated_cost", 0)),
        _row_metric("avg_latency (s)", sl.get("avg_latency", 0), su.get("avg_latency", 0), sd.get("avg_latency", 0)),
        "",
        "## 4. 分类汇总",
        "",
    ])

    by_cat: dict[str, list] = {}
    for c in data.get("comparisons") or []:
        by_cat.setdefault(str(c.get("category", "?")), []).append(c)

    for cat, rows in sorted(by_cat.items()):
        lines.append(f"### 类别 {cat}")
        lines.append("")
        lines.append("| 场景 | objective Δ | relationship Δ | brain Δ |")
        lines.append("|---|---:|---:|---:|")
        for r in rows:
            d = r.get("delta_pct") or {}
            lines.append(
                f"| {r.get('label')} | {_pct(d.get('objective_progress_rate', 0))} | "
                f"{_pct(d.get('relationship_activity_rate', 0))} | "
                f"{_pct(d.get('brain_consistency_score', 0))} |"
            )
        lines.append("")

    lines.extend([
        "## 5. Token / 成本 / 延迟",
        "",
        f"- Legacy 总估算成本（均值×场景）：约 ${sl.get('estimated_cost', 0):.4f}/场景",
        f"- Unified 总估算成本（均值×场景）：约 ${su.get('estimated_cost', 0):.4f}/场景",
        f"- 成本变化：{_pct(sd.get('estimated_cost', 0))}",
        "",
        "## 6. 失败案例",
        "",
    ])

    fail_cases = (data.get("case_studies") or {}).get("failures") or []
    if fail_cases:
        for fc in fail_cases:
            lines.append(f"### {fc.get('label')} ({fc.get('scenario_id')})")
            d = fc.get("delta_pct") or {}
            lines.append(f"- objective_progress_rate: {_pct(d.get('objective_progress_rate', 0))}")
            lines.append(f"- relationship_activity_rate: {_pct(d.get('relationship_activity_rate', 0))}")
            lines.append("")
    else:
        lines.append("（无显著退化场景）")
        lines.append("")

    lines.extend([
        "## 7. 成功案例",
        "",
    ])
    ok_cases = (data.get("case_studies") or {}).get("successes") or []
    if ok_cases:
        for oc in ok_cases:
            lines.append(f"- **{oc.get('label')}**：Unified 在 objective/relationship 上持平或提升")
    else:
        lines.append("（见逐场景表）")
    lines.append("")

    lines.extend([
        "## 8. 回归报警",
        "",
    ])
    for alert in ev.get("alerts") or []:
        lines.append(f"- ⚠ {alert}")
    for reason in ev.get("fail_reasons") or []:
        lines.append(f"- ❌ {reason}")
    if not ev.get("alerts") and not ev.get("fail_reasons"):
        lines.append("- 无")
    lines.append("")

    lines.extend([
        "## 9. 范围说明",
        "",
    ])
    for note in data.get("notes") or []:
        lines.append(f"- {note}")
    lines.append("")

    lines.extend([
        "## 10. Phase 3B 入口建议",
        "",
    ])
    if verdict == "PASS":
        lines.append("回归通过，可提交 Phase 3A 评审；评审通过后允许进入 V5.1 Relationship Dynamics。")
    else:
        lines.append("回归未通过，**禁止**进入 V5.1 / V6.0 Visual / V6.5 Experience UI；须修复 Prompt Unified 后再测。")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
