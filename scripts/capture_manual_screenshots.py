#!/usr/bin/env python3
"""Capture real UI screenshots for release/PromptOS-用户手册.html.

Usage (from prompt-os-engine/):
  pip install playwright
  playwright install chromium
  python scripts/capture_manual_screenshots.py
"""
from __future__ import annotations

import subprocess
import sys
import time
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


def _wait_server(timeout: float = 30.0) -> None:
    import urllib.request

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


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    dist_index = ROOT / "frontend" / "dist" / "index.html"
    if not dist_index.is_file():
        print("Building frontend first…")
        subprocess.run(["npm.cmd", "run", "build"], cwd=ROOT / "frontend", check=True)

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
            for name, path, _label in SHOTS:
                url = f"{BASE}{path}"
                print(f"  {name} ← {url}")
                page.goto(url, wait_until="networkidle", timeout=60_000)
                page.wait_for_timeout(2000)
                if name == "01-api-key":
                    page.wait_for_selector('[role="dialog"]', timeout=10_000)
                dest = OUT / f"{name}.png"
                page.screenshot(path=str(dest), type="png")
                print(f"    → {dest.relative_to(ROOT)}")
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
