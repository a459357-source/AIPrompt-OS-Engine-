#!/usr/bin/env python3
"""
generate_audit_report.py — 实测并生成带日期的 PROJECT_AUDIT_REPORT_YYYY-MM-DD.html
不修改原 PROJECT_AUDIT_REPORT.html。
"""
from __future__ import annotations

import datetime
import html
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT.parent
ENGINE = ROOT
FRONTEND = ENGINE / "frontend" / "src"

# Unit tests only (e2e requires live server / personal data)
UNIT_TESTS = [
    "test_state_store.py", "test_app_settings.py", "test_gen_settings_sync.py",
    "test_character_relations.py", "test_choice_prompt.py", "test_api.py",
    "test_context_compress.py", "test_analytics.py", "test_memory.py",
    "test_full_system.py", "test_graph.py", "test_save.py", "test_events.py",
    "test_state_machine.py",
]


def run_pytest() -> tuple[int, int, str]:
    cmd = [sys.executable, "-m", "pytest", *UNIT_TESTS, "-q", "--tb=no"]
    proc = subprocess.run(cmd, cwd=ENGINE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (proc.stdout or "") + (proc.stderr or "")
    passed = failed = 0
    m = re.search(r"(\d+) passed", out)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+) failed", out)
    if m:
        failed = int(m.group(1))
    m = re.search(r"(\d+) error", out)
    if m:
        failed += int(m.group(1))
    return passed, failed, out.strip()[-500:]


def collect_routes() -> list[tuple[str, str, str]]:
    sys.path.insert(0, str(ENGINE))
    from ui.web_app import app

    seen: set[tuple[str, str]] = set()
    rows: list[tuple[str, str, str]] = []
    for route in app.routes:
        methods = sorted(getattr(route, "methods", None) or [])
        path = getattr(route, "path", "")
        name = getattr(route, "name", "")
        for method in methods:
            if method == "HEAD":
                continue
            key = (method, path.rstrip("/") or "/")
            if key in seen:
                continue
            seen.add(key)
            rows.append((method, path, name))
    rows.sort(key=lambda r: (r[1], r[0]))
    return rows


def count_pattern(path: Path, pattern: str) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        text = path.read_text(encoding="utf-8", errors="replace")
        return len(re.findall(pattern, text))
    total = 0
    for f in path.rglob("*"):
        if f.suffix in {".py", ".ts", ".tsx", ".yaml", ".md"} and f.is_file():
            text = f.read_text(encoding="utf-8", errors="replace")
            total += len(re.findall(pattern, text))
    return total


def file_exists(rel: str) -> bool:
    return (ENGINE / rel).exists() or (FRONTEND / rel.replace("frontend/", "")).exists()


def esc(s: str) -> str:
    return html.escape(str(s))


def build_html(
    *,
    report_date: str,
    pytest_passed: int,
    pytest_failed: int,
    pytest_tail: str,
    routes: list[tuple[str, str, str]],
) -> str:
    legacy_templates = (ENGINE / "ui" / "templates.py").exists()
    legacy_route_refs = count_pattern(ENGINE / "ui", r'["\']/legacy["\']')
    frontend_legacy = count_pattern(FRONTEND, r"/legacy")

    checks = [
        ("engine/state_store.py", (ENGINE / "engine" / "state_store.py").exists(), "RuntimeState 事务层"),
        ("test_state_store.py", (ENGINE / "test_state_store.py").exists(), "事务层测试"),
        ("frontend Game.tsx", (FRONTEND / "pages" / "Game.tsx").exists(), "游戏页"),
        ("frontend Dashboard.tsx", (FRONTEND / "pages" / "Dashboard.tsx").exists(), "仪表盘"),
        ("frontend Settings.tsx", (FRONTEND / "pages" / "Settings.tsx").exists(), "设置页"),
        ("frontend NewStory.tsx", (FRONTEND / "pages" / "NewStory.tsx").exists(), "新故事"),
        ("frontend NPCs.tsx", (FRONTEND / "pages" / "NPCs.tsx").exists(), "NPC 页"),
        ("api listSaves", "listSaves" in (FRONTEND / "lib" / "api.ts").read_text(encoding="utf-8"), "V2 存档 API"),
        ("Settings 手动存档 UI", "handleSaveSlot" in (FRONTEND / "pages" / "Settings.tsx").read_text(encoding="utf-8"), "V2 存档 UI"),
        ("Dashboard Mermaid 分支图", "剧情分支图" in (FRONTEND / "pages" / "Dashboard.tsx").read_text(encoding="utf-8")
         and "mermaid" in (FRONTEND / "pages" / "Dashboard.tsx").read_text(encoding="utf-8"), "可视化（非仅节点数统计）"),
        ("dashboard story_graph API", "story_graph" in (ENGINE / "ui" / "routes" / "api.py").read_text(encoding="utf-8"), "图谱 API 含 mermaid"),
    ]

    npcs_src = (FRONTEND / "pages" / "NPCs.tsx").read_text(encoding="utf-8")
    newstory_src = (FRONTEND / "pages" / "NewStory.tsx").read_text(encoding="utf-8")
    apikey_src = (FRONTEND / "components" / "ApiKeyPrompt.tsx").read_text(encoding="utf-8")
    settings_src = (FRONTEND / "pages" / "Settings.tsx").read_text(encoding="utf-8")

    bug_fixes = [
        ("P1 Game handleChoice 成功清 error", "setError('')" in (FRONTEND / "pages" / "Game.tsx").read_text(encoding="utf-8")),
        ("P1 Dashboard 成功清 error", "setError('')\n      setData(d)" in (FRONTEND / "pages" / "Dashboard.tsx").read_text(encoding="utf-8")),
        ("P1 NPCs load/generate 成功清 error", "setError('')\n      setCharacters" in npcs_src and "setError('')\n      setCharacters((prev)" in npcs_src),
        ("P2 历史回顾 historyError + 重试", "historyError" in (FRONTEND / "pages" / "Game.tsx").read_text(encoding="utf-8")),
        ("P2 Token 引导快捷设置", "快捷设置" in (FRONTEND / "pages" / "Game.tsx").read_text(encoding="utf-8")
         and "setGenSettingsOpen(true)" in (FRONTEND / "pages" / "Game.tsx").read_text(encoding="utf-8")),
        ("P3 NewStory rel_stages UI", "关系阶段（全局）" in newstory_src),
        ("P3 NewStory rel_affection UI", "初始好感度" in newstory_src and "rel_affection" in newstory_src),
        ("P3 NewStory background 字段", "背景故事" in newstory_src),
        ("P3 NewStory special_ability 字段", "特殊能力" in newstory_src),
        ("P3 API Key 双入口说明", "apikey.json" in settings_src),
        ("P3 ApiKeyPrompt settings-changed 事件", "promptos:settings-changed" in apikey_src and "promptos:settings-changed" in settings_src),
    ]

    pytest_ok = pytest_failed == 0
    route_rows = "\n".join(
        f"<tr><td><code>{esc(m)}</code></td><td><code>{esc(p)}</code></td><td>{esc(n)}</td></tr>"
        for m, p, n in routes
    )
    check_rows = "\n".join(
        f"<tr><td><code>{esc(path)}</code></td><td>{'<span class=\"badge badge-ok\">✓</span>' if ok else '<span class=\"badge badge-missing\">✗</span>'}</td><td>{esc(desc)}</td></tr>"
        for path, ok, desc in checks
    )
    bug_rows = "\n".join(
        f"<tr><td>{esc(name)}</td><td>{'<span class=\"badge badge-ok\">已修复</span>' if ok else '<span class=\"badge badge-missing\">未验证</span>'}</td></tr>"
        for name, ok in bug_fixes
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PromptOS 审计报告 {report_date}</title>
  <style>
    :root {{
      --bg:#0f1117; --surface:#1a1d27; --card:#222633; --border:#2e3347;
      --text:#e4e6ef; --muted:#8b90a5; --primary:#7c6cf0; --accent:#5eead4;
      --success:#4ade80; --danger:#f87171;
    }}
    body {{ font-family:"Segoe UI","PingFang SC",sans-serif; background:var(--bg); color:var(--text); padding:2rem; line-height:1.6; }}
    .container {{ max-width:1200px; margin:0 auto; }}
    h1 {{ color:var(--primary); }}
    h2 {{ color:var(--accent); margin-top:2rem; border-bottom:1px solid var(--border); padding-bottom:.4rem; }}
    table {{ width:100%; border-collapse:collapse; margin:1rem 0; font-size:.88rem; }}
    th,td {{ padding:.6rem .8rem; border-bottom:1px solid var(--border); text-align:left; }}
    th {{ background:var(--card); }}
    code {{ background:var(--card); padding:2px 6px; border-radius:4px; color:var(--accent); }}
    .badge {{ display:inline-block; padding:2px 8px; border-radius:6px; font-size:.75rem; font-weight:600; }}
    .badge-ok {{ background:rgba(74,222,128,.15); color:var(--success); }}
    .badge-missing {{ background:rgba(248,113,113,.15); color:var(--danger); }}
    .meta {{ color:var(--muted); margin-bottom:1.5rem; }}
    .summary-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:1rem; margin:1rem 0; }}
    .stat-card {{ background:var(--card); border:1px solid var(--border); border-radius:10px; padding:1rem; text-align:center; }}
    .stat-num {{ font-size:1.8rem; font-weight:700; color:var(--primary); }}
    pre {{ background:var(--card); padding:1rem; border-radius:8px; overflow-x:auto; font-size:.78rem; color:var(--muted); }}
  </style>
</head>
<body>
<div class="container">
  <h1>PromptOS 项目审计报告（实测）</h1>
  <p class="meta">生成日期：{esc(report_date)} · 命令：<code>python scripts/generate_audit_report.py</code> · 原报告 <code>PROJECT_AUDIT_REPORT.html</code> 未修改</p>

  <div class="summary-grid">
    <div class="stat-card"><div class="stat-num">{pytest_passed}</div><div>pytest 通过</div></div>
    <div class="stat-card"><div class="stat-num" style="color:{'var(--success)' if pytest_ok else 'var(--danger)'}">{pytest_failed}</div><div>pytest 失败</div></div>
    <div class="stat-card"><div class="stat-num">{len(routes)}</div><div>API 端点（去重）</div></div>
    <div class="stat-card"><div class="stat-num">{'0' if not legacy_templates else '!'}</div><div>Legacy templates.py</div></div>
  </div>

  <h2>1. Legacy 清理</h2>
  <table>
    <tr><th>检查项</th><th>结果</th></tr>
    <tr><td><code>ui/templates.py</code> 存在</td><td>{'<span class="badge badge-missing">仍存在</span>' if legacy_templates else '<span class="badge badge-ok">已移除</span>'}</td></tr>
    <tr><td>后端 <code>/legacy</code> 引用</td><td>{legacy_route_refs} 处 {'<span class="badge badge-ok">OK</span>' if legacy_route_refs == 0 else '<span class="badge badge-missing">残留</span>'}</td></tr>
    <tr><td>前端 <code>/legacy</code> 引用</td><td>{frontend_legacy} 处 {'<span class="badge badge-ok">OK</span>' if frontend_legacy == 0 else '<span class="badge badge-missing">残留</span>'}</td></tr>
  </table>

  <h2>2. V2 能力（Settings / Dashboard）</h2>
  <table>
    <tr><th>路径/项</th><th>状态</th><th>说明</th></tr>
    {check_rows}
  </table>

  <h2>3. 事务层 state_store</h2>
  <p style="color:var(--muted)"><code>run.step()</code> 回合内内存更新，<code>commit_runtime()</code> 单点落盘 session / memory / story_graph；<code>save_manager.load</code> / <code>/reset</code> / <code>/new</code> 使用 <code>commit_bundle</code>。</p>
  <p style="color:var(--muted)">已知边界：<code>world_pack.yaml</code> 创建故事时独立写入；<code>chapter.md</code> 在 <code>commit_runtime</code> 之后追加，不纳入同事务。</p>

  <h2>4. Bug 修复验证（静态）</h2>
  <table>
    <tr><th>项</th><th>状态</th></tr>
    {bug_rows}
  </table>

  <h2>5. pytest 实测</h2>
  <p>{'<span class="badge badge-ok">全绿</span>' if pytest_ok else '<span class="badge badge-missing">有失败</span>'} — {pytest_passed} passed, {pytest_failed} failed（不含 e2e）</p>
  <pre>{esc(pytest_tail)}</pre>

  <h2>6. FastAPI 端点清单</h2>
  <table>
    <tr><th>方法</th><th>路径</th><th>名称</th></tr>
    {route_rows}
  </table>

  <p class="meta" style="margin-top:3rem">— 报告结束 —</p>
</div>
</body>
</html>"""


def main() -> int:
    report_date = datetime.date.today().isoformat()
    passed, failed, tail = run_pytest()
    routes = collect_routes()
    doc = build_html(
        report_date=report_date,
        pytest_passed=passed,
        pytest_failed=failed,
        pytest_tail=tail,
        routes=routes,
    )
    out_path = WORKSPACE / f"PROJECT_AUDIT_REPORT_{report_date}.html"
    out_path.write_text(doc, encoding="utf-8")
    print(f"[OK] Report written: {out_path}")
    print(f"     pytest: {passed} passed, {failed} failed | routes: {len(routes)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
