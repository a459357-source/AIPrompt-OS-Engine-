#!/usr/bin/env python3
"""
stress_test_auto.py — 100~300 回合自动剧情压力测试

用法（在 prompt-os-engine/ 下）:
  python scripts/stress_test_auto.py --turns 100
  python scripts/stress_test_auto.py --turns 200 --checkpoint 25

生成参数（story_length、option_count、max_tokens 等）一律读取当前 apikey.json /
游戏设置，脚本不会覆盖或写死任何配置。

检查项：人设、memory、story_graph、token 控制
报告：output/stress_test_report.json + output/stress_test_report.html
"""
from __future__ import annotations

import argparse
import datetime
import html
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from engine import io_utils
from engine.run import step
from engine.router import load_graph
from engine.stress_validator import run_all_checks, summarize, StressCheckResult


def _read_recent_api_usage(since_turn: int = 0, limit: int = 50) -> list[dict]:
    rows: list[dict] = []
    path = config.API_USAGE_PATH
    if not path.exists():
        return rows
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    rows.append(entry)
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return rows[-limit:]


def _pick_choice(state: dict, letter: str) -> str:
    history = state.get("history", [])
    if not history:
        return letter
    opts = history[-1].get("options") or []
    idx = ord(letter.upper()) - ord("A")
    if 0 <= idx < len(opts):
        return letter.upper()
    return letter.upper()


def _reload_game_settings() -> None:
    """从 apikey.json 重载内存中的生成参数（只读，不写入）。"""
    config.reload_story_length()
    config.reload_max_tokens()
    config.reload_context_settings()
    config.reload_option_count()
    config.ensure_story_length_context_sync()


def _print_game_settings() -> None:
    print(
        f"[settings] story_length={config.STORY_LENGTH} "
        f"max_tokens={config.MAX_TOKENS} compress_threshold={config.COMPRESS_THRESHOLD} "
        f"option_count={config.OPTION_COUNT}"
    )


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
    summary_json = html.escape(json.dumps(report.get("summary") or {}, ensure_ascii=False, indent=2))
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<title>压力测试报告 {report.get('finished_at','')}</title>
<style>
body{{font-family:sans-serif;background:#0f1117;color:#e4e6ef;padding:2rem}}
table{{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.9rem}}
th,td{{border:1px solid #333;padding:.5rem;text-align:left}}
th{{background:#222}}
h1{{color:#7c6cf0}}
.meta{{color:#8b90a5}}
</style></head><body>
<h1>自动剧情压力测试报告</h1>
<p class="meta">回合 {report.get('start_turn')} → {report.get('end_turn')} ·
目标 {report.get('target_turns')} 轮 · 正文 {report.get('story_length')} 字 ·
选项 {report.get('option_count', '?')} 个 ·
成功 {report.get('success_turns')} · 耗时 {report.get('elapsed_sec')}s</p>
<h2>检查点</h2>
<table><tr><th>Turn</th><th>Nodes</th><th>Errors</th><th>Warnings</th></tr>{cp_rows}</table>
<h2>最终校验</h2>
<table><tr><th>类别</th><th>OK</th><th>级别</th><th>说明</th></tr>{rows}</table>
<pre>{summary_json}</pre>
</body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="PromptOS auto story stress test")
    parser.add_argument("--turns", type=int, default=100, help="额外运行回合数 (100~300)")
    parser.add_argument("--choice", default="A", help="每轮自动选择 (默认 A)")
    parser.add_argument("--checkpoint", type=int, default=25, help="每 N 轮校验一次")
    args = parser.parse_args()

    turns = max(1, min(300, args.turns))

    _reload_game_settings()
    story_length = config.STORY_LENGTH
    option_count = config.OPTION_COUNT
    _print_game_settings()

    state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    start_turn = int(state.get("turn", 0))
    start_nodes = len(load_graph().get("nodes", {}))
    start_time = time.time()

    print(f"\n{'='*50}")
    print(f"压力测试开始: 当前 T{start_turn}, 计划 +{turns} 轮, "
          f"正文 {story_length} 字, 选项 {option_count} 个")
    print(f"{'='*50}\n")

    checkpoints: list[dict] = []
    failures: list[dict] = []
    success = 0

    for i in range(1, turns + 1):
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
        cur_turn = int(state.get("turn", 0))
        history = state.get("history", [])

        if not history and cur_turn == 0:
            choice = None
        else:
            choice = _pick_choice(state, args.choice)

        t0 = time.time()
        result = step(choice)
        if result is None:
            result = step(choice)  # 一次重试（选项数/格式偶发失败）
        elapsed = round(time.time() - t0, 1)

        if result is None:
            from engine.run import get_last_step_error
            err = get_last_step_error() or "unknown"
            print(f"[FAIL] 轮次 {i}/{turns} step 失败: {err}")
            failures.append({"iteration": i, "turn": cur_turn, "error": err})
            break

        success += 1
        new_turn = result.get("state", {}).get("turn", cur_turn)
        story_len = len(result.get("story", ""))
        nodes = len(load_graph().get("nodes", {}))
        print(
            f"[OK] {i}/{turns} T{new_turn} story={story_len}chars "
            f"nodes={nodes} api={elapsed}s"
        )

        if i % args.checkpoint == 0 or i == turns:
            usage = _read_recent_api_usage(limit=args.checkpoint * 2)
            checks = run_all_checks(
                story_length=story_length,
                start_nodes=start_nodes,
                recent_usage=usage,
            )
            sm = summarize(checks)
            checkpoints.append({
                "turn": new_turn,
                "nodes": nodes,
                "errors": sm["error_count"],
                "warnings": sm["warn_count"],
            })
            print(f"  [checkpoint] errors={sm['error_count']} warnings={sm['warn_count']}")

    end_state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    end_turn = int(end_state.get("turn", 0))
    usage = _read_recent_api_usage(limit=turns + 10)
    final_checks = run_all_checks(
        story_length=story_length,
        start_nodes=start_nodes,
        recent_usage=usage,
    )
    summary = summarize(final_checks)

    report = {
        "started_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "finished_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "start_turn": start_turn,
        "end_turn": end_turn,
        "target_turns": turns,
        "success_turns": success,
        "story_length": story_length,
        "option_count": option_count,
        "elapsed_sec": round(time.time() - start_time, 1),
        "checkpoints": checkpoints,
        "failures": failures,
        "summary": summary,
        "final_checks": [
            {
                "ok": c.ok,
                "category": c.category,
                "severity": c.severity,
                "message": c.message,
                "details": c.details,
            }
            for c in final_checks
        ],
    }

    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    json_path = out_dir / "stress_test_report.json"
    html_path = out_dir / "stress_test_report.html"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(_render_html(report), encoding="utf-8")

    print(f"\n{'='*50}")
    print(f"完成: {success}/{turns} 轮 | T{start_turn}→T{end_turn}")
    print(f"校验: errors={summary['error_count']} warnings={summary['warn_count']}")
    print(f"报告: {json_path}")
    print(f"      {html_path}")
    print(f"{'='*50}\n")

    return 0 if summary["passed"] and success == turns else 1


if __name__ == "__main__":
    raise SystemExit(main())
