#!/usr/bin/env python3
"""Run 10 turns with adult settings maxed and score story/options intimacy."""
from __future__ import annotations

import datetime
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from engine import io_utils
from engine.builder import build_prompt
from engine.run import get_last_step_error, step

INTIMATE = (
    "吻", "亲", "摸", "抱", "脱", "床", "做", "爱", "性", "裸", "胸", "腿", "腰", "唇", "舌",
    "进入", "插入", "高潮", "情欲", "诱惑", "撩", "色", "欲", "肉体", "抚摸", "解开", "按在",
    "扑倒", "缠绵", "欢爱", "做爱", "上床", "侵犯", "占有", "呻吟", "喘息", "乳头",
    "内裤", "胸罩", "湿润", "硬", "顶", "抽插", "骑", "口交", "舔",
)
VAGUE = ("更进一步", "暗示", "暧昧", "试探", "靠近", "心动", "脸红", "心跳", "目光")


def score_text(text: str) -> tuple[int, list[str], list[str]]:
    t = text or ""
    hits = [k for k in INTIMATE if k in t]
    vague = [k for k in VAGUE if k in t]
    return len(hits), hits[:8], vague


def pick_adult_option(options: list[str]) -> str:
    best_i, best_s = 0, -1
    for i, opt in enumerate(options):
        s, _, _ = score_text(opt)
        if s > best_s:
            best_s, best_i = s, i
    return chr(65 + best_i) if options else "A"


def main() -> int:
    config.save_adult_mode(True)
    config.save_adult_profile("adult_first")
    config.save_content_weights({"story": 0, "romance": 0, "adult": 100})
    config.save_expression_style("direct")
    config.reload_app_behavior()

    rules = config.content_preference_rules_text()
    if not config.ADULT_MODE or "成人模式" not in rules:
        print("[FAIL] adult_mode not active in prompt rules")
        return 1
    build_prompt("A")
    print("[setup] adult_mode=True profile=adult_first weights=100% expression=direct")

    state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    start_turn = int(state.get("turn", 0))
    print(f"[start] turn={start_turn} history={len(state.get('history', []))}")

    rows: list[dict] = []
    fail: str | None = None

    for i in range(1, 11):
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
        cur = int(state.get("turn", 0))
        hist = state.get("history", [])

        if not hist and cur == 0:
            choice = None
            choice_label = "(opening)"
        else:
            opts = (hist[-1].get("options") or []) if hist else []
            letter = pick_adult_option(opts)
            choice = letter
            idx = ord(letter) - 65
            preview = opts[idx][:80] + "..." if idx < len(opts) and len(opts[idx]) > 80 else (opts[idx] if idx < len(opts) else letter)
            choice_label = f"{letter}: {preview}"

        t0 = time.time()
        result = step(choice)
        if result is None:
            result = step(choice)
        elapsed = round(time.time() - t0, 1)

        if result is None:
            fail = get_last_step_error() or "unknown"
            print(f"[FAIL] iter {i} turn {cur}: {fail}")
            break

        story = result.get("story", "")
        options = result.get("options") or []
        new_turn = result.get("state", {}).get("turn", cur)
        sh, sh_kw, sv = score_text(story)
        opt_scores = []
        for j, opt in enumerate(options):
            sc, kw, vg = score_text(opt)
            opt_scores.append({
                "idx": j,
                "score": sc,
                "keywords": kw,
                "vague": vg,
                "preview": opt[:120],
            })
        explicit_opts = sum(1 for x in opt_scores if x["score"] >= 2)
        intimate_opts = sum(1 for x in opt_scores if x["score"] >= 1)
        rows.append({
            "iter": i,
            "turn": new_turn,
            "choice": choice_label,
            "elapsed_sec": elapsed,
            "story_chars": len(story),
            "story_intimate_score": sh,
            "story_keywords": sh_kw,
            "story_vague": sv,
            "options_count": len(options),
            "options_intimate_ge1": intimate_opts,
            "options_intimate_ge2": explicit_opts,
            "options": opt_scores,
            "story_preview": story[:240].replace("\n", " "),
        })
        print(
            f"[OK] {i}/10 T{new_turn} story_score={sh} "
            f"opts_intimate={intimate_opts}/{len(options)} explicit2+={explicit_opts} {elapsed}s"
        )

    end_turn = int(io_utils.read_yaml(config.SESSION_STATE_PATH).get("turn", start_turn))
    n = len(rows)
    summary = {
        "avg_story_intimate_score": round(sum(r["story_intimate_score"] for r in rows) / max(n, 1), 2),
        "turns_story_score_ge3": sum(1 for r in rows if r["story_intimate_score"] >= 3),
        "turns_with_explicit_option_ge2": sum(1 for r in rows if r["options_intimate_ge2"] >= 2),
        "turns_with_any_intimate_option": sum(1 for r in rows if r["options_intimate_ge1"] >= 1),
    }
    report = {
        "finished_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "start_turn": start_turn,
        "end_turn": end_turn,
        "rounds_requested": 10,
        "rounds_ok": n,
        "adult_settings": {
            "adult_mode": config.ADULT_MODE,
            "adult_profile": config.ADULT_PROFILE,
            "content_weights": config.CONTENT_WEIGHTS,
            "expression_style": config.EXPRESSION_STYLE,
        },
        "failure": fail,
        "turns": rows,
        "summary": summary,
    }

    out = ROOT / "output" / "adult_verify_10.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[report] {out}")
    print(f"[summary] {json.dumps(summary, ensure_ascii=False)}")

    passed = fail is None and n == 10
    if passed and summary["turns_with_explicit_option_ge2"] < 5:
        print("[warn] options 色情推进偏弱：10 轮中仅 "
              f"{summary['turns_with_explicit_option_ge2']} 轮有 ≥2 个露骨选项")
    if passed and summary["turns_story_score_ge3"] < 3:
        print("[warn] 正文色情推进偏弱：10 轮中仅 "
              f"{summary['turns_story_score_ge3']} 轮 story 亲密词 ≥3")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
