"""
web_app.py — FastAPI Web UI for the Galgame Runtime
=====================================================
Serves an interactive web interface:
  • GET  /              → current story + option buttons
  • GET  /next?choice=A → advance the story with chosen option
  • GET  /reset         → reset session state
  • GET  /export        → download Obsidian export

Start with: python engine/run.py --mode web
Or directly:  uvicorn ui.web_app:app --reload
"""

from pathlib import Path
import sys
import json

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI, Query, Request, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from engine.run import step
from engine import io_utils
from engine import save_manager
from engine.memory import get_char_stats_for_ui, load_memory
from config import save_api_key, clear_api_key, reload_api_key, APIKEY_PATH
from config import save_model, reload_model, AVAILABLE_MODELS
from config import save_story_length, reload_story_length
import config

app = FastAPI(
    title="Prompt OS Galgame Runtime",
    description="🎮 Interactive AI Narrative Engine — Web UI",
    version="1.0.0",
)

# Serve local JS libraries for offline dashboard / graph pages
_static_dir = config.OUTPUT_DIR
_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/health")
async def health():
    """Lightweight health-check endpoint (CORS-friendly for splash loader)."""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"status": "ok"},
        headers={"Access-Control-Allow-Origin": "*"},
    )


@app.post("/shutdown")
async def shutdown():
    """Gracefully shut down the server."""
    import os
    os._exit(0)


# ── HTML template (inline) ────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>星痕纪元 — Galgame Runtime</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: "Segoe UI", "Noto Sans SC", system-ui, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            height: 100vh; overflow: hidden;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .container {
            display: flex; gap: 0; align-items: flex-start;
            width: 100%; height: 100%;
        }
        .nav-col {
            width: 48px; flex-shrink: 0; height: 100%;
            background: #0d1117; border-right: 1px solid #21262d;
            display: flex; flex-direction: column; padding: 8px 4px; gap: 2px;
            transition: width 0.2s; overflow: hidden; z-index: 10;
        }
        .nav-col:hover, .nav-col.open { width: 170px; }
        .nav-toggle {
            display: flex; align-items: center; justify-content: center;
            width: 100%; padding: 6px 0; margin-bottom: 6px;
            background: transparent; border: 1px solid #30363d;
            border-radius: 6px; color: #8b949e;
            font-size: 0.85em; cursor: pointer;
            transition: all 0.15s; flex-shrink: 0;
        }
        .nav-toggle:hover { border-color: #58a6ff; color: #58a6ff; }
        .nav-col:not(.open) .nav-toggle span.arr { display: inline-block; transform: rotate(0deg); transition: transform 0.2s; }
        .nav-col.open .nav-toggle span.arr { display: inline-block; transform: rotate(180deg); }
        .nav-item {
            display: flex; align-items: center; gap: 10px;
            padding: 8px 10px; border-radius: 6px;
            color: #8b949e; text-decoration: none;
            font-size: 0.8em; white-space: nowrap;
            transition: all 0.12s;
        }
        .nav-item:hover { background: #1c2333; color: #c9d1d9; }
        .nav-item .ni-icon { font-size: 1.15em; min-width: 20px; text-align: center; flex-shrink: 0; }
        .nav-item .ni-text { opacity: 0; transition: opacity 0.15s; }
        .nav-col:hover .ni-text, .nav-col.open .ni-text { opacity: 1; }
        .main-col {
            flex: 1; min-width: 0; height: 100%;
            display: flex; flex-direction: column; overflow: hidden;
            padding: 10px 16px 4px;
        }
        .side-col {
            width: 240px; flex-shrink: 0; height: 100%;
            transition: opacity 0.25s;
            overflow: hidden;
            display: flex; flex-direction: column;
        }
        .resize-handle {
            width: 5px; flex-shrink: 0; height: 100%;
            background: transparent; cursor: col-resize;
            transition: background 0.15s; z-index: 5;
        }
        .resize-handle:hover, .resize-handle.active { background: #30363d; }
        .side-col.collapsed {
            width: 28px; opacity: 0.6;
        }
        .side-toggle {
            display: block; width: 100%;
            background: #161b22; border: 1px solid #30363d;
            border-radius: 6px; color: #8b949e;
            font-size: 0.75em; padding: 4px 0; cursor: pointer;
            text-align: center; margin-bottom: 8px;
            transition: all 0.15s;
        }
        .side-toggle:hover { border-color: #58a6ff; color: #58a6ff; }
        .side-inner { flex: 1; overflow-y: auto; transition: opacity 0.2s; }
        .side-col.collapsed .side-inner { opacity: 0; pointer-events: none; }
        .char-widget {
            background: #161b22; border: 1px solid #30363d;
            border-radius: 8px; padding: 14px 16px; margin-bottom: 10px;
            font-size: 0.85em; line-height: 1.6;
        }
        .char-widget .cw-name {
            font-weight: bold; color: #d2a8ff; font-size: 1.05em;
        }
        .char-widget .cw-role {
            color: #8b949e; font-size: 0.85em; margin-bottom: 4px;
        }
        .char-widget .cw-level {
            color: #ffa657; font-size: 0.85em;
        }
        .char-widget .cw-hearts {
            font-size: 1.1em; letter-spacing: 1px; margin: 4px 0;
        }
        .char-widget .cw-stage {
            color: #7ee787; font-weight: bold; margin-bottom: 2px;
        }
        .char-widget .cw-stage.bad { color: #f85149; }
        .char-widget .cw-trust-bar {
            height: 4px; background: #21262d; border-radius: 2px;
            margin: 4px 0; overflow: hidden;
        }
        .char-widget .cw-trust-fill {
            height: 100%; border-radius: 2px; transition: width 0.3s;
        }
        .char-widget .cw-flags {
            margin-top: 4px; color: #8b949e; font-size: 0.9em;
        }
        .char-widget .cw-flag {
            display: inline-block; background: #1a3a5c; color: #58a6ff;
            padding: 1px 5px; border-radius: 3px; margin: 1px 2px 1px 0;
            font-size: 0.85em;
        }

        .header {
            text-align: center; flex-shrink: 0;
            padding: 14px 0 10px;
            border-bottom: 1px solid #30363d;
            margin-bottom: 12px;
        }
        .header h1 {
            font-size: 1.6em;
            color: #58a6ff;
            margin-bottom: 2px;
        }
        .header .subtitle {
            color: #8b949e;
            font-size: 0.85em;
        }
        .state-panel {
            display: flex; align-items: center; gap: 12px;
            background: #161b22; flex-shrink: 0;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 6px 14px;
            margin-bottom: 10px;
            font-size: 0.82em; flex-wrap: wrap;
        }
        .state-panel .sep {
            color: #30363d; margin: 0 2px;
        }
        .state-panel .label {
            color: #484f58; margin-right: 2px;
        }
        .state-panel .value {
            color: #c9d1d9; font-weight: bold;
        }
        .status-dots {
            display: flex; gap: 6px; align-items: center;
        }
        .status-dot {
            width: 22px; height: 22px; border-radius: 50%;
            background: #21262d; border: 2px solid #30363d;
            font-size: 0.65em; text-align: center; line-height: 18px;
            color: #484f58; cursor: default;
        }
        .status-dot.active {
            background: #1a3a5c; border-color: #58a6ff; color: #58a6ff;
        }
        .status-dot.passed {
            background: #1a3a2a; border-color: #238636; color: #7ee787;
        }
        .char-inline {
            color: #8b949e; font-size: 0.92em;
        }
        .char-inline .cname { color: #d2a8ff; }
        .char-inline .clevel { color: #ffa657; }
        .char-inline .ctrust { color: #7ee787; }
        .force-badge {
            display: inline-block;
            background: #3d1a1a; color: #f85149;
            border: 1px solid #da3633;
            padding: 1px 7px; border-radius: 8px;
            font-size: 0.75em; font-weight: bold;
            white-space: nowrap;
        }
        .story-block {
            flex: 1; overflow-y: auto; min-height: 0;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px 28px;
            margin-bottom: 10px;
            line-height: 1.9;
            font-size: 1.05em;
            white-space: pre-wrap;
        }
        .options {
            display: flex; flex-shrink: 0;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 10px;
        }
        .option-btn {
            display: block;
            width: 100%;
            text-align: left;
            padding: 12px 20px;
            background: #1c2333;
            border: 1px solid #30363d;
            border-radius: 8px;
            color: #c9d1d9;
            font-size: 1em;
            cursor: pointer;
            transition: all 0.15s;
            text-decoration: none;
        }
        .option-btn:hover {
            background: #212b3d;
            border-color: #58a6ff;
            color: #58a6ff;
        }
        .option-btn .key {
            display: inline-block;
            background: #30363d;
            color: #58a6ff;
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 4px;
            margin-right: 10px;
            min-width: 24px;
            text-align: center;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #8b949e;
        }
        .loading .spinner {
            display: inline-block;
            width: 24px;
            height: 24px;
            border: 2px solid #30363d;
            border-top: 2px solid #58a6ff;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-bottom: 8px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .custom-choice {
            display: flex; gap: 6px; align-items: center; flex-shrink: 0;
            margin-bottom: 8px;
        }
        .custom-choice .cc-label {
            color: #8b949e; font-size: 0.82em; white-space: nowrap;
        }
        .custom-choice input {
            flex: 1; padding: 7px 12px;
            background: #161b22; border: 1px solid #30363d;
            border-radius: 6px; color: #c9d1d9; font-size: 0.9em;
            font-family: inherit;
        }
        .custom-choice input:focus { outline: none; border-color: #ffa657; }
        .custom-choice button {
            padding: 7px 14px; background: #1c2333;
            border: 1px solid #30363d; border-radius: 6px;
            color: #ffa657; font-size: 0.9em; cursor: pointer;
            font-weight: bold; transition: all 0.15s;
        }
        .custom-choice button:hover { background: #212b3d; border-color: #ffa657; }
        .toolbar {
            display: flex; gap: 12px; flex-wrap: wrap; flex-shrink: 0;
            margin-bottom: 4px; justify-content: center;
        }
        .tb-group {
            display: flex; align-items: center; gap: 4px;
            background: #161b22; border: 1px solid #21262d;
            border-radius: 8px; padding: 4px 8px;
        }
        .tb-label { font-size: 0.9em; opacity: 0.7; }
        .tb-slot {
            width: 26px; height: 26px; padding: 0;
            background: #1c2333; border: 1px solid #30363d;
            border-radius: 4px; color: #8b949e;
            font-size: 0.75em; cursor: pointer;
            transition: all 0.12s; line-height: 24px; text-align: center;
        }
        .tb-group:first-child .tb-slot { color: #7ee787; }
        .tb-group:first-child .tb-slot:hover { border-color: #7ee787; color: #7ee787; background: #1a2e1a; }
        .tb-group:last-child .tb-slot { color: #d2a8ff; }
        .tb-group:last-child .tb-slot:hover { border-color: #d2a8ff; color: #d2a8ff; background: #1f1a2e; }
        .toast {
            position: fixed; top: 16px; left: 50%; transform: translateX(-50%);
            background: #1c2333; border: 1px solid #58a6ff;
            color: #58a6ff; padding: 10px 24px; border-radius: 8px;
            font-size: 0.9em; z-index: 100;
            animation: fadeInOut 2.5s ease forwards;
        }
        @keyframes fadeInOut {
            0% { opacity: 0; top: 0; }
            15% { opacity: 1; top: 16px; }
            75% { opacity: 1; top: 16px; }
            100% { opacity: 0; top: 0; }
        }
        /* footer removed — nav in left sidebar */
        .error-block {
            background: #2d1111;
            border: 1px solid #da3633;
            color: #f85149;
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 16px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="nav-col" id="navCol">
            <button class="nav-toggle" onclick="event.stopPropagation();var n=document.getElementById('navCol');n.classList.toggle('open');localStorage.setItem('navOpen',n.classList.contains('open')?'1':'0')" title="锁定/解锁侧栏"><span class="arr">▶</span></button>
            <a class="nav-item" href="/new" title="创建新故事世界"><span class="ni-icon">🆕</span><span class="ni-text">新故事</span></a>
            <a class="nav-item" href="/npcs" title="管理角色与 NPC"><span class="ni-icon">👥</span><span class="ni-text">角色</span></a>
            <a class="nav-item" href="/history" title="查看历史回合"><span class="ni-icon">📜</span><span class="ni-text">历史</span></a>
            <a class="nav-item" href="/dashboard" title="数据仪表盘与分析"><span class="ni-icon">📊</span><span class="ni-text">仪表盘</span></a>
            <a class="nav-item" href="/graph" target="_blank" title="剧情分支图（新窗口）"><span class="ni-icon">🌳</span><span class="ni-text">分支图</span></a>
            <a class="nav-item" href="/settings" title="API Key 与模型设置"><span class="ni-icon">⚙️</span><span class="ni-text">设置</span></a>
            <a class="nav-item" href="#" onclick="if(confirm('确定要重置当前存档？所有进度将丢失。'))location.href='/reset'" title="重置存档到初始状态"><span class="ni-icon">🔄</span><span class="ni-text">重置</span></a>
            <a class="nav-item" href="/export" title="导出完整故事 Markdown"><span class="ni-icon">📝</span><span class="ni-text">导出</span></a>
        </div>
        <div class="main-col">
            <div class="header">
                <h1>🎮 {{TITLE}}</h1>
                <div class="subtitle">{{SUBTITLE}}</div>
            </div>

            {{ERROR}}

            <div class="state-panel">{{STATE_ROW}} <span id="connDot" style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#484f58;margin-left:8px;flex-shrink:0" title="连接状态"></span></div>

            <div class="story-block">{{STORY}}</div>

            {{OPTIONS}}

            <div class="custom-choice">
                <span class="cc-label">✏️ 自由输入：</span>
                <input id="customInput" type="text" placeholder="输入你想做的事…" onkeydown="if(event.key==='Enter')customNext()">
                <button onclick="customNext()">▶</button>
            </div>

            <div class="toolbar">
            <span class="tb-group">
                <span class="tb-label">💾</span>
                <button class="tb-slot" onclick="saveGame('slot1')" title="存档 1">1</button>
                <button class="tb-slot" onclick="saveGame('slot2')" title="存档 2">2</button>
                <button class="tb-slot" onclick="saveGame('slot3')" title="存档 3">3</button>
            </span>
            <span class="tb-group">
                <span class="tb-label">📂</span>
                <button class="tb-slot" onclick="loadGame('slot1')" title="读档 1">1</button>
                <button class="tb-slot" onclick="loadGame('slot2')" title="读档 2">2</button>
                <button class="tb-slot" onclick="loadGame('slot3')" title="读档 3">3</button>
            </span>
            <button class="tb-slot" onclick="if(confirm('确定要关闭服务器？')){fetch('/shutdown',{method:'POST'});setTimeout(function(){document.body.innerHTML='<div style=color:#8b949e;text-align:center;padding-top:40vh;font-size:1.2em>服务器已关闭，可以安全关闭此页面。</div>'},500)}" title="关闭游戏服务器" style="width:auto;padding:0 10px;color:#f85149;border-color:#da3633;">⏻</button>
        </div>


        </div><!-- .main-col -->

        <div class="resize-handle" id="resizeHandle"></div>

        <div class="side-col" id="sideCol">
            <button class="side-toggle" onclick="toggleSidebar()" title="折叠/展开角色面板">◀</button>
            <div class="side-inner">{{SIDEBAR}}</div>
        </div>
    </div>

    <script>
        // Show loading spinner when clicking an option
        document.querySelectorAll('.option-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                const optionsDiv = this.parentElement;
                optionsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><div>正在生成剧情…</div></div>';
            });
        });

        function showToast(msg, color) {
            const toast = document.createElement('div');
            toast.className = 'toast';
            toast.textContent = msg;
            toast.style.color = color || '#58a6ff';
            toast.style.borderColor = color || '#58a6ff';
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 2600);
        }

        async function saveGame(slot) {
            if (!confirm('确定要覆盖存档 ' + slot + ' 吗？')) return;
            try {
                const res = await fetch('/save?slot=' + slot);
                const data = await res.json();
                if (data.error) {
                    showToast('❌ ' + data.error, '#f85149');
                } else {
                    showToast('✅ 已保存到 ' + slot + '（第 ' + data.turn + ' 轮）', '#7ee787');
                }
            } catch(e) {
                showToast('❌ 保存失败：' + e.message, '#f85149');
            }
        }

        async function loadGame(slot) {
            if (!confirm('确定要读取存档 ' + slot + ' 吗？当前进度将被覆盖。')) return;
            try {
                const res = await fetch('/saves');
                const saves = await res.json();
                const found = saves.find(s => s.slot === slot && s.turn > 0);
                if (!found) {
                    showToast('❌ 存档 ' + slot + ' 为空，没有可读取的数据', '#f85149');
                    return;
                }
                window.location.href = '/load?slot=' + slot;
            } catch(e) {
                showToast('❌ 检查存档失败：' + e.message, '#f85149');
            }
        }

        function customNext() {
            const input = document.getElementById('customInput');
            const text = input.value.trim();
            if (!text) return;
            const optionsDiv = document.querySelector('.options');
            if (optionsDiv) optionsDiv.innerHTML = '';
            const cc = document.querySelector('.custom-choice');
            if (cc) cc.innerHTML = '<div class="loading"><div class="spinner"></div><div>正在生成剧情…</div></div>';
            window.location.href = '/next?choice=' + encodeURIComponent(text);
        }

        function toggleSidebar() {
            const sc = document.getElementById('sideCol');
            const btn = sc.querySelector('.side-toggle');
            sc.classList.toggle('collapsed');
            const collapsed = sc.classList.contains('collapsed');
            btn.textContent = collapsed ? '▶' : '◀';
            localStorage.setItem('sideCollapsed', collapsed ? '1' : '0');
        }

        // Resize handle: drag to adjust side panel width
        (function(){
            const handle = document.getElementById('resizeHandle');
            const side = document.getElementById('sideCol');
            let dragging = false, startX, startW;
            handle.addEventListener('mousedown', function(e){
                if(side.classList.contains('collapsed')) return;
                dragging = true; startX = e.clientX; startW = side.offsetWidth;
                handle.classList.add('active');
                document.body.style.cursor = 'col-resize';
                document.body.style.userSelect = 'none';
                e.preventDefault();
            });
            document.addEventListener('mousemove', function(e){
                if(!dragging) return;
                var newW = startW + startX - e.clientX;
                newW = Math.max(160, Math.min(500, newW));
                side.style.width = newW + 'px';
            });
            document.addEventListener('mouseup', function(){
                if(!dragging) return;
                dragging = false;
                handle.classList.remove('active');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            });
        })();

        // Restore sidebar states from localStorage on load
        (function(){
            if(localStorage.getItem('navOpen')==='1'){
                document.getElementById('navCol').classList.add('open');
            }
            if(localStorage.getItem('sideCollapsed')==='1'){
                const sc = document.getElementById('sideCol');
                sc.classList.add('collapsed');
                const btn = sc.querySelector('.side-toggle');
                if(btn) btn.textContent = '▶';
            }
        })();



        // ── Connection indicator ──
        const connDot = document.getElementById('connDot');
        if(connDot){
            setInterval(function(){
                fetch('/health').then(function(){
                    connDot.style.background = '#3fb950';
                    connDot.title = '服务器在线';
                }).catch(function(){
                    connDot.style.background = '#f85149';
                    connDot.title = '服务器断开';
                });
            }, 30000);
        }

        // ── Internal nav tracking (suppress shutdown for in-app clicks) ──
        document.addEventListener('click', function(e){
            var a = e.target.closest('a');
            if(a && a.href && a.origin === location.origin && !a.target){
                sessionStorage.setItem('internalNav', '1');
            }
        });
        document.addEventListener('submit', function(){ sessionStorage.setItem('internalNav', '1'); });
        // Clear flag on fresh load
        if(sessionStorage.getItem('internalNav') === '1'){
            sessionStorage.removeItem('internalNav');
        }

        // ── Auto-shutdown server when tab closes ──
        window.addEventListener('pagehide', function(){
            if(sessionStorage.getItem('internalNav') === '1') return;
            try { navigator.sendBeacon('/shutdown'); } catch(ex) {}
        });
        window.addEventListener('beforeunload', function(){
            if(sessionStorage.getItem('internalNav') === '1') return;
            try { navigator.sendBeacon('/shutdown'); } catch(ex) {}
        });
    </script>
</body>
</html>"""


def _render_template(
    story: str = "",
    options: list[str] | None = None,
    turn: int = 0,
    status: str = "SETUP",
    scene: str = "?",
    error: str = "",
    characters: dict | None = None,
    force_event: bool = False,
    char_stats: list[dict] | None = None,
    title: str = "",
    subtitle: str = "",
    chapter: int = 1,
) -> str:
    """Render the HTML template with current state."""
    options_html = ""
    if options:
        opts = "".join(
            f'<a class="option-btn" href="/next?choice={chr(65+i)}">'
            f'<span class="key">{chr(65+i)}</span>{opt}</a>'
            for i, opt in enumerate(options)
        )
        options_html = f'<div class="options">{opts}</div>'

    error_html = ""
    if error:
        error_html = f'<div class="error-block">{error}</div>'

    # Compact state row: turn | scene | ⬤⬤⬤⬤⬤ | 角色A | 角色B | ⚡
    statuses = ["SETUP", "BUILD", "TENSION", "CLIMAX", "COOLDOWN"]
    status_symbols = {"SETUP": "序", "BUILD": "展", "TENSION": "张", "CLIMAX": "高", "COOLDOWN": "余"}
    current_idx = statuses.index(status) if status in statuses else 0

    dot_parts = []
    for i, s in enumerate(statuses):
        cls = "status-dot"
        if i < current_idx:
            cls += " passed"
        elif i == current_idx:
            cls += " active"
        dot_parts.append(f'<span class="{cls}" title="{s}">{status_symbols[s]}</span>')
    dots_html = "".join(dot_parts)

    # Character inline: protagonist + important chars from char_stats
    char_parts = []
    if char_stats:
        for cs in char_stats:
            name = cs.get("name", "")
            level = cs.get("level", "L0")
            stage = cs.get("stage", "")
            trust_pct = cs.get("trust_pct", 0)
            if trust_pct >= 70:
                trust_color = "#7ee787"
            elif trust_pct >= 40:
                trust_color = "#ffa657"
            elif trust_pct >= 0:
                trust_color = "#8b949e"
            else:
                trust_color = "#f85149"
            char_parts.append(
                f'<span class="char-inline">'
                f'<span class="cname">{name}</span> '
                f'<span class="clevel">{level}</span>'
                f'<span class="ctrust" style="color:{trust_color}">{"·" + stage if stage else ""}</span>'
                f'</span>'
            )

    # Force badge
    force_html = '<span class="force-badge">⚡</span>' if force_event else ""

    # Assemble single row
    row_parts = [
        f'<span class="value">📖 {turn}</span>',
        f'<span class="sep">|</span>',
        f'<span class="value">第{chapter}章</span>',
        f'<span class="sep">|</span>',
        f'<span class="value">{scene}</span>',
        f'<span class="sep">|</span>',
        f'<span class="status-dots">{dots_html}</span>',
    ]
    if char_parts:
        row_parts.append('<span class="sep">|</span>')
        row_parts.append(' · '.join(char_parts))
    if force_html:
        row_parts.append(force_html)

    state_row_html = "".join(row_parts)

    # Sidebar: character widgets with hearts, stage, trust bar, flags
    sidebar_html = ""
    if char_stats:
        widgets = []
        for cs in char_stats:
            trust_pct = cs.get("trust_pct", 0)
            stage = cs.get("stage", "")
            is_bad = trust_pct < 0
            bar_color = "#f85149" if is_bad else "#7ee787"
            bar_pct = min(100, max(0, abs(trust_pct)))

            flags_html = ""
            flags = cs.get("flags", [])
            if flags:
                flags_html = '<div class="cw-flags">' + "".join(
                    f'<span class="cw-flag">{f}</span>' for f in flags[:4]
                ) + '</div>'

            # Custom stats
            custom_html = ""
            for cst in cs.get("custom_stats", []):
                pct = round(cst["value"] / cst["max"] * 100)
                custom_html += (
                    f'<div style="font-size:0.78em;color:#8b949e;margin-top:3px;">'
                    f'{cst["label"]}: <span style="color:#ffa657;">{cst["value"]}</span>'
                    f'<div style="height:3px;background:#21262d;border-radius:2px;margin-top:1px;">'
                    f'<div style="height:100%;width:{pct}%;background:#ffa657;border-radius:2px;"></div>'
                    f'</div></div>'
                )

            widgets.append(
                f'<div class="char-widget">'
                f'<div class="cw-name">{cs["name"]}</div>'
                f'<div class="cw-role">{cs["role"]}</div>'
                f'<div class="cw-level">⭐ {cs["level"]}</div>'
                f'<div class="cw-hearts">{cs["hearts"]}</div>'
                f'<div class="cw-stage{" bad" if is_bad else ""}">{stage}</div>'
                f'<div class="cw-trust-bar">'
                f'<div class="cw-trust-fill" style="width:{bar_pct}%;background:{bar_color}"></div>'
                f'</div>'
                f'{custom_html}'
                f'{flags_html}'
                f'</div>'
            )
        sidebar_html = "".join(widgets)

    return (
        HTML_TEMPLATE
        .replace("{{STORY}}", story or "点击下方按钮开始故事…")
        .replace("{{OPTIONS}}", options_html)
        .replace("{{STATE_ROW}}", state_row_html)
        .replace("{{SIDEBAR}}", sidebar_html)
        .replace("{{ERROR}}", error_html)
        .replace("{{TITLE}}", title or "Galgame")
        .replace("{{SUBTITLE}}", subtitle or "AI Narrative Engine")
    )


# ── Routes ─────────────────────────────────────────────────────────

def _get_world_title() -> tuple[str, str]:
    """Read world_pack.yaml and return (title, subtitle)."""
    try:
        wp = io_utils.read_yaml(config.WORLD_PACK_PATH)
        w = wp.get("world", {})
        title = w.get("title", "")
        genre = w.get("genre", "")
        return title, genre
    except Exception:
        return "", ""

@app.get("/", response_class=HTMLResponse)
async def index():
    """Show the current story state with option buttons."""
    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    except Exception:
        state = {}

    turn = state.get("turn", 0)
    status = state.get("status", "SETUP")
    scene = state.get("scene", "初始")

    # Get last turn's options from session history (clean, no parsing needed)
    history = state.get("history", [])
    if history:
        last = history[-1]
        story = last.get("story", last.get("summary", ""))
        options = last.get("options", [])
    else:
        # No history — auto-generate the opening scene
        result = step(None)
        if result is not None:
            # Re-read state after step() modified it
            try:
                state = io_utils.read_yaml(config.SESSION_STATE_PATH)
            except Exception:
                pass
            turn = state.get("turn", 1)
            status = state.get("status", "SETUP")
            scene = state.get("scene", "初始")
            story = result["story"]
            options = result["options"]
        else:
            # AI generation failed — show static fallback
            world_title = _get_world_title()[0] or "Galgame"
            world_scene = scene or "初始场景"
            story = f"欢迎来到 **{world_title}**。\n\n当前场景：{world_scene}\n\n❌ AI 生成失败，请检查 API Key 后刷新页面。"
            state_chars = state.get("characters", {})
            char_names = [c.get("name", "") for c in state_chars.values() if c.get("name")]
            options = [
                "调查周围环境，寻找线索",
                "与同伴交流当前情况",
                "检查装备和可用资源",
                "深入探索前方的未知区域",
            ]
            if len(char_names) >= 1:
                options[1] = f"与{char_names[0]}商议接下来的行动"
            if len(char_names) >= 2:
                options[2] = f"向{char_names[1]}询问她的看法"

    memory = load_memory()
    try:
        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
    except Exception:
        world_pack = {}
    char_stats = get_char_stats_for_ui(state, memory, world_pack)
    title, subtitle = _get_world_title()

    return _render_template(
        story=story,
        options=options,
        turn=turn,
        status=status,
        scene=scene,
        characters=state.get("characters"),
        force_event=state.get("force_event_pending", False),
        char_stats=char_stats,
        title=title,
        subtitle=subtitle,
        chapter=state.get("chapter", 1),
    )


@app.get("/next", response_class=HTMLResponse)
async def next_turn(choice: str = Query(..., min_length=1, max_length=1)):
    """
    Advance the story with the player's choice (A/B/C/D).
    Returns the new story page.
    """
    # Accept A/B/C/D or free-text (URL-encoded)
    if choice not in ("A", "B", "C", "D"):
        # Free-text choice — pass through as-is
        pass

    result = step(choice)

    if result is None:
        return _render_template(
            error="❌ 生成失败，请确认 API key 已设置且网络正常。",
            turn=0, status="?", scene="?",
        )

    # Read updated state for character & force_event info
    try:
        updated_state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    except Exception:
        updated_state = {}

    memory = load_memory()
    try:
        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
    except Exception:
        world_pack = {}
    char_stats = get_char_stats_for_ui(updated_state, memory, world_pack)
    title, subtitle = _get_world_title()

    return _render_template(
        story=result["story"],
        options=result["options"],
        turn=result["turn"],
        status=result["status"],
        scene=result["scene"],
        characters=updated_state.get("characters", result.get("state", {}).get("characters")),
        force_event=updated_state.get("force_event_pending", False),
        char_stats=char_stats,
        title=title,
        subtitle=subtitle,
        chapter=updated_state.get("chapter", 1),
    )


# ── Save / Load routes ────────────────────────────────────────────

@app.get("/save")
async def save_game(slot: str = Query("autosave", min_length=1)):
    """
    Save the current game state to a slot (autosave, slot1, slot2, slot3).
    Returns JSON summary.
    """
    from fastapi.responses import JSONResponse

    valid_slots = {"autosave", "slot1", "slot2", "slot3"}
    if slot not in valid_slots:
        return JSONResponse(
            {"error": f"无效存档槽: {slot}，可选: {', '.join(sorted(valid_slots))}"},
            status_code=400,
        )

    result = save_manager.save(slot)
    if result is None:
        return JSONResponse({"error": "保存失败"}, status_code=500)

    # Don't overwrite autosave with a manual save to autosave slot
    return JSONResponse(result)


@app.get("/load")
async def load_game(slot: str = Query("autosave", min_length=1)):
    """
    Load a saved game state from a slot.
    Redirects to the main page after loading.
    """
    from fastapi.responses import JSONResponse, RedirectResponse

    valid_slots = {"autosave", "slot1", "slot2", "slot3"}
    if slot not in valid_slots:
        return JSONResponse(
            {"error": f"无效存档槽: {slot}，可选: {', '.join(sorted(valid_slots))}"},
            status_code=400,
        )

    if not save_manager.save_exists(slot):
        return JSONResponse(
            {"error": f"存档槽 '{slot}' 为空，没有存档数据。"},
            status_code=404,
        )

    result = save_manager.load(slot)
    if result is None:
        return JSONResponse({"error": "读取存档失败"}, status_code=500)

    # Redirect to main page to show loaded state
    return RedirectResponse(url="/", status_code=303)


@app.get("/saves")
async def list_saves():
    """Return the list of all save slots as JSON."""
    from fastapi.responses import JSONResponse
    return JSONResponse(save_manager.list_saves())


@app.get("/graph", response_class=HTMLResponse)
async def story_graph_page():
    """
    Render an interactive Mermaid.js story graph page.
    """
    from engine.router import load_graph
    from ui.obsidian_export import _generate_mermaid

    mermaid_lines = _generate_mermaid()
    mermaid_code = "\n".join(mermaid_lines)

    graph_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>剧情分支图 — 星痕纪元</title>
    <script src="/static/mermaid.min.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: "Segoe UI", "Noto Sans SC", system-ui, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            height: 100vh; overflow: auto;
            display: flex; flex-direction: column; align-items: center;
        }}
        .container {{
            width: 100%; padding: 24px 20px;
        }}
        .header {{
            text-align: center; padding: 24px 0;
            border-bottom: 1px solid #30363d; margin-bottom: 24px;
        }}
        .header h1 {{ font-size: 1.6em; color: #58a6ff; }}
        .header a {{ color: #8b949e; text-decoration: none; font-size: 0.9em; }}
        .header a:hover {{ color: #58a6ff; }} .back-btn {{ display:inline-block;padding:5px 14px;background:#1c2333;border:1px solid #58a6ff;border-radius:6px;color:#58a6ff;text-decoration:none;font-size:0.85em;margin-top:8px; }} .back-btn:hover {{ background:#1a3a5c; }}
        .mermaid {{
            background: #161b22; border: 1px solid #30363d;
            border-radius: 8px; padding: 24px; margin-bottom: 24px;
            overflow-x: auto;
        }}
        .info {{
            background: #161b22; border: 1px solid #30363d;
            border-radius: 8px; padding: 16px; margin-bottom: 24px;
            font-size: 0.85em; color: #8b949e; line-height: 1.6;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌳 剧情分支图</h1>
            <a href="/" class="back-btn">← 返回游戏</a>
        </div>
        <div class="info">
            📖 每个节点代表一个剧情回合。边上的字母代表玩家在该节点的选择（A/B/C/D）。
            点击返回游戏继续推进剧情。
        </div>
        <div class="mermaid">
{mermaid_code}
        </div>
    </div>
    <script>
        mermaid.initialize({{ startOnLoad: true, theme: 'dark' }});
    </script>
</body>
</html>"""

    return graph_html


@app.get("/history", response_class=HTMLResponse)
async def history_page():
    """
    Show all past turns as a scrollable history log.
    """
    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    except Exception:
        state = {}

    history = state.get("history", [])
    turn = state.get("turn", 0)
    scene = state.get("scene", "")

    if not history:
        return HTMLResponse(
            HTML_TEMPLATE.replace("{{STORY}}", "尚无历史记录。")
            .replace("{{OPTIONS}}", "")
            .replace("{{STATE_ROW}}", "")
            .replace("{{SIDEBAR}}", "")
            .replace("{{ERROR}}", "")
        )

    blocks: list[str] = []
    for h in history:
        t = h.get("turn", "?")
        s = h.get("status", "?")
        sc = h.get("scene", "?")
        story = h.get("story", h.get("summary", ""))
        choice = h.get("choice", "")

        status_cn = {"SETUP": "序章", "BUILD": "展开", "TENSION": "张力", "CLIMAX": "高潮", "COOLDOWN": "余韵"}.get(s, s)

        blocks.append(
            f'<div style="margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid #30363d;">'
            f'<div style="color:#8b949e;font-size:0.8em;margin-bottom:6px;">'
            f'📖 第{t}轮 · {status_cn} · {sc}'
            f'{(" · 选择: " + choice) if choice else ""}'
            f'</div>'
            f'<div style="line-height:1.8;white-space:pre-wrap;">{story}</div>'
            f'</div>'
        )

    history_html = "\n".join(blocks)

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>历史回顾 — 星痕纪元</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: "Segoe UI", "Noto Sans SC", system-ui, sans-serif;
            background: #0d1117; color: #c9d1d9;
            height: 100vh; overflow: hidden; display: flex; flex-direction: column; align-items: center;
        }}
        .hist-container {{
            width: 100%; height: 100%;
            display: flex; flex-direction: column; padding: 16px 20px;
        }}
        .hist-header {{
            text-align: center; flex-shrink: 0;
            padding: 12px 0; border-bottom: 1px solid #30363d; margin-bottom: 12px;
        }}
        .hist-header h1 {{ font-size: 1.3em; color: #58a6ff; }}
        .hist-header a {{ color: #8b949e; text-decoration: none; font-size: 0.8em; }}
        .hist-header a:hover {{ color: #58a6ff; }} .back-btn {{ display:inline-block;padding:5px 14px;background:#1c2333;border:1px solid #58a6ff;border-radius:6px;color:#58a6ff;text-decoration:none;font-size:0.85em;margin-top:8px; }} .back-btn:hover {{ background:#1a3a5c; }}
        .hist-body {{
            flex: 1; overflow-y: auto; min-height: 0;
            background: #161b22; border: 1px solid #30363d;
            border-radius: 6px; padding: 16px 20px;
            line-height: 1.8;
        }}
    </style>
</head>
<body>
    <div class="hist-container">
        <div class="hist-header">
            <h1>📜 历史回顾</h1>
            <p style="font-size:0.8em;color:#8b949e;">共 {turn} 轮 · 当前场景: {scene}</p>
            <a href="/" class="back-btn">← 返回游戏</a>
        </div>
        <div class="hist-body">
            {history_html}
        </div>
    </div>
</body>
</html>"""

    return HTMLResponse(page)


@app.get("/reset", response_class=HTMLResponse)
async def reset():
    """Reset the session state to the world's factory defaults."""
    from engine import io_utils
    from fastapi.responses import RedirectResponse

    # Try to restore from factory snapshot (saved at world creation)
    if config.WORLD_INIT_PATH.exists():
        try:
            init = io_utils.read_json(config.WORLD_INIT_PATH)
            io_utils.write_yaml(config.SESSION_STATE_PATH, init["state"])
            io_utils.write_json(config.STORY_GRAPH_PATH, init["graph"])
            io_utils.write_json(config.MEMORY_PATH, init["memory"])
            config.CHAPTER_PATH.write_text("", encoding="utf-8")
            return RedirectResponse(url="/", status_code=303)
        except Exception:
            pass

    # Fallback: hardcoded defaults (only used if no world_init.json exists)
    initial_state = {
        "scene": "回声号 — 舰桥",
        "status": "SETUP",
        "turn": 0,
        "characters": {
            "A": {"name": "林夜", "role": "调查船船长", "level": "L0", "relation": "初识", "note": "冷静、理性，背负过去的秘密"},
            "B": {"name": "艾琳", "role": "考古语言学家", "level": "L0", "relation": "初识", "note": "热情、好奇，对星痕有特殊的感知力"},
        },
        "history": [],
        "force_event_pending": False,
        "chapter": 1,
    }
    io_utils.write_yaml(config.SESSION_STATE_PATH, initial_state)
    initial_graph = {
        "nodes": {"0": {"turn": 0, "text": "初始场景：回声号舰桥", "scene": "回声号 — 舰桥", "status": "SETUP", "choices": {}, "parent": None, "choice_taken": None}},
        "current_node": "0", "edges": [],
    }
    io_utils.write_json(config.STORY_GRAPH_PATH, initial_graph)
    initial_memory = {
        "characters": {
            "林夜": {"trust": 0.5, "flags": [], "relationship": "船长，初识"},
            "艾琳": {"trust": 0.5, "flags": [], "relationship": "考古语言学家，初识"},
        },
        "world_flags": [], "global_trust": 0.5,
    }
    io_utils.write_json(config.MEMORY_PATH, initial_memory)
    config.CHAPTER_PATH.write_text("", encoding="utf-8")
    return RedirectResponse(url="/", status_code=303)


# ── New Story creator ──────────────────────────────────────────────

_PRESETS = {
    "scifi": {
        "title": "星痕纪元",
        "world": "公元2247年，人类已进入星际殖民时代。在银河系边缘的「碎星带」，一艘名为「回声号」的调查船发现了一处远古外星遗迹。遗迹中封存着名为「星痕」的神秘能量。",
        "genre": "科幻 / 冒险 / 情感",
        "scene": "回声号 — 舰桥",
        "char1_name": "林夜", "char1_role": "调查船船长", "char1_note": "冷静、理性，背负过去的秘密",
        "char2_name": "艾琳", "char2_role": "考古语言学家", "char2_note": "热情、好奇，对星痕有特殊的感知力",
    },
    "school": {
        "title": "樱之诗",
        "world": "私立樱丘学园，坐落于沿海小城。春天，樱花如雪般飘落。主人公在开学典礼那天，遇见了改变命运的两个人。",
        "genre": "校园 / 恋爱 / 日常",
        "scene": "樱丘学园 — 校门口樱花道",
        "char1_name": "小樱", "char1_role": "同班同学 / 美术部员", "char1_note": "开朗活泼，有点天然呆，画画天赋极高",
        "char2_name": "雪乃", "char2_role": "学生会长", "char2_note": "冰山美人，成绩顶尖，内心藏着柔软的一面",
    },
    "fantasy": {
        "title": "剑与星辉",
        "world": "艾泽拉大陆，魔法与剑术并存的世界。千年和平被北方出现的「虚空裂隙」打破。王国的冒险者公会正在招募勇者。",
        "genre": "奇幻 / 冒险 / 史诗",
        "scene": "冒险者公会 — 王都大厅",
        "char1_name": "艾莉西亚", "char1_role": "精灵弓箭手", "char1_note": "来自古老森林的精灵族，沉默寡言但箭术无双",
        "char2_name": "雷恩", "char2_role": "流浪骑士", "char2_note": "失去记忆的骑士，剑术高超，追寻自己的过去",
    },
    "mystery": {
        "title": "第七日",
        "world": "现代都市。一连串离奇的失踪案打破了城市的平静。作为私家侦探的主角，在调查中发现所有线索都指向一家名为「第七日」的神秘咖啡馆。",
        "genre": "悬疑 / 都市 / 推理",
        "scene": "第七日咖啡馆 — 深夜",
        "char1_name": "苏晓", "char1_role": "私家侦探", "char1_note": "冷静敏锐，观察力极强，有不愿提及的过去",
        "char2_name": "墨言", "char2_role": "神秘顾客", "char2_note": "总是在同一个位置喝黑咖啡，似乎知道所有答案",
    },
}

_NEW_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>新故事 — Prompt OS Galgame</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: "Segoe UI", "Noto Sans SC", system-ui, sans-serif;
            background: #0d1117; color: #c9d1d9;
            height: 100vh; overflow: hidden; display: flex; flex-direction: column; align-items: center;
        }
        .new-container {
            width: 100%; height: 100%;
            display: flex; flex-direction: column; padding: 16px 20px;
        }
        .new-header {
            text-align: center; flex-shrink: 0;
            padding: 12px 0; border-bottom: 1px solid #30363d; margin-bottom: 12px;
        }
        .new-header h1 { font-size: 1.4em; color: #58a6ff; margin-bottom: 8px; }
        .back-btn { display:inline-block;padding:6px 16px;background:#1c2333;border:1px solid #58a6ff;border-radius:6px;color:#58a6ff;text-decoration:none;font-size:0.85em;transition:all 0.15s; }
        .back-btn:hover { background:#1a3a5c;color:#79c0ff; }
        .new-body {
            flex: 1; overflow-y: auto; min-height: 0;
        }
        .new-body label {
            display: block; color: #8b949e; font-size: 0.85em; margin: 12px 0 4px;
        }
        .new-body input, .new-body textarea, .new-body select {
            width: 100%; padding: 8px 12px;
            background: #161b22; border: 1px solid #30363d;
            border-radius: 6px; color: #c9d1d9; font-size: 0.9em;
            font-family: inherit;
        }
        .new-body input:focus, .new-body textarea:focus, .new-body select:focus {
            outline: none; border-color: #58a6ff;
        }
        .new-body textarea { resize: vertical; min-height: 60px; }
        .new-body .row { display: flex; gap: 12px; }
        .new-body .row > div { flex: 1; }
        .new-body button {
            width: 100%; margin-top: 16px; padding: 12px;
            background: #238636; border: none; border-radius: 8px;
            color: #fff; font-size: 1em; cursor: pointer;
            font-weight: bold; transition: all 0.15s;
        }
        .new-body button:hover { background: #2ea043; }
        .kw-section {{
            background: #161b22; border: 1px solid #30363d;
            border-radius: 8px; padding: 12px 16px; margin-bottom: 12px;
        }}
        .kw-section label {{
            display: block; color: #8b949e; font-size: 0.85em; margin-bottom: 6px;
        }}
        .kw-section input {{
            padding: 8px 12px; background: #0d1117; border: 1px solid #30363d;
            border-radius: 6px; color: #c9d1d9; font-size: 0.9em;
            font-family: inherit;
        }}
        .kw-section input:focus {{ outline: none; border-color: #58a6ff; }}
        .kw-section .btn-save {{
            padding: 8px 16px; background: #238636; color: #fff;
            border: none; border-radius: 6px; font-size: 0.9em;
            cursor: pointer; font-weight: bold;
        }}
        .kw-section .btn-save:hover {{ background: #2ea043; }}
        .kw-section .btn-save:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        .kw-section .hint {{ color: #8b949e; font-size: 0.75em; }}
        .preset-bar {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }}
        .preset-btn {
            padding: 5px 14px; background: #1c2333; border: 1px solid #30363d;
            border-radius: 16px; color: #8b949e; font-size: 0.8em; cursor: pointer;
            transition: all 0.15s;
        }
        .preset-btn:hover { border-color: #58a6ff; color: #58a6ff; }
        .preset-btn.active { background: #1a3a5c; border-color: #58a6ff; color: #58a6ff; }
    </style>
</head>
<body>
    <div class="new-container">
        <div class="new-header">
            <h1>🆕 创建新故事</h1>
            <a href="/" class="back-btn">← 返回游戏</a>
        </div>
        <div class="new-body">
            <div class="kw-section">
                <label>💡 AI 关键词生成</label>
                <div style="display:flex;gap:8px;">
                    <input id="kw_input" placeholder="输入关键词，如：修仙 宗门 重生 师徒" style="flex:1">
                    <button type="button" class="btn btn-save" onclick="generateWorld()" style="flex-shrink:0;">✨ 生成</button>
                </div>
                <div class="hint" id="kw_status" style="margin-top:4px;min-height:18px;"></div>
            </div>

            <div class="preset-bar" id="presets">
                <button class="preset-btn active" onclick="loadPreset('scifi',this)">🚀 科幻</button>
                <button class="preset-btn" onclick="loadPreset('school',this)">🌸 校园恋爱</button>
                <button class="preset-btn" onclick="loadPreset('fantasy',this)">⚔️ 奇幻冒险</button>
                <button class="preset-btn" onclick="loadPreset('mystery',this)">🔍 都市悬疑</button>
                <button class="preset-btn" onclick="loadPreset('custom',this)">✨ 自定义</button>
            </div>
            <form method="post" action="/new">
                <label>📖 故事标题</label>
                <input name="title" id="f_title" value="星痕纪元" required>
                <label>🌍 世界观 / 背景</label>
                <textarea name="world" id="f_world" required>公元2247年，人类已进入星际殖民时代……</textarea>
                <label>🎭 类型 / 风格</label>
                <input name="genre" id="f_genre" value="科幻 / 冒险 / 情感">
                <label>📍 初始场景</label>
                <input name="scene" id="f_scene" value="回声号 — 舰桥" required>
                <div class="row">
                    <div>
                        <label>👤 主角</label>
                        <input name="char1_name" id="f_c1n" value="林夜" placeholder="姓名" required>
                        <input name="char1_role" id="f_c1r" value="调查船船长" placeholder="身份" style="margin-top:4px">
                        <input name="char1_note" id="f_c1t" value="冷静、理性，背负过去的秘密" placeholder="性格描述" style="margin-top:4px">
                    </div>
                    <div>
                        <label>👤 角色B</label>
                        <input name="char2_name" id="f_c2n" value="艾琳" placeholder="姓名" required>
                        <input name="char2_role" id="f_c2r" value="考古语言学家" placeholder="身份" style="margin-top:4px">
                        <input name="char2_note" id="f_c2t" value="热情、好奇，对星痕有特殊的感知力" placeholder="性格描述" style="margin-top:4px">
                    </div>
                </div>
                <div class="rules-section" style="margin-top:12px;">
                    <label>🎨 故事专属规则（可选）</label>
                    <button type="button" class="btn-ai" onclick="generateRules()" id="rulesBtn">
                        ✨ AI 生成专属规则
                    </button>
                    <div id="rulesPreview" style="margin-top:8px;font-size:0.8em;color:#8b949e;min-height:20px;"></div>
                    <input type="hidden" name="custom_rules" id="customRulesInput" value="">
                </div>
                <button type="submit">🎬 开始新故事</button>
            </form>
        </div>
    </div>
    <script>
        const presets = """ + json.dumps(_PRESETS, ensure_ascii=False) + """;
        function loadPreset(key, btn) {
            document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            if (key === 'custom') return;
            const p = presets[key];
            document.getElementById('f_title').value = p.title;
            document.getElementById('f_world').value = p.world;
            document.getElementById('f_genre').value = p.genre;
            document.getElementById('f_scene').value = p.scene;
            document.getElementById('f_c1n').value = p.char1_name;
            document.getElementById('f_c1r').value = p.char1_role;
            document.getElementById('f_c1t').value = p.char1_note;
            document.getElementById('f_c2n').value = p.char2_name;
            document.getElementById('f_c2r').value = p.char2_role;
            document.getElementById('f_c2t').value = p.char2_note;
        }

        async function generateRules() {
            const title = document.getElementById('f_title').value;
            const world = document.getElementById('f_world').value;
            const genre = document.getElementById('f_genre').value;
            const c1n = document.getElementById('f_c1n').value;
            const c1r = document.getElementById('f_c1r').value;
            const c2n = document.getElementById('f_c2n').value;
            const c2r = document.getElementById('f_c2r').value;
            const preview = document.getElementById('rulesPreview');
            const btn = document.getElementById('rulesBtn');
            preview.textContent = '⏳ 正在生成专属规则…';
            preview.style.color = '#ffa657';
            btn.disabled = true;
            try {
                const params = new URLSearchParams({title,world,genre,char1_name:c1n,char1_role:c1r,char2_name:c2n,char2_role:c2r});
                const res = await fetch('/generate-rules', {method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:params});
                const data = await res.json();
                if (data.error) { preview.textContent = '❌ '+data.error; preview.style.color='#f85149'; }
                else {
                    document.getElementById('customRulesInput').value = JSON.stringify(data);
                    const stats = (data.stats||[]).map(s=>s.label).join(' · ');
                    const stages = (data.stages||[]).join(' → ');
                    preview.innerHTML = '<span style="color:#7ee787;">✅ 已生成</span><br>追踪维度: <b style="color:#ffa657;">'+stats+'</b><br>关系阶段: <b style="color:#d2a8ff;">'+stages+'</b>';
                }
            } catch(e) { preview.textContent = '❌ '+e.message; preview.style.color='#f85149'; }
            btn.disabled = false;
        }

        async function generateWorld() {
            const kw = document.getElementById('kw_input').value.trim();
            const status = document.getElementById('kw_status');
            const btn = document.querySelector('.kw-section .btn-save');
            if (!kw) { status.textContent = '请输入关键词'; status.style.color = '#f85149'; return; }
            status.textContent = '⏳ AI 正在生成世界观…';
            status.style.color = '#ffa657';
            btn.disabled = true;
            try {
                const res = await fetch('/generate-world', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: 'keywords=' + encodeURIComponent(kw)
                });
                const data = await res.json();
                if (data.error) {
                    status.textContent = '❌ ' + data.error; status.style.color = '#f85149';
                } else {
                    document.getElementById('f_title').value = data.title || '';
                    document.getElementById('f_world').value = data.world || '';
                    document.getElementById('f_genre').value = data.genre || '';
                    document.getElementById('f_scene').value = data.scene || '';
                    document.getElementById('f_c1n').value = data.char1_name || '';
                    document.getElementById('f_c1r').value = data.char1_role || '';
                    document.getElementById('f_c1t').value = data.char1_note || '';
                    document.getElementById('f_c2n').value = data.char2_name || '';
                    document.getElementById('f_c2r').value = data.char2_role || '';
                    document.getElementById('f_c2t').value = data.char2_note || '';
                    document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
                    status.textContent = '✅ 已生成！检查并修改后点击「开始新故事」';
                    status.style.color = '#7ee787';
                }
            } catch(e) {
                status.textContent = '❌ 网络错误：' + e.message; status.style.color = '#f85149';
            }
            btn.disabled = false;
        }
    </script>
</body>
</html>"""


@app.get("/new", response_class=HTMLResponse)
async def new_story_page():
    """Show the new story creation form."""
    return HTMLResponse(_NEW_PAGE)


@app.post("/new", response_class=HTMLResponse)
async def create_new_story(
    title: str = Form(...),
    world: str = Form(...),
    genre: str = Form(""),
    scene: str = Form(...),
    char1_name: str = Form(...),
    char1_role: str = Form(""),
    char1_note: str = Form(""),
    char2_name: str = Form(...),
    char2_role: str = Form(""),
    char2_note: str = Form(""),
    custom_rules: str = Form(""),
):
    """Process the new story form and initialize all state."""
    import yaml

    # Parse custom rules if provided
    custom = {}
    if custom_rules.strip():
        try:
            custom = json.loads(custom_rules.strip())
        except Exception:
            pass

    # Build world_pack.yaml
    world_pack = {
        "world": {
            "title": title,
            "genre": genre,
            "era": "故事开端",
            "setting": world,
            "factions": [],
            "locations": [
                {"name": scene, "desc": "初始场景"},
            ],
            "tone": "聚焦人物情感与选择",
            "themes": [],
        }
    }
    if custom:
        world_pack["custom"] = custom
    io_utils.write_yaml(config.WORLD_PACK_PATH, world_pack)

    # Build initial state
    initial_state = {
        "scene": scene,
        "status": "SETUP",
        "turn": 0,
        "characters": {
            "A": {
                "name": char1_name,
                "role": char1_role,
                "level": "L0",
                "relation": "初识",
                "note": char1_note,
            },
            "B": {
                "name": char2_name,
                "role": char2_role,
                "level": "L0",
                "relation": "初识",
                "note": char2_note,
            },
        },
        "history": [],
        "force_event_pending": False,
        "chapter": 1,
    }
    io_utils.write_yaml(config.SESSION_STATE_PATH, initial_state)

    # Reset chapter
    config.CHAPTER_PATH.write_text("", encoding="utf-8")

    # Reset story graph
    initial_graph = {
        "nodes": {
            "0": {
                "turn": 0,
                "text": f"初始场景：{scene}",
                "scene": scene,
                "status": "SETUP",
                "choices": {},
                "parent": None,
                "choice_taken": None,
            }
        },
        "current_node": "0",
        "edges": [],
    }
    io_utils.write_json(config.STORY_GRAPH_PATH, initial_graph)

    # Reset memory
    initial_memory = {
        "characters": {
            char1_name: {"trust": 0.5, "flags": [], "relationship": f"{char1_role}，初识"},
            char2_name: {"trust": 0.5, "flags": [], "relationship": f"{char2_role}，初识"},
        },
        "world_flags": [],
        "global_trust": 0.5,
    }
    io_utils.write_json(config.MEMORY_PATH, initial_memory)

    # Save factory-reset snapshot so reset() can restore the user's world
    io_utils.write_json(config.WORLD_INIT_PATH, {
        "state": initial_state,
        "graph": initial_graph,
        "memory": initial_memory,
    })

    # Redirect to main page
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/", status_code=303)


# ── AI World Generator ─────────────────────────────────────────────

@app.post("/generate-world")
async def generate_world(keywords: str = Form("")):
    """Generate a world setting from keywords using DeepSeek."""
    from fastapi.responses import JSONResponse
    from engine.deepseek_client import call_deepseek, DeepSeekError

    kw = keywords.strip()
    if not kw:
        return JSONResponse({"error": "请输入关键词"}, status_code=400)

    system = "你是一个 Galgame 世界观生成器。根据用户提供的关键词，生成完整的中文 Galgame 世界观设定。只输出合法 JSON，不要输出其他内容。"
    user = f"""关键词：{kw}

请根据这些关键词，生成一个完整的 Galgame 世界观设定。输出必须是合法的 JSON：

{{
  "title": "故事标题（8字以内）",
  "world": "世界观/背景描述（150-300字，吸引人的叙事风格）",
  "genre": "类型标签（如：修仙/悬疑/恋爱/奇幻，用 / 分隔）",
  "scene": "初始场景/地点名称",
  "char1_name": "主角姓名",
  "char1_role": "主角身份",
  "char1_note": "主角性格描述（15-30字）",
  "char2_name": "第二角色姓名",
  "char2_role": "第二角色身份",
  "char2_note": "第二角色性格描述（15-30字）"
}}

要求：
1. 世界观要有创意和吸引力，能在150-300字内建立独特的设定
2. 两个角色之间要有潜在的戏剧冲突或情感张力
3. 初始场景要具体、有画面感
4. 所有文字用中文
5. 只输出JSON，不要输出markdown代码块或其他文字"""

    try:
        result = call_deepseek(system, user, temperature=0.9, max_tokens=1024)
        return JSONResponse(result)
    except DeepSeekError as exc:
        return JSONResponse({"error": f"AI 生成失败: {exc}"}, status_code=500)
    except Exception as exc:
        return JSONResponse({"error": f"未知错误: {exc}"}, status_code=500)


# ── NPC Management ────────────────────────────────────────────────

_NPC_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>角色管理 — Prompt OS Galgame</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: "Segoe UI", "Noto Sans SC", system-ui, sans-serif;
            background: #0d1117; color: #c9d1d9;
            height: 100vh; overflow: hidden; display: flex; flex-direction: column; align-items: center;
        }
        .npc-container {
            width: 100%; height: 100%;
            display: flex; flex-direction: column; padding: 16px 20px;
        }
        .npc-header {
            text-align: center; flex-shrink: 0;
            padding: 12px 0; border-bottom: 1px solid #30363d; margin-bottom: 12px;
        }
        .npc-header h1 { font-size: 1.3em; color: #58a6ff; margin-bottom: 8px; }
        .back-btn { display:inline-block;padding:6px 16px;background:#1c2333;border:1px solid #58a6ff;border-radius:6px;color:#58a6ff;text-decoration:none;font-size:0.85em;transition:all 0.15s; }
        .back-btn:hover { background:#1a3a5c;color:#79c0ff; }
        .npc-body { flex: 1; overflow-y: auto; min-height: 0; }
        .npc-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; }
        .npc-card {
            background: #161b22; border: 1px solid #30363d;
            border-radius: 8px; padding: 14px 16px; position: relative;
        }
        .npc-card .tag {
            display: inline-block; padding: 1px 6px; border-radius: 3px;
            font-size: 0.7em; margin-left: 6px; vertical-align: middle;
        }
        .npc-card .tag.main { background: #1a3a5c; color: #58a6ff; }
        .npc-card .tag.npc { background: #3d2a1a; color: #ffa657; }
        .npc-card .name { font-weight: bold; color: #d2a8ff; font-size: 1.05em; }
        .npc-card .role { color: #8b949e; font-size: 0.85em; margin: 4px 0; }
        .npc-card .note { color: #c9d1d9; font-size: 0.82em; line-height: 1.5; margin-top: 6px; }
        .npc-card .level { color: #ffa657; font-size: 0.8em; }
        .npc-card .trust { color: #7ee787; font-size: 0.8em; }
        .npc-card .del-btn {
            position: absolute; top: 8px; right: 10px;
            background: none; border: none; color: #484f58;
            font-size: 1em; cursor: pointer;
        }
        .npc-card .del-btn:hover { color: #f85149; }
        .add-section {
            background: #161b22; border: 1px solid #30363d;
            border-radius: 8px; padding: 14px 16px; margin-bottom: 14px;
        }
        .add-section label { display: block; color: #8b949e; font-size: 0.85em; margin: 6px 0 3px; }
        .add-section input, .add-section textarea {
            width: 100%; padding: 6px 10px;
            background: #0d1117; border: 1px solid #30363d;
            border-radius: 4px; color: #c9d1d9; font-size: 0.85em;
            font-family: inherit;
        }
        .add-section input:focus, .add-section textarea:focus { outline: none; border-color: #58a6ff; }
        .add-section textarea { resize: vertical; min-height: 40px; }
        .add-section .btn-row { display: flex; gap: 8px; margin-top: 10px; }
        .add-section button {
            padding: 7px 16px; border-radius: 6px; font-size: 0.85em;
            cursor: pointer; border: none; font-weight: bold;
        }
        .btn-add { background: #238636; color: #fff; }
        .btn-add:hover { background: #2ea043; }
        .btn-ai { background: #1a3a5c; color: #58a6ff; border: 1px solid #58a6ff; }
        .btn-ai:hover { background: #1f4a73; }
        .btn-ai:disabled { opacity: 0.5; cursor: not-allowed; }
        .ai-row { display: flex; gap: 8px; margin-top: 4px; }
        .ai-row input { flex: 1; }
    </style>
</head>
<body>
    <div class="npc-container">
        <div class="npc-header">
            <h1>👥 角色管理</h1>
            <a href="/" class="back-btn">← 返回游戏</a>
        </div>
        <div class="npc-body">
            <div class="add-section">
                <label>✨ AI 生成 NPC（输入关键词或描述）</label>
                <div class="ai-row">
                    <input id="ai_kw" placeholder="如：神秘商人 情报贩子 亦正亦邪">
                    <button class="btn-ai" id="ai_btn" onclick="generateNPC()">🤖 AI 生成</button>
                </div>
                <div id="ai_status" style="font-size:0.75em;color:#8b949e;margin-top:4px;min-height:18px;"></div>
                <label>或手动添加</label>
                <form method="post" action="/npcs/add">
                    <input name="name" placeholder="姓名" required>
                    <input name="role" placeholder="身份" style="margin-top:4px;">
                    <input name="note" placeholder="性格 / 背景描述" style="margin-top:4px;">
                    <div class="btn-row">
                        <button class="btn-add" type="submit">➕ 添加角色</button>
                    </div>
                </form>
            </div>
            <div class="npc-grid">
                {{NPC_CARDS}}
            </div>
        </div>
    </div>
    <script>
        async function generateNPC() {
            const kw = document.getElementById('ai_kw').value.trim();
            const status = document.getElementById('ai_status');
            const btn = document.getElementById('ai_btn');
            if (!kw) { status.textContent = '请输入描述'; status.style.color = '#f85149'; return; }
            status.textContent = '⏳ AI 正在生成角色…'; status.style.color = '#ffa657';
            btn.disabled = true;
            try {
                const res = await fetch('/npcs/generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: 'keywords=' + encodeURIComponent(kw)
                });
                const data = await res.json();
                if (data.error) {
                    status.textContent = '❌ ' + data.error; status.style.color = '#f85149';
                } else {
                    status.textContent = '✅ 已创建: ' + data.name;
                    status.style.color = '#7ee787';
                    setTimeout(() => location.reload(), 800);
                }
            } catch(e) {
                status.textContent = '❌ ' + e.message; status.style.color = '#f85149';
            }
            btn.disabled = false;
        }
    </script>
</body>
</html>"""


@app.get("/npcs", response_class=HTMLResponse)
async def npc_page():
    """Show all characters with management options."""
    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    except Exception:
        state = {}

    chars = state.get("characters", {})
    if not chars:
        cards = '<p style="color:#8b949e;text-align:center;padding:40px;">尚无角色，请添加</p>'
    else:
        cards_list = []
        for key, c in chars.items():
            is_main = key in ("A", "B")
            tag = '<span class="tag main">主角</span>' if is_main else '<span class="tag npc">NPC</span>'
            del_btn = '' if is_main else '<a class="del-btn" href="/npcs/delete?key=' + key + '" onclick="return confirm(&quot;delete ' + c.get('name', key) + '?&quot;)" title="delete">X</a>'
            cards_list.append(
                f'<div class="npc-card">'
                f'{del_btn}'
                f'<div class="name">{c.get("name", key)}{tag}</div>'
                f'<div class="role">{c.get("role", "")}</div>'
                f'<div class="level">⭐ {c.get("level", "L0")}</div>'
                f'<div class="trust">🤝 {c.get("relation", "初识")}</div>'
                f'<div class="note">{c.get("note", "")}</div>'
                f'</div>'
            )
        cards = "\n".join(cards_list)

    page = _NPC_PAGE.replace("{{NPC_CARDS}}", cards)
    return HTMLResponse(page)


@app.post("/npcs/add", response_class=HTMLResponse)
async def add_npc_manual(
    name: str = Form(...),
    role: str = Form(""),
    note: str = Form(""),
):
    """Manually add a new NPC."""
    from fastapi.responses import RedirectResponse

    state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    chars = state.get("characters", {})

    # Find next available key
    existing = set(chars.keys())
    next_key = "C"
    while next_key in existing:
        next_key = chr(ord(next_key) + 1)

    chars[next_key] = {
        "name": name.strip(),
        "role": role.strip(),
        "level": "L0",
        "relation": "初识",
        "note": note.strip(),
        "is_npc": True,
    }
    state["characters"] = chars
    io_utils.write_yaml(config.SESSION_STATE_PATH, state)

    # Also add to memory
    mem = load_memory()
    mem.setdefault("characters", {})[name.strip()] = {
        "trust": 0.5, "flags": [], "relationship": f"{role.strip()}，初识"
    }
    from engine.memory import save_memory
    save_memory(mem)

    return RedirectResponse(url="/npcs", status_code=303)


@app.get("/npcs/delete", response_class=HTMLResponse)
async def delete_npc(key: str = Query(...)):
    """Delete an NPC (not main characters A/B)."""
    from fastapi.responses import RedirectResponse

    if key in ("A", "B"):
        return RedirectResponse(url="/npcs", status_code=303)

    state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    chars = state.get("characters", {})
    if key in chars:
        chars.pop(key)
        state["characters"] = chars
        io_utils.write_yaml(config.SESSION_STATE_PATH, state)
    return RedirectResponse(url="/npcs", status_code=303)


@app.post("/npcs/generate")
async def generate_npc(keywords: str = Form("")):
    """Generate a new NPC from keywords using DeepSeek."""
    from fastapi.responses import JSONResponse
    from engine.deepseek_client import call_deepseek, DeepSeekError

    kw = keywords.strip()
    if not kw:
        return JSONResponse({"error": "请输入描述"}, status_code=400)

    # Get world context
    try:
        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
        world_title = world_pack.get("world", {}).get("title", "")
        world_setting = world_pack.get("world", {}).get("setting", "")
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
        existing_chars = state.get("characters", {})
        existing_names = ", ".join(c.get("name", k) for k, c in existing_chars.items())
    except Exception:
        world_title = ""
        world_setting = ""
        existing_names = ""

    system = "你是一个 Galgame 角色生成器。根据世界观和关键词，生成一个合适的NPC角色。只输出合法JSON。"
    user = f"""当前世界观：{world_title}
背景：{world_setting}
已有角色：{existing_names}
关键词描述：{kw}

请生成一个新NPC角色，输出JSON：
{{
  "name": "角色名（2-4字中文名）",
  "role": "身份/职业",
  "note": "性格和外貌描述（20-40字）"
}}

要求：角色要符合世界观设定，与已有角色不重复，有独特的性格特点。只输出JSON。"""

    try:
        result = call_deepseek(system, user, temperature=0.9, max_tokens=512)

        # Auto-add to state + memory
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
        chars = state.get("characters", {})
        existing = set(chars.keys())
        next_key = "C"
        while next_key in existing:
            next_key = chr(ord(next_key) + 1)

        name = result.get("name", "未命名")
        role = result.get("role", "")
        note = result.get("note", "")

        chars[next_key] = {
            "name": name,
            "role": role,
            "level": "L0",
            "relation": "初识",
            "note": note,
            "is_npc": True,
        }
        state["characters"] = chars
        io_utils.write_yaml(config.SESSION_STATE_PATH, state)

        mem = load_memory()
        mem.setdefault("characters", {})[name] = {
            "trust": 0.5, "flags": [], "relationship": f"{role}，初识"
        }
        from engine.memory import save_memory
        save_memory(mem)

        return JSONResponse({"name": name, "role": role, "note": note, "key": next_key})
    except DeepSeekError as exc:
        return JSONResponse({"error": f"AI 生成失败: {exc}"}, status_code=500)


# ── Custom Rules Generator ─────────────────────────────────────────

@app.post("/generate-rules")
async def generate_rules(
    title: str = Form(""),
    world: str = Form(""),
    genre: str = Form(""),
    char1_name: str = Form(""),
    char1_role: str = Form(""),
    char2_name: str = Form(""),
    char2_role: str = Form(""),
):
    """Generate story-specific custom tracking rules."""
    from fastapi.responses import JSONResponse
    from engine.deepseek_client import call_deepseek, DeepSeekError

    system = "你是 Galgame 规则设计师。根据故事设定生成专属的角色追踪维度。只输出合法JSON。"
    user = f"""故事标题：{title}
类型：{genre}
世界观：{world}
角色1：{char1_name}（{char1_role}）
角色2：{char2_name}（{char2_role}）

请为这个故事设计 2-3 个专属的角色追踪维度（替代通用的"好感度"）。
例如：
- 宫廷故事 → 忠诚度、权势、民心
- 修仙故事 → 修为、道心、羁绊
- 商战故事 → 信任度、影响力、筹码

同时设计 5-7 个关系阶段标签（替代通用的"陌生→朋友→恋人"）。

输出 JSON：
{{
  "stats": [
    {{"key": "loyalty", "label": "忠诚度", "max": 100}},
    {{"key": "power", "label": "权势", "max": 100}}
  ],
  "stages": ["陌路", "相识", "君臣", "心腹", "托付"]
}}

要求：
1. stat.key 用英文（loyalty/power等），label 用中文
2. 每个 stat 有 max 值（建议 100）
3. stages 5-7 个，从疏远到亲密递进
4. 维度要贴合故事背景，有创意
5. 只输出 JSON"""

    try:
        result = call_deepseek(system, user, temperature=0.9, max_tokens=512)
        return JSONResponse(result)
    except DeepSeekError as exc:
        return JSONResponse({"error": f"AI 生成失败: {exc}"}, status_code=500)


# ── Settings / API Key ─────────────────────────────────────────────

_SETTINGS_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>设置 — Prompt OS Galgame</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: "Segoe UI", "Noto Sans SC", system-ui, sans-serif;
            background: #0d1117; color: #c9d1d9;
            height: 100vh; overflow: hidden; display: flex; flex-direction: column; align-items: center;
        }
        .set-container {
            max-width: 700px; width: 100%; padding: 32px 20px;
        }
        .set-header {
            text-align: center; padding: 12px 0;
            border-bottom: 1px solid #30363d; margin-bottom: 20px;
        }
        .set-header h1 { font-size: 1.3em; color: #58a6ff; margin-bottom: 8px; }
        .back-btn { display:inline-block;padding:6px 16px;background:#1c2333;border:1px solid #58a6ff;border-radius:6px;color:#58a6ff;text-decoration:none;font-size:0.85em;transition:all 0.15s; }
        .back-btn:hover { background:#1a3a5c;color:#79c0ff; }
        .set-card {
            background: #161b22; border: 1px solid #30363d;
            border-radius: 8px; padding: 20px 24px; margin-bottom: 16px;
        }
        .set-card label {
            display: block; color: #8b949e; font-size: 0.85em; margin-bottom: 6px;
        }
        .set-card input {
            width: 100%; padding: 10px 14px;
            background: #0d1117; border: 1px solid #30363d;
            border-radius: 6px; color: #c9d1d9; font-size: 0.9em;
            font-family: monospace;
        }
        .set-card input:focus { outline: none; border-color: #58a6ff; }
        .set-card .hint {
            color: #484f58; font-size: 0.75em; margin-top: 6px;
        }
        .set-card .status {
            margin-top: 8px; font-size: 0.85em;
        }
        .set-card .status.ok { color: #7ee787; }
        .set-card .status.empty { color: #f85149; }
        .btn-row { display: flex; gap: 10px; margin-top: 12px; }
        .btn {
            padding: 8px 20px; border-radius: 6px; font-size: 0.9em;
            cursor: pointer; border: none; font-weight: bold;
        }
        .btn-save { background: #238636; color: #fff; }
        .btn-save:hover { background: #2ea043; }
        .btn-clear { background: #3d1a1a; color: #f85149; border: 1px solid #da3633; }
        .btn-clear:hover { background: #4d2020; }
    </style>
</head>
<body>
    <div class="set-container">
        <div class="set-header">
            <h1>⚙️ 设置</h1>
            <a href="/" class="back-btn">← 返回游戏</a>
        </div>
        <form class="set-card" method="post" action="/settings">
            <label>🔑 DeepSeek API Key</label>
            <input name="api_key" type="password" id="keyInput"
                   placeholder="sk-xxxxxxxxxxxxxxxx"
                   value="{{CURRENT_KEY}}">
            <div class="hint">Key 仅存储在本地 <code>data/apikey.json</code>，不会上传</div>
            <label style="margin-top:14px;">🧠 模型选择</label>
            <select name="model" id="modelSelect" style="width:100%;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:0.9em;">
                {{MODEL_OPTIONS}}
            </select>
            <div class="hint">{{MODEL_HINT}}</div>
            <label style="margin-top:14px;">📝 每轮字数</label>
            <input name="story_length" type="number" min="300" max="3000" step="100"
                   value="{{STORY_LENGTH}}" style="width:120px;">
            <div class="hint">AI 每轮生成的文字量（300–3000），默认 1000。对首次开篇也有影响。</div>
            <div class="status {{STATUS_CLASS}}">{{STATUS_TEXT}}</div>
            <div class="btn-row">
                <button class="btn btn-save" type="submit">💾 保存</button>
                <button class="btn btn-clear" type="button"
                        onclick="if(confirm('确定要清除已保存的 API Key？')){fetch('/settings/clear',{method:'POST'}).then(()=>location.reload())}">
                    🗑️ 清除
                </button>
            </div>
        </form>
    </div>
</body>
</html>"""


@app.get("/settings", response_class=HTMLResponse)
async def settings_page():
    """Show API key settings page."""
    key = config.DEEPSEEK_API_KEY
    masked = ""
    if key:
        masked = key[:8] + "…" + key[-4:] if len(key) > 12 else "***"

    status_class = "ok" if key else "empty"
    status_text = f"✅ 已配置 ({masked})" if key else "❌ 未设置 — 请在下方输入 API Key"

    # Model options
    current_model = config.DEEPSEEK_MODEL
    model_opts = []
    model_hint = ""
    for mid, mlabel in AVAILABLE_MODELS.items():
        sel = ' selected' if mid == current_model else ''
        model_opts.append(f'<option value="{mid}"{sel}>{mlabel}</option>')
        if mid == current_model:
            model_hint = f"当前: {mlabel}"
    if not model_hint:
        model_hint = "当前: V4-Flash（默认）"

    page = (
        _SETTINGS_PAGE
        .replace("{{CURRENT_KEY}}", key)
        .replace("{{STATUS_CLASS}}", status_class)
        .replace("{{STATUS_TEXT}}", status_text)
        .replace("{{MODEL_OPTIONS}}", "\n".join(model_opts))
        .replace("{{MODEL_HINT}}", model_hint)
        .replace("{{STORY_LENGTH}}", str(config.STORY_LENGTH))
    )
    return HTMLResponse(page)


@app.post("/settings", response_class=HTMLResponse)
async def save_settings(api_key: str = Form(""), model: str = Form("deepseek-chat"), story_length: int = Form(1500)):
    """Save API key, model, and story length."""
    key = api_key.strip()
    if key:
        save_api_key(key)
        reload_api_key()
    if model in AVAILABLE_MODELS:
        save_model(model)
        reload_model()
    length = max(300, min(3000, story_length))
    save_story_length(length)
    reload_story_length()
    return await settings_page()


@app.post("/settings/clear", response_class=HTMLResponse)
async def clear_settings():
    """Clear the stored API key."""
    clear_api_key()
    reload_api_key()
    return await settings_page()


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Analytics dashboard with toggleable panels — uses unified engine."""
    from engine.dashboard import build_html, ensure_local_js
    ensure_local_js()
    html = build_html()
    # Rewrite local paths for web serving
    html = html.replace('./mermaid.min.js', '/static/mermaid.min.js')
    html = html.replace('./chart.umd.min.js', '/static/chart.umd.min.js')
    return HTMLResponse(html)


@app.get("/export")
async def export_obsidian():
    """Export the full story as Obsidian Markdown and return it for download."""
    from ui.obsidian_export import export_full_story
    path = export_full_story()
    return FileResponse(
        path=path,
        media_type="text/markdown",
        filename="星痕纪元_完整叙事.md",
    )


# ── Helpers ────────────────────────────────────────────────────────


