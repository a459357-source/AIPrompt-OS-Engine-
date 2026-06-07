#!/usr/bin/env python3
"""Capture real UI screenshots for release/PromptOS-用户手册.html.

Usage (from prompt-os-engine/):
  pip install playwright requests
  playwright install chromium
  set PROMPTOS_SCREENSHOT_API_KEY=sk-...
  python scripts/capture_manual_screenshots.py

Or pass the key explicitly (avoid shell history when possible):
  python scripts/capture_manual_screenshots.py --api-key sk-...
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "release" / "manual-screenshots"
PORT = 8766
BASE = f"http://127.0.0.1:{PORT}"

SHOTS: list[tuple[str, str, str]] = [
    ("01-api-key", "/", "API Key 引导弹窗"),
    ("02-nav-world", "/new", "世界构建页与顶栏导航"),
    ("03-game", "/game", "模拟页（游戏）"),
    ("04-settings", "/settings", "设置页"),
    ("05-dashboard", "/dashboard", "势力 / 仪表盘"),
    ("06-npcs", "/npcs", "角色页"),
]

DEMO_STORY = {
    "title": "星海迷途",
    "world": "2157年，人类在火星发现古代文明遗迹「星门」，打开了通往银河系各地的通道。各大势力争夺星门控制权。",
    "genre": "科幻 / 冒险",
    "scene": "火星轨道站「回声号」舰桥",
    "main_goal": "找到星门的真正起源，阻止各方势力引爆星际战争",
    "chars_json": json.dumps([
        {
            "name": "林夜",
            "isMain": True,
            "role_tags": ["调查船船长", "前特种部队"],
            "personality_tags": ["冷静", "果断", "内敛"],
            "appearance": "黑发灰瞳，左脸有一道旧伤疤",
            "relationship": ["自身"],
            "goal": "揭开星门之谜",
            "secret": "曾在特种部队执行过涉及星门的黑色行动",
            "background": "前地球联邦军特种部队，因一次任务失败被降职",
            "special_ability": "战术分析与危机应变",
        },
        {
            "name": "艾琳",
            "isMain": False,
            "role_tags": ["考古语言学家", "星门研究员"],
            "personality_tags": ["热情", "好奇", "敏感"],
            "appearance": "银白长发，紫色眼瞳，佩戴古代文字解码器",
            "relationship": ["同事", "暗恋对象"],
            "goal": "解码星门文字，证明古文明的存在",
            "secret": "体内植入了星门碎片，能与遗迹产生共鸣",
            "background": "联盟科学院最年轻的研究员",
        },
        {
            "name": "白璃",
            "isMain": False,
            "role_tags": ["情报商人", "自由航行者"],
            "personality_tags": ["狡猾", "幽默", "重情义"],
            "appearance": "红色短发，左耳三个耳环",
            "relationship": ["朋友", "情报来源"],
            "goal": "赚够钱买下自己的飞船",
            "secret": "曾是帝国情报局特工，叛逃后隐姓埋名",
            "background": "在星际黑市中长大",
        },
    ]),
    "rel_system": json.dumps({
        "stages": ["崩坏", "敌视", "对立", "冷漠", "疏远", "陌生", "认识", "信赖", "盟友", "羁绊"],
        "affection": 30,
    }),
    "factions_json": json.dumps([
        {
            "name": "地球联邦",
            "type": "government",
            "description": "人类母星政府，掌控星门安保",
            "goals": ["垄断星门控制权", "压制分离势力"],
            "resources": ["联邦舰队", "星门安保系统"],
            "controlledTerritories": ["火星轨道", "联邦首都"],
            "subordinateOrganizations": ["联邦舰队司令部", "星门管理局"],
            "keyAssets": ["星门主控站", "联邦舰队"],
            "power": {"military": 80, "economic": 70, "political": 85, "technology": 60},
            "influence": 85,
            "relation_to_player": "hostile",
            "leader": "卡尔森上将",
        },
        {
            "name": "自由航行者联盟",
            "type": "guild",
            "description": "独立飞船船长的互助组织，反对政府垄断",
            "goals": ["打破星门垄断", "建立自由通商区"],
            "resources": ["商船队", "情报网"],
            "controlledTerritories": ["自由港", "小行星带据点"],
            "subordinateOrganizations": ["商船工会", "走私网络"],
            "keyAssets": ["自由港", "加密通讯网"],
            "power": {"military": 30, "economic": 50, "political": 40, "technology": 55},
            "influence": 55,
            "relation_to_player": "ally",
            "leader": "白璃",
        },
    ]),
    "artifacts_json": json.dumps([
        {
            "name": "星门主钥",
            "type": "world",
            "description": "传说中能完全控制星门网络的古代装置",
            "ownerType": "none",
            "ownerId": "",
            "importance": 95,
            "abilities": ["控制星门", "关闭通道", "打开新通道"],
            "tags": ["古代遗物", "争夺目标"],
        },
    ]),
    "custom_rules": json.dumps({
        "stats": [
            {"key": "trust", "label": "信任度", "max": 100},
            {"key": "influence", "label": "影响力", "max": 100},
        ],
    }),
}


def _wait_server(timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    url = f"{BASE}/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"server did not start on {BASE}")


def _http_post_form(path: str, fields: dict[str, str], *, timeout: float = 120.0) -> tuple[int, str, str]:
    body = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content_type = resp.headers.get("Content-Type", "")
        return resp.status, resp.read().decode("utf-8", errors="replace"), content_type


def _http_get_json(path: str, *, timeout: float = 30.0) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _save_api_key(api_key: str) -> None:
    status, body, _ctype = _http_post_form("/api/settings-key", {"api_key": api_key.strip()})
    if status != 200:
        raise RuntimeError(f"save api key failed ({status}): {body[:200]}")
    data = json.loads(body)
    if data.get("error"):
        raise RuntimeError(f"save api key failed: {data['error']}")


def _create_demo_story() -> None:
    status, _body, _ctype = _http_post_form("/new", DEMO_STORY, timeout=60.0)
    if status not in (200, 303, 302):
        raise RuntimeError(f"create story failed (HTTP {status})")


def _wait_game_ready(*, min_story: int = 80, max_wait: float = 240.0) -> dict:
    deadline = time.time() + max_wait
    last_error = ""
    while time.time() < deadline:
        try:
            data = _http_get_json("/api/game-state")
        except OSError as exc:
            last_error = str(exc)
            time.sleep(1.0)
            continue
        if data.get("error"):
            last_error = str(data["error"])
            time.sleep(1.0)
            continue
        if data.get("not_started"):
            gen = _http_get_json("/api/generation-status")
            if gen.get("active"):
                partial = len(str(gen.get("story", "")))
                if partial > 20:
                    print(f"    generating… {partial} chars", end="\r")
            time.sleep(2.0)
            continue
        story_len = len(str(data.get("story", "")))
        if story_len >= min_story and data.get("options"):
            print(f"    game ready: turn={data.get('state', {}).get('turn')}, story={story_len} chars")
            return data
        time.sleep(1.5)
    raise RuntimeError(f"game did not become ready in time ({last_error or 'timeout'})")


def _start_game_and_wait(*, max_wait: float = 240.0) -> None:
    status, body, content_type = _http_post_form("/api/start", {}, timeout=max_wait)
    if status != 200:
        raise RuntimeError(f"start game failed ({status}): {body[:200]}")
    if "application/json" in content_type:
        data = json.loads(body)
        if data.get("error"):
            raise RuntimeError(f"start game failed: {data['error']}")
        if not data.get("not_started") and len(str(data.get("story", ""))) > 80:
            print(f"    opening returned immediately ({len(data.get('story', ''))} chars)")
            return
    _wait_game_ready(max_wait=max_wait)


def _advance_one_turn(*, max_wait: float = 240.0) -> None:
    """One turn so dashboard / npc pages have richer runtime data."""
    before = _http_get_json("/api/game-state")
    turn_before = int((before.get("state") or {}).get("turn") or 0)
    options = before.get("options") or []
    if not options:
        return
    status, _body, _ctype = _http_post_form("/api/next", {"choice": "A"}, timeout=max_wait)
    if status != 200:
        print(f"    warn: next turn HTTP {status}")
        return
    deadline = time.time() + max_wait
    while time.time() < deadline:
        data = _http_get_json("/api/game-state")
        turn_now = int((data.get("state") or {}).get("turn") or 0)
        if turn_now > turn_before and len(str(data.get("story", ""))) > 40:
            print(f"    advanced to turn {turn_now}")
            return
        time.sleep(2.0)
    print("    warn: next turn timed out")


def _capture_pages(page, names: list[str]) -> None:
    for name, path, label in SHOTS:
        if name not in names:
            continue
        url = f"{BASE}{path}"
        print(f"  {name} ← {url} ({label})")
        page.goto(url, wait_until="networkidle", timeout=60_000)
        page.wait_for_timeout(2500)
        if name == "03-game":
            page.wait_for_selector("article, .prose, [class*='story']", timeout=30_000)
        if name == "05-dashboard":
            page.wait_for_timeout(1500)
        dest = OUT / f"{name}.png"
        page.screenshot(path=str(dest), type="png")
        print(f"    → {dest.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture manual screenshots with optional live game setup.")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("PROMPTOS_SCREENSHOT_API_KEY", "").strip(),
        help="DeepSeek API key (or set PROMPTOS_SCREENSHOT_API_KEY)",
    )
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="Only capture pages; assume story already started and key configured",
    )
    args = parser.parse_args()

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    dist_index = ROOT / "frontend" / "dist" / "index.html"
    if not dist_index.is_file():
        print("Building frontend first…")
        subprocess.run(["npm.cmd", "run", "build"], cwd=ROOT / "frontend", check=True)

    if not args.skip_setup:
        print("Resetting factory data (no API key)…")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "reset_user_data.py")], check=True)

    print(f"Starting server on {BASE} …")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "ui.web_app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_server()
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            print("Install playwright: pip install playwright && playwright install chromium")
            raise SystemExit(1) from exc

        OUT.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.emulate_media(color_scheme="dark")

            # 1) API key dialog before key is saved
            if not args.skip_setup:
                print("Capturing API key prompt…")
                page.goto(f"{BASE}/", wait_until="networkidle", timeout=60_000)
                page.wait_for_selector('[role="dialog"]', timeout=15_000)
                page.wait_for_timeout(1000)
                page.screenshot(path=str(OUT / "01-api-key.png"), type="png")
                print(f"    → {OUT.relative_to(ROOT)}/01-api-key.png")

                if not args.api_key:
                    browser.close()
                    raise SystemExit(
                        "Need --api-key or PROMPTOS_SCREENSHOT_API_KEY to capture functional pages."
                    )

                print("Saving API key and creating demo story…")
                _save_api_key(args.api_key)
                _create_demo_story()
                print("Starting game (AI opening, may take 1–3 min)…")
                _start_game_and_wait()
                print("Advancing one turn for dashboard data…")
                _advance_one_turn()

            remaining = [n for n, _, _ in SHOTS if args.skip_setup or n != "01-api-key"]
            _capture_pages(page, remaining)
            browser.close()

        print(f"Done. {len(SHOTS)} screenshots in {OUT.relative_to(ROOT)}/")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
