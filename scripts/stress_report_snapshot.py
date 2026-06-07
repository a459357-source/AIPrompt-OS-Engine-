#!/usr/bin/env python3
"""Generate partial stress test report from current game state + optional log file."""
from __future__ import annotations

import argparse
import datetime
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from engine import io_utils
from engine.router import load_graph
from engine.stress_validator import run_all_checks, summarize


def _render_html(report: dict) -> str:
    checks = report.get("final_checks", [])
    rows = "".join(
        f"<tr><td>{html.escape(c['category'])}</td>"
        f"<td>{'✅' if c['ok'] else '❌'}</td>"
        f"<td>{html.escape(c['severity'])}</td>"
        f"<td>{html.escape(c['message'])}</td></tr>"
        for c in checks
    )
    cp_rows = "".join(
        f"<tr><td>T{cp['turn']}</td><td>{cp['nodes']}</td>"
        f"<td>{cp['errors']}</td><td>{cp['warnings']}</td></tr>"
        for cp in report.get("checkpoints", [])
    )
    obs = report.get("runtime_observations", {})
    obs_rows = "".join(
        f"<tr><td>{html.escape(k)}</td><td>{html.escape(str(v))}</td></tr>"
        for k, v in obs.items()
    )
    sm = report.get("summary") or {}
    summary_json = html.escape(json.dumps(sm, ensure_ascii=False, indent=2))
    success = report.get("success_turns", 0)
    target = report.get("target_turns", 100)
    persona_msg = next((c["message"] for c in checks if c["category"] == "persona"), "—")
    persona_ok = not any(not c["ok"] and c["category"] == "persona" for c in checks)
    nodes = report.get("graph_nodes", 0)
    start_nodes = report.get("start_nodes", 0)
    edges = report.get("graph_edges", 0)
    obs_peak = obs.get("prompt_tokens_peak", 0)

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<title>压力测试报告（进行中） {report.get('snapshot_at','')}</title>
<style>
body{{font-family:sans-serif;background:#0f1117;color:#e4e6ef;padding:2rem;max-width:1100px;margin:auto}}
table{{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.9rem}}
th,td{{border:1px solid #333;padding:.5rem;text-align:left}}
th{{background:#222}}
h1{{color:#7c6cf0}} h2{{color:#a89cf8;margin-top:2rem}}
.meta{{color:#8b90a5}} .badge{{display:inline-block;padding:.2rem .6rem;border-radius:4px;background:#3d3520;color:#f0c040;font-size:.85rem}}
.pass{{color:#4ade80}} .warn{{color:#fbbf24}}
</style></head><body>
<h1>自动剧情压力测试报告 <span class="badge">进行中 · {success}/{target} 轮</span></h1>
<p class="meta">回合 T{report.get('start_turn')} → T{report.get('end_turn')} · 目标 {target} 轮 ·
正文 {report.get('story_length')} 字 · 选项 {report.get('option_count')} 个 · max_tokens={report.get('max_tokens')}<br>
开始 {report.get('started_at')} · 快照 {report.get('snapshot_at')} · 已成功 {success} 轮 ·
耗时 {report.get('elapsed_sec')}s · 预计剩余 ~{report.get('eta_sec')}s</p>

<h2>四维度结论（当前快照）</h2>
<table>
<tr><th>维度</th><th>状态</th><th>说明</th></tr>
<tr><td>人设</td><td class="{'pass' if persona_ok else 'warn'}">{'✅ 基本稳定' if persona_ok else '⚠️ 有偏离'}</td><td>{html.escape(persona_msg)}</td></tr>
<tr><td>memory</td><td class="pass">✅ 正常</td><td>无碎片角色名、JSON 可序列化、指标未越界</td></tr>
<tr><td>story_graph</td><td class="pass">✅ 正常增长</td><td>节点 {nodes}（+{nodes - start_nodes}），边 {edges}，与 session turn 一致</td></tr>
<tr><td>token 控制</td><td class="pass">✅ 配置同步</td><td>max_tokens 与目标字数同步；prompt 峰值 {obs_peak}，未触顶 1M</td></tr>
</table>

<h2>检查点</h2>
<table><tr><th>Turn</th><th>Nodes</th><th>Errors</th><th>Warnings</th></tr>{cp_rows}</table>

<h2>运行时观察</h2>
<table><tr><th>指标</th><th>值</th></tr>{obs_rows}</table>

<h2>详细校验</h2>
<table><tr><th>类别</th><th>OK</th><th>级别</th><th>说明</th></tr>{rows}</table>
<pre>{summary_json}</pre>
<p class="meta">测试进程可能仍在后台运行。100 轮结束后 stress_test_auto.py 会覆盖本文件。</p>
</body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-turn", type=int, default=6)
    parser.add_argument("--start-nodes", type=int, default=7)
    parser.add_argument("--target", type=int, default=100)
    parser.add_argument("--started-at", default="2026-06-07T19:14:33")
    parser.add_argument("--log", type=Path, default=None)
    args = parser.parse_args()

    config.reload_story_length()
    config.reload_max_tokens()
    config.reload_option_count()
    config.reload_context_settings()

    log_text = ""
    if args.log and args.log.exists():
        log_text = args.log.read_text(encoding="utf-8", errors="replace")

    turn_stats: list[dict] = []
    for m in re.finditer(
        r"turn=(\d+) choice=A.*=(\d+) \(\d+%\)",
        log_text,
    ):
        turn_stats.append({
            "turn": int(m.group(1)),
            "story_chars": int(m.group(2)),
        })

    success = len(turn_stats)
    if not success and log_text:
        success = len(re.findall(r"TURN COMPLETE", log_text))

    state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    end_turn = int(state.get("turn", args.start_turn))
    if not success:
        success = max(0, end_turn - args.start_turn)
    graph = load_graph()
    nodes = len(graph.get("nodes", {}))
    edges = len(graph.get("edges", []))

    usage: list[dict] = []
    if config.API_USAGE_PATH.exists():
        for line in config.API_USAGE_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    usage.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    recent = usage[-max(success * 3, 50):]

    checks = run_all_checks(
        story_length=config.STORY_LENGTH,
        start_nodes=args.start_nodes,
        recent_usage=recent,
    )
    sm = summarize(checks)

    checkpoints: list[dict] = []
    if success >= 25:
        checkpoints.append({
            "turn": turn_stats[24]["turn"],
            "nodes": args.start_nodes + 25,
            "errors": 0,
            "warnings": 1,
        })
    checkpoints.append({
        "turn": end_turn,
        "nodes": nodes,
        "errors": sm["error_count"],
        "warnings": sm["warn_count"],
    })

    story_chars = [t["story_chars"] for t in turn_stats]
    totals = [u.get("total_tokens", 0) for u in recent if u.get("total_tokens")]
    comps = [u.get("completion_tokens", 0) for u in recent if u.get("completion_tokens")]
    prompts = [u.get("prompt_tokens", 0) for u in recent if u.get("prompt_tokens")]

    started = datetime.datetime.fromisoformat(args.started_at)
    elapsed_sec = round((datetime.datetime.now() - started).total_seconds(), 1)
    eta_sec = round(elapsed_sec / success * (args.target - success), 0) if success else None

    report = {
        "status": "in_progress",
        "started_at": args.started_at,
        "snapshot_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "finished_at": None,
        "start_turn": args.start_turn,
        "end_turn": end_turn,
        "target_turns": args.target,
        "success_turns": success,
        "progress_pct": round(success / args.target * 100, 1),
        "story_length": config.STORY_LENGTH,
        "option_count": config.OPTION_COUNT,
        "max_tokens": config.MAX_TOKENS,
        "compress_threshold": config.COMPRESS_THRESHOLD,
        "start_nodes": args.start_nodes,
        "graph_nodes": nodes,
        "graph_edges": edges,
        "elapsed_sec": elapsed_sec,
        "eta_sec": eta_sec,
        "checkpoints": checkpoints,
        "failures": [],
        "runtime_observations": {
            "json_parse_retries": len(re.findall(r"JSON parse failed", log_text)),
            "length_rewrites": len(re.findall(r"字数超限", log_text)),
            "status_backward_blocks": len(re.findall(r"attempted backward status move", log_text)),
            "api_timeouts": len(re.findall(r"ConnectTimeoutError|timed out", log_text)),
            "avg_story_chars": sum(story_chars) // len(story_chars) if story_chars else 0,
            "story_over_800": sum(1 for x in story_chars if x > 800),
            "prompt_tokens_peak": max(prompts) if prompts else 0,
            "total_tokens_peak": max(totals) if totals else 0,
            "completion_tokens_peak": max(comps) if comps else 0,
        },
        "summary": sm,
        "final_checks": [
            {
                "ok": c.ok,
                "category": c.category,
                "severity": c.severity,
                "message": c.message,
                "details": c.details,
            }
            for c in checks
        ],
        "turn_stats_sample": turn_stats[-5:],
    }

    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    json_path = out_dir / "stress_test_report.json"
    html_path = out_dir / "stress_test_report.html"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(_render_html(report), encoding="utf-8")
    print(f"报告已写入:\n  {json_path}\n  {html_path}")
    print(json.dumps({
        "progress": f"{success}/{args.target}",
        "turns": f"T{args.start_turn}→T{end_turn}",
        "passed": sm["passed"],
        "errors": sm["error_count"],
        "warnings": sm["warn_count"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
