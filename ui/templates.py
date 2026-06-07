# Auto-generated from web_app.py split — HTML template constants
# See ui/web_app.py for the original monolithic file.

import json


def _escape_html(text: str) -> str:
    """HTML-entity-escape user/AI-driven text to prevent XSS injection.

    Replaces &, <, >, " with their named entities.  Safe to call on
    already-escaped text (idempotent for the common case).
    """
    if not isinstance(text, str):
        return str(text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{{TITLE}} — Galgame Runtime</title>
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
            margin: 0 auto 10px;
            max-width: 100%; width: 100%;
            font-size: 0.82em; flex-wrap: wrap;
        }
        body.wide-layout .state-panel,
        body.wide-layout .story-block,
        body.wide-layout .options,
        body.wide-layout .custom-choice,
        body.wide-layout .toolbar { max-width: none; }
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
            margin: 0 auto 10px;
            max-width: 100%; width: 100%;
            line-height: 1.9;
            font-size: 1.05em;
            white-space: pre-wrap;
        }
        .options {
            display: flex; flex-shrink: 0;
            flex-direction: column;
            gap: 8px;
            margin: 0 auto 10px;
            max-width: 100%; width: 100%;
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
            margin: 0 auto 8px;
            max-width: 100%; width: 100%;
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
            margin: 0 auto 4px;
            max-width: 100%; width: 100%; justify-content: center;
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

            <div class="state-panel">{{STATE_ROW}} <span id="widthToggle" onclick="toggleWidth()" title="切换宽屏/窄屏阅读模式" style="display:inline-block;width:20px;height:20px;line-height:18px;text-align:center;border:1px solid #30363d;border-radius:4px;color:#8b949e;cursor:pointer;font-size:0.7em;margin-left:4px;flex-shrink:0;user-select:none">↔</span> <span id="connDot" style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#484f58;margin-left:2px;flex-shrink:0" title="连接状态"></span></div>

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



        // ── Width toggle ──
        function toggleWidth(){
            var wide = document.body.classList.toggle('wide-layout');
            localStorage.setItem('wideLayout', wide ? '1' : '0');
            var btn = document.getElementById('widthToggle');
            btn.style.color = wide ? '#58a6ff' : '#8b949e';
            btn.style.borderColor = wide ? '#58a6ff' : '#30363d';
        }
        if(localStorage.getItem('wideLayout') === '1'){
            document.body.classList.add('wide-layout');
            var btn = document.getElementById('widthToggle');
            if(btn){ btn.style.color = '#58a6ff'; btn.style.borderColor = '#58a6ff'; }
        }

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
        window.addEventListener('beforeunload', function(e){
            if(sessionStorage.getItem('internalNav') === '1') return;
            try { navigator.sendBeacon('/shutdown'); } catch(ex) {}
            e.preventDefault();
            e.returnValue = '';
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
            name = _escape_html(cs.get("name", ""))
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
                f'<div class="cw-name">{_escape_html(cs["name"])}</div>'
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
        .replace("{{STORY}}", _escape_html(story) if story else "点击下方按钮开始故事…")
        .replace("{{OPTIONS}}", options_html)
        .replace("{{STATE_ROW}}", state_row_html)
        .replace("{{SIDEBAR}}", sidebar_html)
        .replace("{{ERROR}}", _escape_html(error) if error else "")
        .replace("{{TITLE}}", _escape_html(title) if title else "Galgame")
        .replace("{{SUBTITLE}}", _escape_html(subtitle) if subtitle else "AI Narrative Engine")
    )


_PRESETS = {
    "scifi": {
        "title": "星痕纪元",
        "world": "公元2247年，人类已进入星际殖民时代。在银河系边缘的「碎星带」，一艘名为「回声号」的调查船发现了一处远古外星遗迹。遗迹中封存着名为「星痕」的神秘能量。",
        "genre": ["科幻", "冒险", "情感"],
        "scene": "回声号 — 舰桥",
        "main_goal": "调查星痕遗迹的真相",
        "characters": [
            {"name": "林夜", "isMain": True, "role_tags": ["调查船船长", "退役军人"], "personality_tags": ["冷静", "理性", "内敛", "有责任感"], "appearance": "短发，眼神锐利，常穿深色作战服", "relationship": [], "goal": "寻找星痕背后的真相", "secret": "", "background": "曾参与第七远征舰队", "special_ability": "星痕感知"},
            {"name": "艾琳", "isMain": False, "role_tags": ["考古语言学家"], "personality_tags": ["热情", "好奇", "冲动", "敏锐"], "appearance": "金色长发，碧绿色眼睛", "relationship": ["工作伙伴"], "goal": "破解星痕文字", "secret": "能够听见遗迹中的低语", "background": "", "special_ability": ""}
        ],
        "rel_stages": ["陌生", "熟悉", "朋友", "信赖", "暧昧", "恋人"],
        "rel_affection": 0,
        "stats": [{"key": "trust", "label": "好感度", "max": 100}, {"key": "insight", "label": "洞察力", "max": 100}]
    },
    "school": {
        "title": "樱之诗",
        "world": "私立樱丘学园，坐落于沿海小城。春天，樱花如雪般飘落。主人公在开学典礼那天，遇见了改变命运的两个人。",
        "genre": ["校园", "恋爱", "日常"],
        "scene": "樱丘学园 — 校门口樱花道",
        "main_goal": "在樱花飘落的季节，找到属于自己的青春答案",
        "characters": [
            {"name": "小樱", "isMain": True, "role_tags": ["转学生"], "personality_tags": ["开朗", "温柔", "天然呆"], "appearance": "粉色长发，常穿校服", "relationship": [], "goal": "融入新学校，交到朋友", "secret": "", "background": "因家庭原因频繁转学", "special_ability": ""},
            {"name": "雪乃", "isMain": False, "role_tags": ["学生会长"], "personality_tags": ["高冷", "完美主义", "外冷内热"], "appearance": "黑色长发，戴眼镜", "relationship": ["同班同学"], "goal": "维持学生会权威", "secret": "私下喜欢画漫画", "background": "", "special_ability": ""}
        ],
        "rel_stages": ["陌生", "认识", "朋友", "知己", "暧昧", "恋人"],
        "rel_affection": 0,
        "stats": [{"key": "trust", "label": "好感度", "max": 100}, {"key": "popularity", "label": "人气", "max": 100}]
    },
    "fantasy": {
        "title": "剑与星辉",
        "world": "艾泽拉大陆，魔法与剑术并存的世界。千年和平被北方出现的「虚空裂隙」打破。王国的冒险者公会正在招募勇者。",
        "genre": ["奇幻", "冒险", "史诗"],
        "scene": "冒险者公会 — 王都大厅",
        "main_goal": "封印虚空裂隙，拯救艾泽拉大陆",
        "characters": [
            {"name": "雷恩", "isMain": True, "role_tags": ["流浪骑士"], "personality_tags": ["正直", "勇敢", "沉默"], "appearance": "银白短发，蓝色眼睛，身穿旧铠甲", "relationship": [], "goal": "找回失去的记忆", "secret": "", "background": "失去记忆的骑士", "special_ability": "剑术无双"},
            {"name": "艾莉西亚", "isMain": False, "role_tags": ["精灵弓箭手"], "personality_tags": ["冷静", "高傲", "忠诚"], "appearance": "金色长发，尖耳朵，绿色披风", "relationship": ["同伴", "救命恩人"], "goal": "保护森林族人的安全", "secret": "拥有预知箭术的能力", "background": "", "special_ability": ""}
        ],
        "rel_stages": ["陌路", "同行", "战友", "信赖", "羁绊", "灵魂共鸣"],
        "rel_affection": 0,
        "stats": [{"key": "bond", "label": "羁绊", "max": 100}, {"key": "power", "label": "战力", "max": 100}]
    },
    "mystery": {
        "title": "第七日",
        "world": "现代都市。一连串离奇的失踪案打破了城市的平静。作为私家侦探的主角，在调查中发现所有线索都指向一家名为「第七日」的神秘咖啡馆。",
        "genre": ["悬疑", "都市", "推理"],
        "scene": "第七日咖啡馆 — 深夜",
        "main_goal": "破解失踪案的真相，揭开第七日的秘密",
        "characters": [
            {"name": "苏晓", "isMain": True, "role_tags": ["私家侦探"], "personality_tags": ["冷静", "敏锐", "孤僻"], "appearance": "黑色风衣，常戴墨镜", "relationship": [], "goal": "查明真相，找回失踪者", "secret": "", "background": "曾是一名刑警", "special_ability": "过目不忘的观察力"},
            {"name": "墨言", "isMain": False, "role_tags": ["咖啡馆老板"], "personality_tags": ["神秘", "优雅", "深不可测"], "appearance": "黑发，常穿深色西装", "relationship": ["线人", "对手"], "goal": "守护第七日的秘密", "secret": "知道所有失踪案的真相", "background": "", "special_ability": ""}
        ],
        "rel_stages": ["陌生", "试探", "合作", "信任", "依赖", "命运共同体"],
        "rel_affection": 0,
        "stats": [{"key": "trust", "label": "信任度", "max": 100}, {"key": "clue", "label": "线索进度", "max": 100}]
    },
}

_NEW_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>新故事 — Prompt OS Galgame</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Segoe UI","Noto Sans SC",system-ui,sans-serif;background:#0d1117;color:#c9d1d9;min-height:100vh}
.topbar{display:flex;align-items:center;justify-content:space-between;padding:10px 24px;border-bottom:1px solid #21262d;background:#0d1117}
.topbar h1{font-size:1.15em;color:#58a6ff}
.back-btn{display:inline-block;padding:5px 14px;background:#1c2333;border:1px solid #58a6ff;border-radius:6px;color:#58a6ff;text-decoration:none;font-size:0.82em}
.back-btn:hover{background:#1a3a5c;color:#79c0ff}
.layout{display:flex;gap:20px;max-width:1100px;margin:0 auto;padding:16px 24px}
.sidebar{width:280px;flex-shrink:0}
.sidebar .card{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:14px;margin-bottom:12px}
.sidebar .card h3{font-size:0.85em;color:#8b949e;margin-bottom:8px}
.sidebar .card input{width:100%;padding:7px 10px;background:#0d1117;border:1px solid #30363d;border-radius:5px;color:#c9d1d9;font-size:0.85em;margin-bottom:6px}
.sidebar .card input:focus{outline:none;border-color:#58a6ff}
.sidebar .card .btn{display:block;width:100%;padding:8px 0;background:#1a3a5c;color:#58a6ff;border:1px solid #58a6ff;border-radius:5px;font-size:0.85em;cursor:pointer;text-align:center;margin-top:6px}
.sidebar .card .btn:hover{background:#1f4a7a}
.sidebar .card .btn.primary{background:#238636;color:#fff;border-color:#238636}
.sidebar .card .btn.primary:hover{background:#2ea043}
.sidebar .card .btn:disabled{opacity:0.5;cursor:not-allowed}
.sidebar .card .hint{color:#8b949e;font-size:0.72em;margin-top:4px;min-height:16px}
.preset-bar{display:flex;flex-direction:column;gap:4px}
.preset-btn{padding:7px 12px;background:#1c2333;border:1px solid #30363d;border-radius:6px;color:#8b949e;font-size:0.82em;cursor:pointer;text-align:left;transition:all 0.12s}
.preset-btn:hover{border-color:#58a6ff;color:#58a6ff}
.preset-btn.active{background:#1a3a5c;border-color:#58a6ff;color:#58a6ff}
.main-form{flex:1;min-width:0;padding-bottom:40px}
.field-group{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:14px 18px;margin-bottom:12px}
.field-group .fg-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}
.field-group .fg-header label{font-size:0.85em;color:#8b949e;font-weight:600}
.field-group .fg-header .desc{font-size:0.72em;color:#484f58;margin-left:8px}
.field-group .fg-row{display:flex;gap:8px;align-items:flex-start}
.field-group .fg-row input,.field-group .fg-row textarea,.field-group .fg-row select{flex:1;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:5px;color:#c9d1d9;font-size:0.88em;font-family:inherit}
.field-group .fg-row textarea{resize:vertical;min-height:60px}
.field-group .fg-row input:focus,.field-group .fg-row textarea:focus,.field-group .fg-row select:focus{outline:none;border-color:#58a6ff}
.ai-btn{flex-shrink:0;padding:7px 12px;background:transparent;border:1px solid #d2a8ff;border-radius:5px;color:#d2a8ff;font-size:0.78em;cursor:pointer;white-space:nowrap;transition:all 0.12s}
.ai-btn:hover{background:#1f1a2e;border-color:#bc8cff;color:#bc8cff}
.ai-btn:disabled{opacity:0.4;cursor:not-allowed}
.ai-btn .spin{display:none}
.ai-btn.loading .spin{display:inline-block;animation:spin 0.7s linear infinite}
.char-list{display:flex;flex-wrap:wrap;gap:12px}
.char-card{flex:1;min-width:260px;max-width:380px;background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:12px}
.char-card .ch-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}
.char-card .ch-top .ch-num{font-size:0.75em;color:#484f58}
.char-card .ch-top .ch-del{background:none;border:none;color:#484f58;font-size:0.9em;cursor:pointer}
.char-card .ch-top .ch-del:hover{color:#f85149}
.char-card input{padding:6px 10px;width:100%;background:#161b22;border:1px solid #30363d;border-radius:4px;color:#c9d1d9;font-size:0.85em;margin-bottom:4px}
.char-card input:focus{outline:none;border-color:#58a6ff}
.char-card .ch-ai-btn{display:inline-block;padding:4px 10px;margin-top:4px;background:transparent;border:1px solid #d2a8ff;border-radius:4px;color:#d2a8ff;font-size:0.72em;cursor:pointer}
.char-card .ch-ai-btn:hover{background:#1f1a2e}
.char-card .ch-ai-btn:disabled{opacity:0.4}
.add-char-btn{display:inline-flex;align-items:center;gap:4px;padding:8px 16px;margin-top:8px;background:transparent;border:1px dashed #30363d;border-radius:6px;color:#8b949e;font-size:0.82em;cursor:pointer}
.add-char-btn:hover{border-color:#58a6ff;color:#58a6ff}
.btn-submit{display:inline-block;margin-top:16px;padding:12px 40px;background:#238636;border:none;border-radius:6px;color:#fff;font-size:1em;cursor:pointer;font-weight:bold}
.btn-submit:hover{background:#2ea043}
@keyframes spin{to{transform:rotate(360deg)}}
</style>
</head>
<body>
<div class="topbar">
    <h1>🆕 创建新故事</h1>
    <a href="/" class="back-btn">← 返回游戏</a>
</div>
<div class="layout">
    <div class="sidebar">
        <div class="card">
            <h3>🤖 一键生成</h3>
            <textarea id="kw_input" placeholder="粘贴小说简介 / 世界观描述 / 关键词均可&#10;&#10;示例 ①：修仙 宗门 重生 系统流&#10;示例 ②：一个被退婚的废柴少年，在悬崖下捡到一枚神秘戒指……&#10;示例 ③：公元2247年，人类发现了外星遗迹……" style="width:100%;height:110px;padding:10px 12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:0.85em;resize:vertical;font-family:inherit;margin-bottom:6px;line-height:1.5"></textarea>
            <button class="btn primary" onclick="generateWorld()">✨ 一键生成完整设定</button>
            <div class="hint" id="kw_status"></div>
        </div>
        <div class="card">
            <h3>📦 预设模板</h3>
            <div class="preset-bar" id="presets">
                <button class="preset-btn active" onclick="loadPreset('scifi',this)">🚀 星痕纪元 · 科幻</button>
                <button class="preset-btn" onclick="loadPreset('school',this)">🌸 樱之诗 · 校园恋爱</button>
                <button class="preset-btn" onclick="loadPreset('fantasy',this)">⚔️ 奇幻冒险</button>
                <button class="preset-btn" onclick="loadPreset('mystery',this)">🔍 都市悬疑</button>
                <button class="preset-btn" onclick="loadPreset('custom',this)">✨ 空白自定义</button>
            </div>
        </div>
    </div>
    <form class="main-form" method="post" action="/new" onsubmit="prepareSubmit()">
        <input type="hidden" name="chars_json" id="charsJson" value="">
        <input type="hidden" name="custom_rules" id="customRulesInput" value="">
        <input type="hidden" name="main_goal" id="f_main_goal" value="调查星痕遗迹的真相">
        <input type="hidden" name="rel_system" id="f_rel_system" value="">

        <div class="field-group">
            <div class="fg-header"><label>📖 故事标题</label><span class="desc">8~20字，吸引人的名称</span></div>
            <div class="fg-row">
                <input name="title" id="f_title" value="星痕纪元" required placeholder="给你的故事起个名字">
                <button type="button" class="ai-btn" onclick="genField('title')">✨ 生成</button>
            </div>
        </div>

        <div class="field-group">
            <div class="fg-header"><label>🎭 类型 / 风格</label><span class="desc">下拉挑选 + 回车自定义，可多选</span></div>
            <div id="genreTags" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px;min-height:28px"></div>
            <div class="fg-row" style="gap:6px">
                <select id="genreSelect" onchange="pickGenre(this.value);this.value=''" style="flex:1;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:5px;color:#c9d1d9;font-size:0.88em">
                    <option value="">— 挑选风格标签 —</option>
                    <option value="科幻">🚀 科幻</option><option value="冒险">⚔️ 冒险</option><option value="情感">💕 情感</option>
                    <option value="校园">🌸 校园</option><option value="恋爱">💌 恋爱</option><option value="日常">☕ 日常</option>
                    <option value="奇幻">🧙 奇幻</option><option value="成长">🌱 成长</option><option value="悬疑">🔍 悬疑</option>
                    <option value="推理">🧩 推理</option><option value="都市">🏙️ 都市</option><option value="修仙">🏔️ 修仙</option>
                    <option value="玄幻">✨ 玄幻</option><option value="热血">🔥 热血</option><option value="恐怖">👻 恐怖</option>
                    <option value="惊悚">😱 惊悚</option><option value="生存">🏕️ 生存</option><option value="历史">🏯 历史</option>
                    <option value="权谋">♟️ 权谋</option><option value="战争">⚡ 战争</option><option value="赛博朋克">🤖 赛博朋克</option>
                    <option value="反乌托邦">🏚️ 反乌托邦</option>
                </select>
                <input id="genreInput" placeholder="输入自定义，回车添加…" style="flex:1" onkeydown="if(event.key==='Enter'){event.preventDefault();addCustomGenre()}">
            </div>
            <input type="hidden" name="genre" id="f_genre" value="科幻 / 冒险 / 情感">
        </div>

        <div class="field-group">
            <div class="fg-header"><label>📍 开局地点</label><span class="desc">故事开始的第一个场景</span></div>
            <div class="fg-row">
                <input name="scene" id="f_scene" value="回声号 — 舰桥" required placeholder="如：高二三班教室、回声号舰桥、云岚宗外门">
                <button type="button" class="ai-btn" onclick="genField('scene')">✨ AI生成</button>
            </div>
        </div>

        <div class="field-group">
            <div class="fg-header"><label>🎯 故事主线目标</label><span class="desc">为AI提供长期剧情驱动力</span></div>
            <div class="fg-row">
                <input id="f_main_goal_input" value="调查星痕遗迹的真相" placeholder="如：调查失踪舰队、找到失踪的妹妹、攻略五位女主、成为最强修仙者" onchange="document.getElementById('f_main_goal').value=this.value">
                <button type="button" class="ai-btn" onclick="genField('main_goal')">✨ AI生成</button>
            </div>
        </div>

        <div class="field-group" style="border-style:dashed;border-color:#30363d;opacity:0.85">
            <div class="fg-header"><label>🌍 世界观背景</label><span class="desc">可选 · 50~300字 · 校园恋爱/都市日常可跳过</span></div>
            <div class="fg-row">
                <textarea name="world" id="f_world" placeholder="公元2247年，人类已进入星际殖民时代…（留空也完全可以）">公元2247年，人类已进入星际殖民时代。在银河系边缘的「碎星带」，一艘名为「回声号」的调查船发现了一处远古外星遗迹。遗迹中封存着名为「星痕」的神秘能量。</textarea>
                <button type="button" class="ai-btn" onclick="genField('world')">✨ AI生成</button>
            </div>
        </div>

        <div class="field-group">
            <div class="fg-header"><label>❤️ 关系系统</label><span class="desc">设定角色关系阶段和初始好感度</span></div>
            <div id="relStages" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px;min-height:28px"></div>
            <div class="fg-row" style="gap:6px;align-items:center;margin-bottom:6px">
                <input id="relStageInput" placeholder="输入阶段名，回车添加…" style="flex:1" onkeydown="if(event.key==='Enter'){event.preventDefault();addRelStage()}">
                <span style="font-size:0.78em;color:#8b949e;white-space:nowrap">终点</span>
            </div>
            <div class="fg-row" style="align-items:center;gap:10px">
                <label style="font-size:0.78em;color:#8b949e;white-space:nowrap">初始好感（0~100）：</label>
                <input type="range" id="affectionSlider" min="0" max="100" value="0" oninput="document.getElementById('affVal').textContent=this.value;updateRelSystem()" style="flex:1;accent-color:#d2a8ff">
                <span id="affVal" style="font-size:0.85em;color:#d2a8ff;font-weight:bold;min-width:28px;text-align:center">0</span>
            </div>
            <button type="button" class="ai-btn" onclick="genField('rel_system')" style="margin-top:6px">✨ AI推荐关系系统</button>
        </div>

        <div class="field-group">
            <div class="fg-header"><label>👥 角色设定</label><span class="desc">主角 + 重要NPC，可自由增减</span></div>
            <div id="charList" class="char-list"></div>
            <button type="button" class="add-char-btn" onclick="addCharacter()">➕ 新增角色</button>
        </div>

        <div class="field-group">
            <div class="fg-header"><label>🎨 专属规则</label><span class="desc">可选，AI 生成追踪维度和关系阶段</span></div>
            <button type="button" class="ai-btn" onclick="generateRules()" id="rulesBtn">✨ AI 生成专属规则</button>
            <div id="rulesPreview" style="margin-top:6px;font-size:0.78em;color:#8b949e;min-height:18px">📊 默认追踪：<b style="color:#7ee787">好感度</b>（陌生→恋人，7阶段）· 无需生成即可使用</div>
        </div>

        <button type="submit" class="btn-submit">🎬 开始新故事</button>
    </form>
</div>

<script>
const presets = """ + json.dumps(_PRESETS, ensure_ascii=False) + """;

// ── Character management ──
let characters = [
    {name:'林夜',role_tags:['调查船船长','退役军人'],appearance:'短发，眼神锐利，常穿深色作战服',personality_tags:['冷静','理性','内敛','有责任感'],relationship:[],goal:'寻找星痕背后的真相',secret:'',background:'曾参与第七远征舰队',special_ability:'星痕感知',notes:'',isMain:true},
    {name:'艾琳',role_tags:['考古语言学家'],appearance:'金色长发，碧绿色眼睛',personality_tags:['热情','好奇','冲动','敏锐'],relationship:['工作伙伴'],goal:'破解星痕文字',secret:'能够听见遗迹中的低语',background:'',special_ability:'',notes:'',isMain:false}
];
let charIdCounter = 2;

// ── Relationship system defaults ──
var relStagesArr = ['陌生','熟悉','朋友','信赖','暧昧','恋人'];
var relAffection = 0;

// ── Tag presets ──
var ROLE_PRESETS = ['战士','法师','刺客','治疗师','船长','指挥官','科学家','考古学家','语言学家','工程师','商人','情报贩子','贵族','平民','学生','教师','侦探','记者','黑客','飞行员','赏金猎人','走私者','叛军','特工','流浪者','隐士'];
var PERSONALITY_PRESETS = ['冷静','热情','理性','冲动','内敛','外向','乐观','悲观','勇敢','谨慎','狡猾','正直','温柔','冷酷','幽默','严肃','忠诚','叛逆','善良','自私','敏感','迟钝','固执','灵活','孤僻','开朗','腹黑','天然呆','傲娇','病娇'];
var RELATION_PRESETS = ['同伴','朋友','恋人','暗恋对象','青梅竹马','上级','下属','导师','学生','亲人','兄弟','姐妹','父亲','母亲','对手','仇人','陌生人','盟友','敌人','救命恩人','背叛者','守护者','被守护者','房东','师尊','同班同学','工作伙伴','上司'];

// ── Relationship stage management ──
function renderRelStages(){
    var div = document.getElementById('relStages');
    if(!div) return;
    var h='';
    for(var i=0; i<relStagesArr.length; i++){
        h+='<span class="rel-tag" onclick="removeRelStage('+i+')" style="display:inline-block;padding:3px 10px;background:#1a3a5c;border:1px solid #58a6ff;border-radius:12px;color:#58a6ff;font-size:0.75em;cursor:pointer;margin:2px 3px">'+esc(relStagesArr[i])+' ×</span>';
        if(i < relStagesArr.length-1) h+='<span style="color:#484f58;font-size:0.75em">→</span>';
    }
    div.innerHTML = h || '<span style="color:#484f58;font-size:0.75em">点击下方输入框添加阶段</span>';
    updateRelSystem();
}
function addRelStage(){
    var inp = document.getElementById('relStageInput');
    var val = inp.value.trim();
    if(!val) return;
    relStagesArr.push(val);
    inp.value = '';
    renderRelStages();
}
function removeRelStage(idx){
    if(relStagesArr.length <= 2) return;
    relStagesArr.splice(idx,1);
    renderRelStages();
}
function updateRelSystem(){
    var aff = parseInt(document.getElementById('affectionSlider').value) || 0;
    document.getElementById('f_rel_system').value = JSON.stringify({stages:relStagesArr, affection:aff});
}
renderRelStages();

function renderCharTags(containerId, tags, presetList, charIdx, fieldName){
    var div = document.getElementById(containerId);
    if(!div) return;
    var h='';
    for(var t=0; t<tags.length; t++){
        h+='<span style=\"display:inline-block;padding:1px 8px;background:#1a3a5c;border:1px solid #58a6ff;border-radius:10px;color:#58a6ff;font-size:0.7em;cursor:pointer;margin:2px 3px 2px 0\" onclick=\"removeCharTag('+charIdx+',&quot;'+esc(fieldName)+'&quot;,'+t+')\">'+esc(tags[t])+' ×</span>';
    }
    div.innerHTML = h;

    // Also render suggestion chips
    var sugDiv = document.getElementById(containerId+'_sug');
    if(sugDiv && presetList){
        var s='';
        for(var p=0; p<presetList.length; p++){
            var tag = presetList[p];
            if(tags.indexOf(tag)<0){
                s+='<span style=\"display:inline-block;padding:1px 6px;background:#1c2333;border:1px solid #30363d;border-radius:8px;color:#8b949e;font-size:0.65em;cursor:pointer;margin:1px 2px\" onclick=\"addCharTag('+charIdx+',&quot;'+esc(fieldName)+'&quot;,&quot;'+esc(tag)+'&quot;)\">'+esc(tag)+'</span>';
            }
        }
        sugDiv.innerHTML = s;
    }
}

function addCharTag(i, field, tag){
    if(!tag) return;
    var arr = characters[i][field];
    if(!arr) arr = characters[i][field] = [];
    if(arr.indexOf(tag)<0){ arr.push(tag); renderAllCharTags(i); }
    // Clear input
    var inp = document.getElementById('ch_'+i+'_'+field);
    if(inp) inp.value = '';
}

function removeCharTag(i, field, idx){
    var arr = characters[i][field];
    if(arr){ arr.splice(idx,1); renderAllCharTags(i); }
}

function renderAllCharTags(i){
    var c = characters[i];
    renderCharTags('ch_'+i+'_role_tags', c.role_tags||[], ROLE_PRESETS, i, 'role_tags');
    renderCharTags('ch_'+i+'_personality_tags', c.personality_tags||[], PERSONALITY_PRESETS, i, 'personality_tags');
    if(!c.isMain){
        renderCharTags('ch_'+i+'_relationship', c.relationship||[], RELATION_PRESETS, i, 'relationship');
    }
}

function renderCharacters(){
    var html='';
    characters.forEach(function(c,i){
        html+='<div class=\"char-card\" id=\"chcard_'+i+'\">'+
            '<div class=\"ch-top\"><span class=\"ch-num\">'+(c.isMain?'⭐ 主角':'👤 NPC #'+(i+1))+'</span>'+
            (!c.isMain && characters.length>1?'<button class=\"ch-del\" onclick=\"removeChar('+i+')\" title=\"移除\">×</button>':'')+
            '</div>'+
            '<input placeholder=\"姓名\" value=\"'+esc(c.name)+'\" onchange=\"updateChar('+i+',&quot;name&quot;,this.value)\" required style=\"font-weight:bold\">'+
            '<div style=\"margin-top:4px\"><span style=\"font-size:0.7em;color:#8b949e\">身份/职业</span>'+
            '<div style=\"display:flex;gap:4px;margin:2px 0\"><input id=\"ch_'+i+'_role_tags\" placeholder=\"输入后回车添加\" style=\"flex:1;font-size:0.8em;padding:3px 8px\" onkeydown=\"if(event.key==&quot;Enter&quot;){event.preventDefault();addCharTag('+i+',&quot;role_tags&quot;,this.value)}\"></div>'+
            '<div id=\"ch_'+i+'_role_tags_tags\" style=\"min-height:18px\"></div>'+
            '<div id=\"ch_'+i+'_role_tags_sug\" style=\"max-height:48px;overflow-y:auto;line-height:1.6\"></div></div>'+
            '<div style=\"margin-top:4px\"><span style=\"font-size:0.7em;color:#8b949e\">外貌特征</span>'+
            '<input placeholder=\"发型、瞳色、着装风格…\" value=\"'+esc(c.appearance||'')+'\" onchange=\"updateChar('+i+',&quot;appearance&quot;,this.value)\" style=\"font-size:0.8em;padding:3px 8px;margin-top:2px\"></div>'+
            '<div style=\"margin-top:4px\"><span style=\"font-size:0.7em;color:#8b949e\">性格标签</span>'+
            '<div style=\"display:flex;gap:4px;margin:2px 0\"><input id=\"ch_'+i+'_personality_tags\" placeholder=\"输入后回车添加\" style=\"flex:1;font-size:0.8em;padding:3px 8px\" onkeydown=\"if(event.key==&quot;Enter&quot;){event.preventDefault();addCharTag('+i+',&quot;personality_tags&quot;,this.value)}\"></div>'+
            '<div id=\"ch_'+i+'_personality_tags_tags\" style=\"min-height:18px\"></div>'+
            '<div id=\"ch_'+i+'_personality_tags_sug\" style=\"max-height:48px;overflow-y:auto;line-height:1.6\"></div></div>'+
            (!c.isMain?'<div style=\"margin-top:4px\"><span style=\"font-size:0.7em;color:#8b949e\">与主角关系</span>'+
            '<div style=\"display:flex;gap:4px;margin:2px 0\"><input id=\"ch_'+i+'_relationship\" placeholder=\"输入后回车添加\" style=\"flex:1;font-size:0.8em;padding:3px 8px\" onkeydown=\"if(event.key==&quot;Enter&quot;){event.preventDefault();addCharTag('+i+',&quot;relationship&quot;,this.value)}\"></div>'+
            '<div id=\"ch_'+i+'_relationship_tags\" style=\"min-height:18px\"></div>'+
            '<div id=\"ch_'+i+'_relationship_sug\" style=\"max-height:48px;overflow-y:auto;line-height:1.6\"></div></div>':'')+
            '<div style=\"margin-top:4px\"><span style=\"font-size:0.7em;color:#8b949e\">当前目标</span>'+
            '<input placeholder=\"角色想要达成的事…\" value=\"'+esc(c.goal||'')+'\" onchange=\"updateChar('+i+',&quot;goal&quot;,this.value)\" style=\"font-size:0.8em;padding:3px 8px;margin-top:2px\"></div>'+
            '<div style=\"margin-top:4px\"><span style=\"font-size:0.7em;color:#d2a8ff\">🔒 隐藏秘密</span>'+
            '<input placeholder=\"用于制造剧情爆点的秘密…\" value=\"'+esc(c.secret||'')+'\" onchange=\"updateChar('+i+',&quot;secret&quot;,this.value)\" style=\"font-size:0.8em;padding:3px 8px;margin-top:2px;background:#1a121f;border-color:#4a3060;color:#d2a8ff\"></div>'+
            '<div style=\"margin-top:4px\"><span style=\"font-size:0.7em;color:#8b949e\">自由设定</span>'+
            '<textarea placeholder=\"任何你想补充的角色细节…\" onchange=\"updateChar('+i+',&quot;notes&quot;,this.value)\" style=\"width:100%;font-size:0.8em;padding:3px 8px;margin-top:2px;resize:vertical;min-height:36px;background:#161b22;border:1px solid #30363d;border-radius:4px;color:#c9d1d9;font-family:inherit\">'+esc(c.notes||'')+'</textarea></div>'+
            '<button type=\"button\" class=\"ch-ai-btn\" onclick=\"genCharacter('+i+')\">✨ 生成此角色</button>'+
            '</div>';
    });
    document.getElementById('charList').innerHTML=html;
    // Render tags for each character after DOM update
    for(var i=0; i<characters.length; i++){
        renderAllCharTags(i);
    }
}
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function updateChar(i,field,val){characters[i][field]=val;}
function addCharacter(){
    characters.push({name:'',role_tags:[],appearance:'',personality_tags:[],relationship:[],goal:'',secret:'',background:'',special_ability:'',notes:'',isMain:false});
    renderCharacters();
}
function removeChar(i){
    if(characters[i].isMain) return;
    if(characters.length<=1) return;
    characters.splice(i,1);
    renderCharacters();
}
function prepareSubmit(){
    document.getElementById('charsJson').value=JSON.stringify(characters);
    document.getElementById('f_genre').value=selectedGenres.join(' / ');
    document.getElementById('f_main_goal').value=document.getElementById('f_main_goal_input').value;
    updateRelSystem();
}
renderCharacters();

// ── Genre tag management ──
var selectedGenres = ['科幻','冒险','情感'];
function renderGenreTags(){
    var container = document.getElementById('genreTags');
    container.innerHTML = '';
    for(var i=0; i<selectedGenres.length; i++){
        var g = selectedGenres[i];
        var tag = document.createElement('span');
        tag.textContent = g + ' \u00d7';
        tag.title = '\u70b9\u51fb\u79fb\u9664';
        tag.style.cssText = 'display:inline-block;padding:2px 10px;background:#1a3a5c;border:1px solid #58a6ff;border-radius:12px;color:#58a6ff;font-size:0.78em;cursor:pointer;margin:2px 4px 2px 0;user-select:none';
        tag.onclick = (function(genre){ return function(){ removeGenre(genre); }; })(g);
        container.appendChild(tag);
    }
    if(selectedGenres.length === 0){
        container.innerHTML = '<span style="color:#484f58;font-size:0.78em">\u4ece\u4e0b\u62c9\u83dc\u5355\u6311\u9009\uff0c\u6216\u8f93\u5165\u81ea\u5b9a\u4e49\u98ce\u683c</span>';
    }
    document.getElementById('f_genre').value = selectedGenres.join(' / ');
}
function pickGenre(g){
    if(!g) return;
    if(selectedGenres.indexOf(g) < 0){
        selectedGenres.push(g);
        renderGenreTags();
    }
}
function addCustomGenre(){
    var inp = document.getElementById('genreInput');
    var val = inp.value.trim();
    if(!val) return;
    if(selectedGenres.indexOf(val) < 0){
        selectedGenres.push(val);
        renderGenreTags();
    }
    inp.value = '';
}
function removeGenre(g){
    var idx = selectedGenres.indexOf(g);
    if(idx >= 0){ selectedGenres.splice(idx,1); renderGenreTags(); }
}
renderGenreTags();

// ── Load preset ──
function loadPreset(key,btn){
    document.querySelectorAll('.preset-btn').forEach(function(b){b.classList.remove('active');});
    btn.classList.add('active');
    if(key==='custom'){
        document.getElementById('f_title').value='';document.getElementById('f_world').value='';
        document.getElementById('f_scene').value='';document.getElementById('f_main_goal_input').value='';
        document.getElementById('f_main_goal').value='';
        characters=[{name:'',role_tags:[],appearance:'',personality_tags:[],relationship:[],goal:'',secret:'',background:'',special_ability:'',notes:'',isMain:true}];
        relStagesArr=['陌生','熟悉','朋友','信赖','暧昧','恋人'];
        document.getElementById('affectionSlider').value=0;document.getElementById('affVal').textContent='0';
        renderCharacters();renderRelStages();return;
    }
    var p=presets[key];
    document.getElementById('f_title').value=p.title;document.getElementById('f_world').value=p.world||'';
    document.getElementById('f_scene').value=p.scene;
    if(p.main_goal){ document.getElementById('f_main_goal_input').value=p.main_goal; document.getElementById('f_main_goal').value=p.main_goal; }
    // Parse genre
    if(Array.isArray(p.genre)){selectedGenres=p.genre.slice();}
    else{selectedGenres=(p.genre||'').split('/').map(function(s){return s.trim();}).filter(Boolean);}
    renderGenreTags();
    if(p.characters && p.characters.length>0){
        characters=p.characters.map(function(c){
            return {
                name:c.name||'',isMain:!!c.isMain,
                role_tags:Array.isArray(c.role_tags)?c.role_tags.slice():(c.role_tags?[c.role_tags]:[]),
                personality_tags:Array.isArray(c.personality_tags)?c.personality_tags.slice():[],
                appearance:c.appearance||'',relationship:Array.isArray(c.relationship)?c.relationship.slice():[],
                goal:c.goal||'',secret:c.secret||'',background:c.background||'',
                special_ability:c.special_ability||'',notes:c.note||''
            };
        });
    } else {
        characters=[
            {name:p.char1_name||'主角',role_tags:p.char1_role?[p.char1_role]:[],personality_tags:[],appearance:'',relationship:[],goal:'',secret:'',background:'',special_ability:'',notes:p.char1_note||'',isMain:true},
            {name:p.char2_name||'',role_tags:p.char2_role?[p.char2_role]:[],personality_tags:[],appearance:'',relationship:[],goal:'',secret:'',background:'',special_ability:'',notes:p.char2_note||'',isMain:false}
        ];
    }
    renderCharacters();
    if(p.rel_stages){ relStagesArr=p.rel_stages.slice(); renderRelStages(); }
    if(p.rel_affection!=null){ document.getElementById('affectionSlider').value=p.rel_affection; document.getElementById('affVal').textContent=p.rel_affection; }
    if(p.stats){
        var rulesData = {stats: p.stats, stages: p.rel_stages || relStagesArr};
        document.getElementById('customRulesInput').value = JSON.stringify(rulesData);
        var statsLabels=(p.stats||[]).map(function(s){return s.label;}).join(' · ');
        var stagesLabels=(p.rel_stages||relStagesArr).join(' → ');
        document.getElementById('rulesPreview').innerHTML='<span style=\"color:#7ee787;\">✅ 预设</span><br>追踪维度: <b style=\"color:#ffa657;\">'+statsLabels+'</b><br>关系阶段: <b style=\"color:#d2a8ff;\">'+stagesLabels+'</b>';
    }
    updateRelSystem();
}

// ── AI field generation ──
async function genField(field){
    var btn=event.target, orig=btn.textContent;
    btn.disabled=true;btn.innerHTML='<span class="spin">⏳</span> 生成中';
    var title=document.getElementById('f_title').value;
    var world=document.getElementById('f_world').value;
    var genre=document.getElementById('f_genre').value;
    try{
        var params=new URLSearchParams({field:field,title:title,world:world,genre:genre});
        var res=await fetch('/generate-field',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:params});
        var data=await res.json();
        if(data.error){alert(data.error);}
        else{
            var story=data.story||data.title||data.name||'';
            if(field==='title')document.getElementById('f_title').value=story.replace(/["']/g,'').trim().slice(0,20);
            if(field==='world')document.getElementById('f_world').value=story.trim();
            if(field==='main_goal'){
                var goal=story||data.main_goal||'';
                document.getElementById('f_main_goal_input').value=goal.trim();
                document.getElementById('f_main_goal').value=goal.trim();
            }
            if(field==='scene')document.getElementById('f_scene').value=story.trim();
            if(field==='genre' && data.genre){
                if(Array.isArray(data.genre)){selectedGenres=data.genre;}
                else{selectedGenres=data.genre.split('/').map(function(s){return s.trim();}).filter(Boolean);}
                renderGenreTags();
            }
            if(field==='rel_system'){
                if(data.rel_stages){ relStagesArr=data.rel_stages; renderRelStages(); }
                if(data.rel_affection!=null){ document.getElementById('affectionSlider').value=data.rel_affection; document.getElementById('affVal').textContent=data.rel_affection; }
                updateRelSystem();
            }
        }
    }catch(e){alert('生成失败: '+e.message);}
    btn.disabled=false;btn.textContent=orig;
}

async function genCharacter(i){
    var btn=event.target, orig=btn.textContent;
    btn.disabled=true;btn.textContent='⏳ 生成中';
    var title=document.getElementById('f_title').value;
    var world=document.getElementById('f_world').value;
    try{
        var params=new URLSearchParams({field:'character',title:title,world:world,char_role:''});
        var res=await fetch('/generate-field',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:params});
        var data=await res.json();
        if(!data.error){
            if(data.name) characters[i].name=data.name;
            if(data.role_tags){ characters[i].role_tags=Array.isArray(data.role_tags)?data.role_tags:[data.role_tags]; }
            else if(data.role){ characters[i].role_tags=[data.role]; }
            if(data.appearance) characters[i].appearance=data.appearance;
            if(data.personality_tags){ characters[i].personality_tags=Array.isArray(data.personality_tags)?data.personality_tags:[data.personality_tags]; }
            else if(data.personality){ characters[i].personality_tags=[data.personality]; }
            if(data.relationship){ characters[i].relationship=Array.isArray(data.relationship)?data.relationship:[data.relationship]; }
            if(data.goal) characters[i].goal=data.goal;
            if(data.secret) characters[i].secret=data.secret;
            if(data.background) characters[i].background=data.background;
            if(data.special_ability) characters[i].special_ability=data.special_ability;
            if(data.notes) characters[i].notes=data.notes;
            renderCharacters();
        }
    }catch(e){alert('生成失败: '+e.message);}
    btn.disabled=false;btn.textContent=orig;
}

// ── One-click world generation ──
async function generateWorld(){
    var kw=document.getElementById('kw_input').value.trim();
    var status=document.getElementById('kw_status');
    var btn=document.querySelector('.sidebar .btn.primary');
    if(!kw){status.textContent='请输入关键词';status.style.color='#f85149';return;}
    status.textContent='⏳ AI 正在生成…';status.style.color='#ffa657';
    btn.disabled=true;
    try{
        var res=await fetch('/generate-world',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'keywords='+encodeURIComponent(kw)});
        var data=await res.json();
        if(data.error){status.textContent='❌ '+data.error;status.style.color='#f85149';}
        else{
            document.getElementById('f_title').value=data.title||'';
            document.getElementById('f_world').value=data.world||'';
            if(data.genre){
                if(Array.isArray(data.genre)){selectedGenres=data.genre;}
                else{selectedGenres=data.genre.split('/').map(function(s){return s.trim();}).filter(Boolean);}
                renderGenreTags();
            }
            document.getElementById('f_scene').value=data.scene||'';
            if(data.main_goal){
                document.getElementById('f_main_goal_input').value=data.main_goal;
                document.getElementById('f_main_goal').value=data.main_goal;
            }
            if(data.characters && data.characters.length>0){
                characters=data.characters.map(function(c){
                    return {
                        name:c.name||'',isMain:!!c.isMain,
                        role_tags:Array.isArray(c.role_tags)?c.role_tags:(c.role?[c.role]:[]),
                        personality_tags:Array.isArray(c.personality_tags)?c.personality_tags:(c.personality?[c.personality]:[]),
                        appearance:c.appearance||'',relationship:Array.isArray(c.relationship)?c.relationship:[],
                        goal:c.goal||'',secret:c.secret||'',background:c.background||'',
                        special_ability:c.special_ability||'',notes:c.note||c.notes||''
                    };
                });
            }
            renderCharacters();
            if(data.rel_stages){ relStagesArr=data.rel_stages.slice(); renderRelStages(); }
            if(data.rel_affection!=null){ document.getElementById('affectionSlider').value=data.rel_affection; document.getElementById('affVal').textContent=data.rel_affection; updateRelSystem(); }
            if(data.stats){
                var rulesData = {stats: data.stats, stages: data.rel_stages || relStagesArr};
                document.getElementById('customRulesInput').value = JSON.stringify(rulesData);
                var stats=(data.stats||[]).map(function(s){return s.label;}).join(' · ');
                var stages=(data.rel_stages||relStagesArr).join(' → ');
                document.getElementById('rulesPreview').innerHTML='<span style=\"color:#7ee787;\">✅ 已生成</span><br>追踪维度: <b style=\"color:#ffa657;\">'+stats+'</b><br>关系阶段: <b style=\"color:#d2a8ff;\">'+stages+'</b>';
            }
            document.querySelectorAll('.preset-btn').forEach(function(b){b.classList.remove('active');});
            status.textContent='✅ 已生成，可继续修改';
            status.style.color='#7ee787';
        }
    }catch(e){status.textContent='❌ 网络错误: '+e.message;status.style.color='#f85149';}
    btn.disabled=false;
}

// ── Rules generation ──
async function generateRules(){
    var title=document.getElementById('f_title').value;
    var world=document.getElementById('f_world').value;
    var preview=document.getElementById('rulesPreview');
    var btn=document.getElementById('rulesBtn');
    var names=characters.map(function(c){return c.name;}).filter(Boolean);
    preview.textContent='⏳ 正在生成专属规则…';preview.style.color='#ffa657';
    btn.disabled=true;
    try{
        var params=new URLSearchParams({title:title,world:world,genre:'',char1_name:names[0]||'',char1_role:'',char2_name:names[1]||'',char2_role:''});
        var res=await fetch('/generate-rules',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:params});
        var data=await res.json();
        if(data.error){preview.textContent='❌ '+data.error;preview.style.color='#f85149';}
        else{
            document.getElementById('customRulesInput').value=JSON.stringify(data);
            var stats=(data.stats||[]).map(function(s){return s.label;}).join(' · ');
            var stages=(data.stages||[]).join(' → ');
            preview.innerHTML='<span style="color:#7ee787;">✅ 已生成</span><br>追踪维度: <b style="color:#ffa657;">'+stats+'</b><br>关系阶段: <b style="color:#d2a8ff;">'+stages+'</b>';
            if(data.stages && data.stages.length>0){ relStagesArr=data.stages.slice(); renderRelStages(); updateRelSystem(); }
        }
    }catch(e){preview.textContent='❌ '+e.message;preview.style.color='#f85149';}
    btn.disabled=false;
}
</script>
</body>
</html>"""


_NPC_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>角色管理 — Prompt OS Galgame</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Segoe UI","Noto Sans SC",system-ui,sans-serif;background:#0d1117;color:#c9d1d9;min-height:100vh}
.topbar{display:flex;align-items:center;justify-content:space-between;padding:10px 24px;border-bottom:1px solid #21262d;background:#0d1117}
.topbar h1{font-size:1.15em;color:#58a6ff}
.back-btn{display:inline-block;padding:5px 14px;background:#1c2333;border:1px solid #58a6ff;border-radius:6px;color:#58a6ff;text-decoration:none;font-size:0.82em}
.back-btn:hover{background:#1a3a5c;color:#79c0ff}
.content{max-width:1100px;margin:0 auto;padding:16px 24px}
.add-bar{display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap;margin-bottom:16px;padding:14px;background:#161b22;border:1px solid #21262d;border-radius:8px}
.add-bar label{font-size:0.78em;color:#8b949e;margin-bottom:2px;display:block}
.add-bar input{padding:7px 10px;background:#0d1117;border:1px solid #30363d;border-radius:5px;color:#c9d1d9;font-size:0.85em;min-width:100px}
.add-bar input:focus{outline:none;border-color:#58a6ff}
.add-bar button{padding:7px 14px;border-radius:5px;font-size:0.82em;cursor:pointer;border:none;font-weight:bold;white-space:nowrap}
.btn-add{background:#238636;color:#fff}
.btn-add:hover{background:#2ea043}
.btn-ai{background:#1a3a5c;color:#58a6ff;border:1px solid #58a6ff!important}
.btn-ai:hover{background:#1f4a73}
.btn-ai:disabled{opacity:0.5;cursor:not-allowed}
.npc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px}
.npc-card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px 16px;position:relative}
.npc-card .tag{display:inline-block;padding:1px 6px;border-radius:3px;font-size:0.68em;margin-left:6px;vertical-align:middle}
.npc-card .tag.main{background:#1a3a5c;color:#58a6ff}
.npc-card .tag.npc{background:#3d2a1a;color:#ffa657}
.npc-card .name{font-weight:bold;color:#d2a8ff;font-size:1.05em}
.npc-card .role{color:#8b949e;font-size:0.82em;margin:4px 0}
.npc-card .note{color:#c9d1d9;font-size:0.8em;line-height:1.5;margin-top:6px}
.npc-card .level{color:#ffa657;font-size:0.78em}
.npc-card .trust{color:#7ee787;font-size:0.78em}
.npc-card .del-btn{position:absolute;top:8px;right:10px;background:none;border:none;color:#484f58;font-size:1em;cursor:pointer}
.npc-card .del-btn:hover{color:#f85149}
</style>
</head>
<body>
<div class="topbar">
    <h1>👥 角色管理</h1>
    <a href="/" class="back-btn">← 返回游戏</a>
</div>
<div class="content">
    <div class="add-bar">
        <div>
            <label>🤖 AI 生成</label>
            <div style="display:flex;gap:6px">
                <input id="ai_kw" placeholder="关键词：神秘商人 情报贩子" style="width:220px">
                <button class="btn-ai" id="ai_btn" onclick="generateNPC()">生成</button>
            </div>
            <div id="ai_status" style="font-size:0.72em;color:#8b949e;margin-top:2px;min-height:16px"></div>
        </div>
        <div style="border-left:1px solid #21262d;padding-left:12px">
            <form method="post" action="/npcs/add" style="display:flex;gap:6px;align-items:flex-end">
                <div><label>姓名</label><input name="name" placeholder="姓名" required style="width:100px"></div>
                <div><label>身份</label><input name="role" placeholder="身份" style="width:110px"></div>
                <div><label>描述</label><input name="note" placeholder="性格/背景" style="width:160px"></div>
                <button class="btn-add" type="submit">+ 添加</button>
            </form>
        </div>
    </div>
    <div class="npc-grid">
        {{NPC_CARDS}}
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


_SETTINGS_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>设置 — Prompt OS Galgame</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Segoe UI","Noto Sans SC",system-ui,sans-serif;background:#0d1117;color:#c9d1d9;min-height:100vh}
.topbar{display:flex;align-items:center;justify-content:space-between;padding:10px 24px;border-bottom:1px solid #21262d;background:#0d1117}
.topbar h1{font-size:1.15em;color:#58a6ff}
.back-btn{display:inline-block;padding:5px 14px;background:#1c2333;border:1px solid #58a6ff;border-radius:6px;color:#58a6ff;text-decoration:none;font-size:0.82em}
.back-btn:hover{background:#1a3a5c;color:#79c0ff}
.content{max-width:560px;margin:0 auto;padding:20px 24px}
.set-card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px 24px;margin-bottom:16px}
.set-card label{display:block;color:#8b949e;font-size:0.85em;margin-bottom:6px}
.set-card input,.set-card select{width:100%;padding:10px 14px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:0.9em;font-family:monospace}
.set-card input:focus,.set-card select:focus{outline:none;border-color:#58a6ff}
.set-card .hint{color:#484f58;font-size:0.75em;margin-top:6px}
.set-card .status{margin-top:8px;font-size:0.85em}
.set-card .status.ok{color:#7ee787}
.set-card .status.empty{color:#f85149}
.btn-row{display:flex;gap:10px;margin-top:12px}
.btn{padding:8px 20px;border-radius:6px;font-size:0.9em;cursor:pointer;border:none;font-weight:bold}
.btn-save{background:#238636;color:#fff}
.btn-save:hover{background:#2ea043}
.btn-clear{background:#3d1a1a;color:#f85149;border:1px solid #da3633}
.btn-clear:hover{background:#4d2020}
</style>
</head>
<body>
<div class="topbar">
    <h1>⚙️ 设置</h1>
    <a href="/" class="back-btn">← 返回游戏</a>
</div>
<div class="content">
    <form class="set-card" method="post" action="/settings">
            <label>🔑 DeepSeek API Key</label>
            <input name="api_key" type="password" id="keyInput"
                   placeholder="sk-xxxxxxxxxxxxxxxx"
                   value="{{MASKED_KEY}}">
            <div class="hint">Key 仅存储在本地 <code>data/apikey.json</code>，不会上传</div>
            <label style="margin-top:14px;">🧠 模型选择</label>
            <select name="model" id="modelSelect" style="width:100%;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:0.9em;">
                {{MODEL_OPTIONS}}
            </select>
            <div class="hint">{{MODEL_HINT}}</div>
            <label style="margin-top:14px;">📝 每轮字数</label>
            <input name="story_length" type="number" min="{{STORY_LENGTH_MIN}}" max="{{STORY_LENGTH_MAX}}" step="100"
                   value="{{STORY_LENGTH}}" style="width:120px;">
            <div class="hint">AI 每轮生成的文字量（{{STORY_LENGTH_MIN}}–{{STORY_LENGTH_MAX}}，建议 {{STORY_LENGTH_RECOMMENDED}}），默认 1000。对首次开篇也有影响。</div>
            <label style="margin-top:14px;">📐 AI 最大 Token</label>
            <select name="max_tokens" id="maxTokens" style="width:100%;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:0.9em;">
                {{MAX_TOKENS_OPTIONS}}
            </select>
            <div class="hint">控制 AI 回复长度上限（官方最大 384K output），随游戏页目标字数自动匹配。世界观生成最多 2× 且不超过官方上限。</div>
            <label style="margin-top:14px;">🌡️ 温度</label>
            <input name="temperature" type="range" min="0.1" max="2.0" step="0.1"
                   value="{{TEMPERATURE}}" style="width:100%;accent-color:#d2a8ff;">
            <div class="hint">当前: {{TEMPERATURE}} — 越高越有创意，越低越保守</div>
            <label style="margin-top:14px;">🎯 Top P</label>
            <input name="top_p" type="range" min="0" max="1" step="0.05"
                   value="{{TOP_P}}" style="width:100%;accent-color:#58a6ff;">
            <div class="hint">当前: {{TOP_P}} — 核采样参数，0.9 为推荐值</div>
            <label style="margin-top:14px;">📡 流式输出</label>
            <select name="stream" id="streamSelect" style="width:100%;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:0.9em;">
                {{STREAM_OPTIONS}}
            </select>
            <div class="hint">启用后 AI 回复会逐字流式展示（实验性）</div>
            <label style="margin-top:14px;">💬 上下文消息上限</label>
            <input name="max_context_messages" type="number" min="4" max="100" step="2"
                   value="{{MAX_CONTEXT_MESSAGES}}" style="width:100px;">
            <div class="hint">对话历史保留条数（4–100），默认 20。越长消耗 token 越多。</div>
            <label style="margin-top:14px;">🗜️ 自动压缩</label>
            <select name="auto_compress" id="autoCompress" style="width:100%;padding:8px 12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;font-size:0.9em;">
                {{AUTO_COMPRESS_OPTIONS}}
            </select>
            <div class="hint">超过阈值时自动压缩对话历史，减少 token 消耗</div>
            <label style="margin-top:14px;">📏 压缩阈值 (tokens)</label>
            <input name="compress_threshold" type="number" min="500" max="1000000" step="500"
                   value="{{COMPRESS_THRESHOLD}}" style="width:120px;">
            <div class="hint">达到此 token 数时触发自动压缩（500–1000000，官方上下文 1M），默认 4000</div>
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


