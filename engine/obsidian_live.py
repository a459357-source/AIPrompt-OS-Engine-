"""
obsidian_live.py — Real-time Obsidian Vault Export
====================================================
After every turn, writes/updates Obsidian-compatible Markdown files
directly into a configured vault folder.  Obsidian watches the
filesystem and auto-refreshes — open the vault to read the story live.

Structure created in the vault:
  星痕纪元/
  ├── _index.md              ← master index (Dataview-ready)
  ├── Chapters/
  │   ├── 001.md              ← per-chapter with frontmatter
  │   └── ...
  ├── Characters/
  │   └── <name>.md           ← auto-updated character sheets
  ├── 剧情图谱.md             ← Mermaid flowchart
  └── 完整叙事.md             ← concatenated full story
"""

import logging
from datetime import datetime
from pathlib import Path

import config
from engine import io_utils
from engine.router import load_graph

logger = logging.getLogger(__name__)

STORY_DIR = "星痕纪元"
CHAPTERS_DIR = f"{STORY_DIR}/Chapters"
CHARS_DIR = f"{STORY_DIR}/Characters"


# ── Public API ──────────────────────────────────────────────────────

def is_enabled() -> bool:
    """Check if live Obsidian export is configured."""
    return bool(config.OBSIDIAN_VAULT_PATH)


def get_vault_path() -> Path:
    """Return the resolved vault path."""
    return Path(config.OBSIDIAN_VAULT_PATH)


def init_vault() -> Path | None:
    """
    Create the folder structure in the Obsidian vault.
    Call once at startup.  Returns the vault path or None if not configured.
    """
    if not is_enabled():
        return None

    vault = get_vault_path()
    if not vault.exists():
        logger.warning("Obsidian vault not found: %s", vault)
        return None

    # Create subdirectories
    (vault / CHAPTERS_DIR).mkdir(parents=True, exist_ok=True)
    (vault / CHARS_DIR).mkdir(parents=True, exist_ok=True)

    # Write initial index if it doesn't exist
    index_path = vault / STORY_DIR / "_index.md"
    if not index_path.exists():
        _write_index(vault)

    logger.info("Obsidian vault ready: %s", vault)
    return vault


def on_turn(response: dict, state: dict, choice: str | None) -> None:
    """
    Called after each turn.  Writes the new chapter and updates all
    index/character/graph files in the Obsidian vault.

    Args:
        response: The LLM response dict (story, options, state)
        state: The new session state (turn, status, scene, ...)
        choice: The player's choice from the previous turn (or None)
    """
    if not is_enabled():
        return

    vault = get_vault_path()
    if not vault.exists():
        return

    turn = state.get("turn", 0)
    status = state.get("status", "?")
    scene = state.get("scene", "?")
    story = response.get("story", "")
    options = response.get("options", [])

    try:
        # 1. Write the chapter file
        _write_chapter_file(vault, turn, status, scene, choice, story, options)

        # 2. Update full story
        _update_full_story(vault)

        # 3. Update character sheets
        _update_characters(vault)

        # 4. Update story graph (Mermaid in vault)
        _update_graph_view(vault)

        # 4b. Also write standalone HTML graph (no Obsidian needed)
        _write_graph_html(vault)

        # 5. Update master index
        _write_index(vault)

        logger.info("Obsidian vault updated (turn %d)", turn)
    except Exception as exc:
        logger.warning("Obsidian live export failed (turn %d): %s", turn, exc)


# ── Internal helpers ────────────────────────────────────────────────

def _chapter_filename(turn: int) -> str:
    return f"{turn:03d}.md"


def _sanitize_filename(name: str) -> str:
    """Remove characters invalid in filenames."""
    return "".join(c for c in name if c not in r'\/:*?"<>|').strip()


def _write_chapter_file(
    vault: Path, turn: int, status: str, scene: str,
    choice: str | None, story: str, options: list[str],
) -> None:
    """Write a single chapter .md file with full frontmatter."""
    path = vault / CHAPTERS_DIR / _chapter_filename(turn)

    lines: list[str] = []
    lines.append("---")
    lines.append(f"turn: {turn}")
    lines.append(f"status: {status}")
    lines.append(f"scene: \"{scene}\"")
    lines.append(f"choice: \"{choice or 'auto'}\"")
    lines.append(f"generated: \"{datetime.now().isoformat()}\"")
    # Dataview fields
    lines.append(f"tags: [chapter, {status.lower()}]")
    lines.append("---")
    lines.append("")
    lines.append(f"# Chapter {turn}")
    lines.append("")
    lines.append(f"**Status:** `{status}`  |  **Scene:** {scene}")
    if choice:
        lines.append(f"**Player choice:** `{choice}`")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(story)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Options")
    lines.append("")
    for idx, opt in enumerate(options, 1):
        lines.append(f"- **{chr(64 + idx)}.** {opt}")
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _update_full_story(vault: Path) -> None:
    """Concatenate all chapters into one full-story file."""
    chapters_dir = vault / CHAPTERS_DIR

    state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    memory = io_utils.read_json(config.MEMORY_PATH)

    lines: list[str] = []
    lines.append("---")
    lines.append("title: 星痕纪元 — 完整叙事")
    lines.append(f"turns: {state.get('turn', 0)}")
    lines.append(f"status: {state.get('status', '?')}")
    lines.append(f"updated: {datetime.now().isoformat()}")
    lines.append("tags: [story, full-narrative]")
    lines.append("---")
    lines.append("")
    lines.append("# 星痕纪元 — 完整叙事")
    lines.append("")

    # Character summary
    chars = memory.get("characters", {})
    if chars:
        lines.append("## 角色关系")
        lines.append("")
        for name, data in chars.items():
            trust = data.get("trust", 0.5)
            rel = data.get("relationship", "")
            flags = data.get("flags", [])
            lines.append(f"- **[[Characters/{_sanitize_filename(name)}|{name}]]**: "
                         f"信任度 {trust:.0%}, {rel}")
            if flags:
                lines.append(f"  - 事件: {', '.join(flags)}")
        lines.append("")

    # All chapters
    if chapters_dir.exists():
        for chap in sorted(chapters_dir.glob("*.md")):
            text = chap.read_text(encoding="utf-8")
            # Strip frontmatter for clean reading
            clean = _strip_frontmatter(text)
            lines.append(clean)
            lines.append("")

    path = vault / STORY_DIR / "完整叙事.md"
    path.write_text("\n".join(lines), encoding="utf-8")


def _update_characters(vault: Path) -> None:
    """Update per-character .md files from memory."""
    memory = io_utils.read_json(config.MEMORY_PATH)
    chars = memory.get("characters", {})
    chars_dir = vault / CHARS_DIR

    for name, data in chars.items():
        trust = data.get("trust", 0.5)
        rel = data.get("relationship", "")
        flags = data.get("flags", [])

        lines: list[str] = []
        lines.append("---")
        lines.append(f"name: {name}")
        lines.append(f"trust: {trust}")
        lines.append(f"relationship: \"{rel}\"")
        lines.append("tags: [character]")
        lines.append("---")
        lines.append("")
        lines.append(f"# {name}")
        lines.append("")
        lines.append(f"**信任度:** {trust:.0%}  |  **关系:** {rel}")
        lines.append("")
        if flags:
            lines.append("## 关键事件")
            lines.append("")
            for f in flags:
                lines.append(f"- {f}")
            lines.append("")

        filename = _sanitize_filename(name)
        path = chars_dir / f"{filename}.md"
        path.write_text("\n".join(lines), encoding="utf-8")


def _update_graph_view(vault: Path) -> None:
    """Write a Mermaid flowchart of the story graph."""
    graph = load_graph()
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])

    lines: list[str] = []
    lines.append("---")
    lines.append("title: 剧情分支图")
    lines.append(f"updated: {datetime.now().isoformat()}")
    lines.append("tags: [graph, mermaid]")
    lines.append("---")
    lines.append("")
    lines.append("# 剧情分支图")
    lines.append("")
    lines.append("```mermaid")
    lines.append("graph TD")

    for nid, node in nodes.items():
        turn = node.get("turn", "?")
        text = node.get("text", "")[:40].replace('"', "'")
        label = f"T{turn}: {text}"
        lines.append(f'  n{nid}["{label}"]')

    for edge in edges:
        frm = edge["from"]
        to = edge["to"]
        choice = edge.get("choice", "").replace('"', "'")
        lines.append(f"  n{frm} -- {choice} --> n{to}")

    lines.append("```")
    lines.append("")

    # Also add node detail table
    lines.append("## 节点详情")
    lines.append("")
    lines.append("| Node | Turn | Scene | Status |")
    lines.append("|------|------|-------|--------|")
    for nid in sorted(nodes.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        node = nodes[nid]
        lines.append(
            f"| {nid} | {node.get('turn', '?')} | "
            f"{node.get('scene', '?')} | {node.get('status', '?')} |"
        )
    lines.append("")

    path = vault / STORY_DIR / "剧情图谱.md"
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_graph_html(vault: Path) -> None:
    """Full analytics dashboard — Mermaid graph + Chart.js charts + toggles.
    Double-click to open — no Obsidian, no server, no dependencies (CDN only)."""
    from engine.router import load_graph
    from engine.analytics import compute_all

    graph = load_graph()
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])
    memory = io_utils.read_json(config.MEMORY_PATH)
    chars = memory.get("characters", {})
    state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    analytics = compute_all()
    from engine.router import load_graph

    graph = load_graph()
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])
    memory = io_utils.read_json(config.MEMORY_PATH)
    chars = memory.get("characters", {})
    state = io_utils.read_yaml(config.SESSION_STATE_PATH)

    # ── Build Mermaid source with characters ──
    mm = ["graph TD"]

    # Story nodes as rectangles
    for nid, node in nodes.items():
        turn = node.get("turn", "?")
        text = node.get("text", "")[:30].replace('"', "'")
        mm.append(f'  n{nid}["T{turn}: {text}"]')

    # Character nodes as rounded rects (Mermaid uses `()` for round edges)
    # Assign IDs like c0, c1, ...
    char_ids = {}
    for i, (name, data) in enumerate(chars.items()):
        cid = f"c{i}"
        char_ids[name] = cid
        trust = data.get("trust", 0.5)
        trust_pct = int(trust * 100)
        label = f"{name} ({trust_pct}%)".replace('"', "'")
        mm.append(f'  {cid}("{label}")')

        # Connect character to story nodes where their name appears
        for nid, node in nodes.items():
            text = node.get("text", "")
            if name in text:
                mm.append(f"  {cid} -.-> n{nid}")

    # Story edges (choices)
    for edge in edges:
        frm = edge["from"]
        to = edge["to"]
        choice = edge.get("choice", "").replace('"', "'")
        mm.append(f"  n{frm} -- {choice} --> n{to}")

    # Style definitions for Mermaid
    mm.append("")
    mm.append("  classDef story fill:#1f6feb,stroke:#58a6ff,color:#fff")
    mm.append("  classDef highTrust fill:#2ea043,stroke:#3fb950,color:#fff")
    mm.append("  classDef midTrust fill:#d29922,stroke:#e3b341,color:#fff")
    mm.append("  classDef lowTrust fill:#da3633,stroke:#f85149,color:#fff")
    mm.append("")

    # Apply story class to all story nodes
    story_ids = " ".join(f"n{nid}" for nid in nodes)
    if story_ids:
        mm.append(f"  class {story_ids} story")

    # Apply trust classes to character nodes
    for name, data in chars.items():
        cid = char_ids[name]
        trust = data.get("trust", 0.5)
        if trust >= 0.7:
            mm.append(f"  class {cid} highTrust")
        elif trust >= 0.4:
            mm.append(f"  class {cid} midTrust")
        else:
            mm.append(f"  class {cid} lowTrust")

    mermaid_src = "\n".join(mm)

    # ── Character relationship cards data ──
    char_cards = ""
    for name, data in chars.items():
        trust = data.get("trust", 0.5)
        trust_pct = int(trust * 100)
        rel = data.get("relationship", "")
        flags = data.get("flags", [])

        if trust >= 0.7:
            bar_color = "#2ea043"
            bar_bg = "#0d3320"
        elif trust >= 0.4:
            bar_color = "#d29922"
            bar_bg = "#332a14"
        else:
            bar_color = "#da3633"
            bar_bg = "#331414"

        flags_html = " ".join(
            f'<span style="display:inline-block;background:#1f2940;color:#58a6ff;padding:2px 8px;border-radius:10px;font-size:12px;margin:2px">{f}</span>'
            for f in flags
        ) if flags else '<span style="color:#484f58">暂无事件</span>'

        char_cards += f"""
    <div style="background:#161b22;border:1px solid #21262d;border-radius:8px;padding:16px;min-width:260px;flex:1">
      <div style="font-size:18px;font-weight:700;color:#c9d1d9;margin-bottom:6px">{name}</div>
      <div style="color:#8b949e;font-size:13px;margin-bottom:8px">{rel or '关系未明'}</div>
      <div style="background:{bar_bg};border-radius:4px;height:8px;margin-bottom:4px">
        <div style="background:{bar_color};border-radius:4px;height:100%;width:{trust_pct}%"></div>
      </div>
      <div style="font-size:13px;color:{bar_color};margin-bottom:10px">信任度 {trust_pct}%</div>
      <div style="display:flex;flex-wrap:wrap;gap:4px">{flags_html}</div>
    </div>"""

    # ── Node detail rows ──
    node_rows = ""
    for nid in sorted(nodes.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        node = nodes[nid]
        # Highlight character names in story preview
        text = node.get("text", "")[:60]
        for name in chars:
            text = text.replace(name, f'<mark style="background:#1f6feb33;color:#58a6ff;border-radius:2px">{name}</mark>')
        node_rows += f"<tr><td>{nid}</td><td>{node.get('turn','?')}</td><td>{node.get('scene','?')}</td><td>{node.get('status','?')}</td><td>{text}</td></tr>\n"

    # ── Build dashboard HTML ──
    import json as _json
    analytics_json = _json.dumps(analytics, ensure_ascii=False)
    s = analytics.get("summary", {})
    au = analytics.get("api_usage", {}).get("totals", {})
    bs = analytics.get("branch_stats", {})

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>星痕纪元 — 剧情仪表盘</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0d1117;color:#c9d1d9;font-family:system-ui,sans-serif;min-height:100vh}}
.header{{padding:20px 28px 12px;border-bottom:1px solid #21262d}}
.header h1{{font-size:22px;color:#58a6ff;margin-bottom:6px}}
.stats{{display:flex;flex-wrap:wrap;gap:16px;margin-top:8px}}
.stat{{background:#161b22;border:1px solid #21262d;border-radius:6px;padding:10px 16px;text-align:center;min-width:80px}}
.stat .val{{font-size:20px;font-weight:700;color:#c9d1d9}}
.stat .lbl{{font-size:11px;color:#8b949e;margin-top:2px}}
.toggle-bar{{display:flex;flex-wrap:wrap;gap:6px;padding:12px 28px;border-bottom:1px solid #21262d;background:#0d1117;position:sticky;top:0;z-index:10}}
.toggle-btn{{padding:5px 14px;border-radius:14px;border:1px solid #30363d;background:#161b22;color:#8b949e;cursor:pointer;font-size:13px;transition:all .2s}}
.toggle-btn.on{{background:#1f6feb;border-color:#58a6ff;color:#fff}}
.toggle-btn:hover{{border-color:#58a6ff}}
.section{{display:none;padding:20px 28px;border-bottom:1px solid #21262d}}
.section.on{{display:block}}
.section h2{{color:#58a6ff;font-size:16px;margin-bottom:14px}}
.chart-wrap{{max-width:700px;margin:0 auto;position:relative}}
.chart-wrap.wide{{max-width:900px}}
.graph-wrap{{display:flex;justify-content:center;overflow:auto}}
.char-cards{{display:flex;flex-wrap:wrap;gap:14px}}
.char-card{{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:14px;min-width:220px;flex:1}}
.char-card .name{{font-size:17px;font-weight:700;margin-bottom:4px}}
.char-card .rel{{color:#8b949e;font-size:12px;margin-bottom:8px}}
.char-card .bar-bg{{border-radius:4px;height:8px;margin-bottom:4px}}
.char-card .bar-fg{{border-radius:4px;height:100%}}
.char-card .trust-pct{{font-size:12px;margin-bottom:8px}}
.char-card .flags{{display:flex;flex-wrap:wrap;gap:4px}}
.char-card .flag{{display:inline-block;background:#1f2940;color:#58a6ff;padding:2px 8px;border-radius:10px;font-size:11px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;padding:7px 10px;background:#161b22;color:#8b949e;font-weight:600}}
td{{padding:7px 10px;border-top:1px solid #21262d}}
tr:hover td{{background:#161b22}}
.footer{{text-align:center;padding:18px;color:#484f58;font-size:11px;border-top:1px solid #21262d}}
a{{color:#58a6ff;text-decoration:none}}
@media(max-width:600px){{.stats{{gap:8px}}.stat{{min-width:60px;padding:8px 10px}}.stat .val{{font-size:16px}}}}
</style></head>
<body>
<div class="header">
<h1>🌳 星痕纪元 — 剧情仪表盘</h1>
<div class="stats">
<div class="stat"><div class="val">{s.get('turns',0)}</div><div class="lbl">轮次</div></div>
<div class="stat"><div class="val">{s.get('status','?')}</div><div class="lbl">状态</div></div>
<div class="stat"><div class="val">{s.get('characters',0)}</div><div class="lbl">角色</div></div>
<div class="stat"><div class="val">{s.get('total_words',0):,}</div><div class="lbl">总字数</div></div>
<div class="stat"><div class="val">{s.get('nodes',0)}</div><div class="lbl">节点</div></div>
<div class="stat"><div class="val">{s.get('edges',0)}</div><div class="lbl">分支</div></div>
<div class="stat"><div class="val">${{au.get('cost_usd',0):.4f}}</div><div class="lbl">费用</div></div>
<div class="stat"><div class="val">{au.get('total_tokens',0):,}</div><div class="lbl">Tokens</div></div>
</div>
</div>

<div class="toggle-bar">
<button class="toggle-btn on" onclick="t('chars')">🎭 角色卡片</button>
<button class="toggle-btn" onclick="t('graph')">🌳 剧情图谱</button>
<button class="toggle-btn" onclick="t('trust')">📈 信任曲线</button>
<button class="toggle-btn" onclick="t('timeline')">⏱️ 状态时间线</button>
<button class="toggle-btn" onclick="t('words')">📊 字数趋势</button>
<button class="toggle-btn" onclick="t('choices')">🎯 选择偏好</button>
<button class="toggle-btn" onclick="t('api')">💰 API用量</button>
<button class="toggle-btn" onclick="t('charfreq')">👥 角色出场</button>
<button class="toggle-btn" onclick="t('nodes')">📋 节点详情</button>
<button class="toggle-btn" onclick="t('factions')">🏛️ 世界势力</button>
<button class="toggle-btn" onclick="t('branch')">🔀 分支统计</button>
</div>

<div id="sec-chars" class="section on">{_build_char_cards(chars)}</div>

<div id="sec-graph" class="section">
<div class="graph-wrap"><div class="mermaid">{mermaid_src}</div></div>
<p style="text-align:center;color:#8b949e;font-size:12px;margin-top:8px">▭ 剧情 | ╱╲ 角色 &nbsp;<span style="color:#2ea043">●</span>高 <span style="color:#d29922">●</span>中 <span style="color:#da3633">●</span>低信任 &nbsp; 虚线=出场</p>
</div>

<div id="sec-trust" class="section">
<h2>📈 角色指标变化曲线</h2>
<div id="metricCharts"></div>
</div>

<div id="sec-timeline" class="section"><h2>⏱️ 剧情状态时间线</h2><div class="chart-wrap wide"><canvas id="timelineChart"></canvas></div></div>

<div id="sec-words" class="section"><h2>📊 每轮 AI 生成字数</h2><div class="chart-wrap"><canvas id="wordsChart"></canvas></div></div>

<div id="sec-choices" class="section"><h2>🎯 玩家选择偏好</h2><div class="chart-wrap" style="max-width:350px"><canvas id="choicesChart"></canvas></div></div>

<div id="sec-api" class="section"><h2>💰 API Token 用量</h2><div class="chart-wrap"><canvas id="apiChart"></canvas></div></div>

<div id="sec-charfreq" class="section"><h2>👥 角色出场频率</h2><div class="chart-wrap"><canvas id="charFreqChart"></canvas></div></div>

<div id="sec-nodes" class="section"><h2>📋 剧情节点详情</h2><div style="overflow-x:auto"><table><tr><th>Node</th><th>Turn</th><th>Scene</th><th>Status</th><th>Preview</th></tr>{node_rows}</table></div></div>

<div id="sec-factions" class="section">
<h2>🏛️ 世界势力</h2>
<div id="factionCards"></div>
<div id="factionCharts"></div>
</div>

<div id="sec-branch" class="section"><h2>🔀 分支树统计</h2>
<div class="stats" style="justify-content:center">
<div class="stat"><div class="val">{bs.get('total_nodes',0)}</div><div class="lbl">总节点</div></div>
<div class="stat"><div class="val">{bs.get('leaf_count',0)}</div><div class="lbl">叶子节点</div></div>
<div class="stat"><div class="val">{bs.get('max_depth',0)}</div><div class="lbl">最大深度</div></div>
<div class="stat"><div class="val">{bs.get('avg_branches',0)}</div><div class="lbl">平均分支</div></div>
</div></div>

<div class="footer">Prompt OS Galgame Runtime v1 · 星痕纪元<br>Mermaid.js + Chart.js · 双击 HTML 即可查看 · 每轮自动更新</div>

<script>
const A = {analytics_json};
function t(id){{var s=document.getElementById('sec-'+id);var b=document.querySelectorAll('.toggle-btn');if(s){{s.classList.toggle('on')}};var on=document.getElementById('sec-'+id).classList.contains('on');b.forEach(function(btn){{if(btn.textContent.includes(document.getElementById('sec-'+id).querySelector('h2')?document.getElementById('sec-'+id).querySelector('h2').textContent:'')||btn.onclick.toString().includes("'"+id+"'")){{if(on)btn.classList.add('on');else btn.classList.remove('on')}}}})}}
function toggleBtn(id){{var s=document.getElementById('sec-'+id);s.classList.toggle('on');return s.classList.contains('on');}}
// Fix toggle buttons: simpler approach
document.querySelectorAll('.toggle-btn').forEach(function(btn){{btn.addEventListener('click',function(){{var id=this.getAttribute('onclick').match(/'([^']+)'/)[1];var s=document.getElementById('sec-'+id);var nowOn=s.classList.toggle('on');if(nowOn){{this.classList.add('on')}}else{{this.classList.remove('on')}}}})}});
// Set initial state: only chars on
document.querySelectorAll('.section').forEach(function(s){{if(s.id!=='sec-chars')s.classList.remove('on')}});
document.querySelectorAll('.toggle-btn').forEach(function(b){{var m=b.getAttribute('onclick').match(/'([^']+)'/);if(m&&m[1]!=='chars')b.classList.remove('on')}});

mermaid.initialize({{startOnLoad:true,theme:'dark',themeVariables:{{primaryColor:'#1f6feb',primaryTextColor:'#c9d1d9',lineColor:'#30363d',fontSize:'14px'}}}});

// ── Charts ──
Chart.defaults.color='#8b949e';Chart.defaults.borderColor='#21262d';
const colors=['#58a6ff','#3fb950','#d29922','#f85149','#bc8cff','#fea759','#7ee787'];

function makeChart(id,type,data,options){{return new Chart(document.getElementById(id),{{type:type,data:data,options:Object.assign({{responsive:true,maintainAspectRatio:true,plugins:{{legend:{{labels:{{color:'#8b949e'}}}}}},scales:type!=='pie'&&type!=='doughnut'?{{x:{{ticks:{{color:'#8b949e'}},grid:{{color:'#21262d'}}}},y:{{ticks:{{color:'#8b949e'}},grid:{{color:'#21262d'}}}}}}:{{}}}},options)}})}}

// Dynamic metric curves — one chart per detected metric
(function(){{
  var mc=A.metrics_curves;if(!mc)return;
  var container=document.getElementById('metricCharts');
  var metrics=Object.keys(mc);
  metrics.forEach(function(metric,idx){{
    var curve=mc[metric];if(!curve||!curve.datasets||!curve.datasets.length)return;
    var label=curve.label||metric;
    // Create canvas + wrapper
    var wrap=document.createElement('div');wrap.className='chart-wrap';
    wrap.style.marginBottom='24px';
    var h3=document.createElement('h3');
    h3.style.cssText='color:#8b949e;font-size:14px;margin-bottom:8px;font-weight:400';
    h3.textContent=label;
    var canvas=document.createElement('canvas');canvas.id='metricChart'+idx;
    wrap.appendChild(h3);wrap.appendChild(canvas);
    container.appendChild(wrap);
    // Render chart
    new Chart(canvas,{{type:'line',data:{{labels:curve.labels,datasets:curve.datasets.map(function(d,i){{return{{label:d.name,data:d.data,borderColor:colors[i%7],backgroundColor:colors[i%7]+'22',tension:0.3,fill:false,pointRadius:4}}}})}},options:{{responsive:true,maintainAspectRatio:true,plugins:{{legend:{{labels:{{color:'#8b949e'}}}}}},scales:{{x:{{ticks:{{color:'#8b949e'}},grid:{{color:'#21262d'}}}},y:{{ticks:{{color:'#8b949e'}},grid:{{color:'#21262d'}},min:0,max:100}}}}}}}});
  }});
}})();}}

// Status timeline: horizontal stacked bar using canvas
(function(){{
  var tl=A.status_timeline;if(!tl||!tl.length)return;
  var statusColors={{'SETUP':'#58a6ff','BUILD':'#3fb950','TENSION':'#d29922','CLIMAX':'#f85149','COOLDOWN':'#bc8cff'}};
  var labels=tl.map(function(t){{return'T'+t.turn}});
  var datasets=[];
  var statuses=['SETUP','BUILD','TENSION','CLIMAX','COOLDOWN'];
  statuses.forEach(function(st){{
    var data=tl.map(function(t){{return t.status===st?1:0}});
    datasets.push({{label:st,data:data,backgroundColor:statusColors[st]||'#484f58',borderRadius:2,borderSkipped:false}});
  }});
  new Chart(document.getElementById('timelineChart'),{{type:'bar',data:{{labels:labels,datasets:datasets}},options:{{responsive:true,indexAxis:'y',stacked:true,plugins:{{legend:{{labels:{{color:'#8b949e'}}}},tooltip:{{callbacks:{{label:function(c){{var t=tl[c.dataIndex];return t.status+' — '+t.scene}}}}}}}},scales:{{x:{{stacked:true,display:false}},y:{{stacked:true,ticks:{{color:'#8b949e'}},grid:{{display:false}}}}}}}}}});
}})();

// Word counts
if(A.word_counts&&A.word_counts.length){{makeChart('wordsChart','bar',{{labels:A.word_counts.map(function(w){{return'T'+w.turn}}),datasets:[{{label:'字数',data:A.word_counts.map(function(w){{return w.chars}}),backgroundColor:'#58a6ff66',borderColor:'#58a6ff',borderRadius:3}},{{label:'词数',data:A.word_counts.map(function(w){{return w.words}}),backgroundColor:'#3fb95066',borderColor:'#3fb950',borderRadius:3}}]}},{{scales:{{y:{{beginAtZero:true}}}}}})}}

// Choice pie
if(A.choice_stats&&A.choice_stats.labels){{makeChart('choicesChart','doughnut',{{labels:A.choice_stats.labels,datasets:[{{data:A.choice_stats.counts,backgroundColor:['#58a6ff','#3fb950','#d29922','#f85149'],borderWidth:0}}]}})}}

// API usage
if(A.api_usage&&A.api_usage.per_turn&&A.api_usage.per_turn.length){{makeChart('apiChart','bar',{{labels:A.api_usage.per_turn.map(function(u){{return'T'+u.turn}}),datasets:[{{label:'Prompt',data:A.api_usage.per_turn.map(function(u){{return u.prompt_tokens}}),backgroundColor:'#58a6ff66',borderColor:'#58a6ff',borderRadius:3}},{{label:'Completion',data:A.api_usage.per_turn.map(function(u){{return u.completion_tokens}}),backgroundColor:'#3fb95066',borderColor:'#3fb950',borderRadius:3}}]}},{{scales:{{x:{{stacked:true}},y:{{stacked:true,beginAtZero:true}}}}}})}}

// Character frequency
if(A.character_frequency&&A.character_frequency.labels){{makeChart('charFreqChart','bar',{{labels:A.character_frequency.labels,datasets:[{{label:'出场轮次',data:A.character_frequency.counts,backgroundColor:['#58a6ff','#3fb950','#d29922','#f85149','#bc8cff'],borderRadius:3}}]}},{{scales:{{y:{{beginAtZero:true,ticks:{{stepSize:1}}}}}}}})}}

// Faction cards + reputation charts
(function(){{
  var fc=A.faction_curves;if(!fc)return;
  var cardContainer=document.getElementById('factionCards');
  var chartContainer=document.getElementById('factionCharts');
  var fColor=['#58a6ff','#d29922','#f85149','#3fb950','#bc8cff'];
  var fIdx=0;
  Object.keys(fc).forEach(function(name){{
    var f=fc[name];if(!f)return;
    var rep=f.datasets&&f.datasets[0]?f.datasets[0].data:[];var lastRep=rep.length?rep[rep.length-1]:50;
    var c=fColor[fIdx%5];fIdx++;
    // Card
    var card=document.createElement('div');
    card.style.cssText='display:inline-block;background:#161b22;border:1px solid #21262d;border-radius:8px;padding:14px;margin:6px;min-width:200px;vertical-align:top';
    card.innerHTML='<div style="font-size:16px;font-weight:700;margin-bottom:4px">'+name+'</div>'
      +'<div style="color:#8b949e;font-size:12px;margin-bottom:6px">'+(f.role||'')+'</div>'
      +'<div style="background:'+c+'22;border-radius:4px;height:8px;margin-bottom:4px"><div style="background:'+c+';border-radius:4px;height:100%;width:'+lastRep+'%"></div></div>'
      +'<div style="font-size:12px;color:'+c+'">声望 '+lastRep+'%</div>';
    cardContainer.appendChild(card);
    // Chart
    var wrap=document.createElement('div');wrap.className='chart-wrap';wrap.style.marginTop='16px';
    var h3=document.createElement('h3');h3.style.cssText='color:#8b949e;font-size:14px;margin-bottom:8px;font-weight:400';h3.textContent=f.label;
    var canvas=document.createElement('canvas');
    wrap.appendChild(h3);wrap.appendChild(canvas);
    chartContainer.appendChild(wrap);
    new Chart(canvas,{{type:'line',data:{{labels:f.labels,datasets:[{{label:name,data:f.datasets[0].data,borderColor:c,backgroundColor:c+'22',tension:0.3,fill:false,pointRadius:4}}]}},options:{{responsive:true,maintainAspectRatio:true,plugins:{{legend:{{labels:{{color:'#8b949e'}}}}}},scales:{{x:{{ticks:{{color:'#8b949e'}},grid:{{color:'#21262d'}}}},y:{{ticks:{{color:'#8b949e'}},grid:{{color:'#21262d'}},min:0,max:100}}}}}}}});
  }});
}})();
</script>
</body></html>"""

    path = vault / STORY_DIR / "剧情图谱.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def _build_char_cards(chars: dict) -> str:
    """Build HTML character cards with trust bars and event flags."""
    if not chars:
        return '<p style="color:#484f58">暂无角色数据</p>'

    cards = '<div class="char-cards">'
    for name, data in chars.items():
        trust = data.get("trust", 0.5)
        trust_pct = int(trust * 100)
        rel = data.get("relationship", "")
        flags = data.get("flags", [])

        if trust >= 0.7:
            bar_color, bar_bg = "#2ea043", "#0d3320"
        elif trust >= 0.4:
            bar_color, bar_bg = "#d29922", "#332a14"
        else:
            bar_color, bar_bg = "#da3633", "#331414"

        flags_html = " ".join(
            f'<span class="flag">{f}</span>' for f in flags
        ) if flags else '<span style="color:#484f58;font-size:11px">暂无事件</span>'

        cards += f"""
<div class="char-card">
  <div class="name">{name}</div>
  <div class="rel">{rel or '关系未明'}</div>
  <div class="bar-bg" style="background:{bar_bg}">
    <div class="bar-fg" style="background:{bar_color};width:{trust_pct}%"></div>
  </div>
  <div class="trust-pct" style="color:{bar_color}">信任度 {trust_pct}%</div>
  <div class="flags">{flags_html}</div>
</div>"""
    cards += '</div>'
    return cards


def _write_index(vault: Path) -> None:
    """Write the master index with Dataview queries."""
    state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    memory = io_utils.read_json(config.MEMORY_PATH)

    chapters_dir = vault / CHAPTERS_DIR
    chapter_count = len(list(chapters_dir.glob("*.md"))) if chapters_dir.exists() else 0

    lines: list[str] = []
    lines.append("---")
    lines.append("title: 星痕纪元")
    lines.append(f"turns: {state.get('turn', 0)}")
    lines.append(f"status: {state.get('status', '?')}")
    lines.append(f"chapters: {chapter_count}")
    lines.append(f"updated: {datetime.now().isoformat()}")
    lines.append("tags: [index, dashboard]")
    lines.append("---")
    lines.append("")
    lines.append(f"# ⭐ 星痕纪元")
    lines.append("")
    lines.append(f"> **进度:** 第 {state.get('turn', 0)} 轮  |  "
                 f"**状态:** {state.get('status', '?')}  |  "
                 f"**章节:** {chapter_count}")
    lines.append("")
    lines.append("## 📖 快速导航")
    lines.append("")
    lines.append(f"- [[完整叙事|完整叙事]] — 从头到尾读")
    lines.append(f"- [[剧情图谱|剧情图谱]] — 分支可视化")
    lines.append("")
    lines.append("## 🎭 角色")
    lines.append("")
    chars = memory.get("characters", {})
    if chars:
        for name, data in chars.items():
            trust = data.get("trust", 0.5)
            filename = _sanitize_filename(name)
            lines.append(f"- [[Characters/{filename}|{name}]] — 信任度 {trust:.0%}")
    else:
        lines.append("*尚未登场*")
    lines.append("")

    # Dataview queries (work if Dataview plugin is installed)
    lines.append("## 📋 所有章节 (Dataview)")
    lines.append("")
    lines.append("```dataview")
    lines.append("TABLE turn, status, scene, choice")
    lines.append('FROM "星痕纪元/Chapters"')
    lines.append("SORT turn ASC")
    lines.append("```")
    lines.append("")

    path = vault / STORY_DIR / "_index.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter from markdown text."""
    lines = text.split("\n")
    result: list[str] = []
    in_fm = False
    for line in lines:
        if line.strip() == "---":
            in_fm = not in_fm
            continue
        if not in_fm:
            result.append(line)
    return "\n".join(result)
