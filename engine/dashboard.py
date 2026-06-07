"""
dashboard.py — Unified Dashboard Generator
============================================
Single source of truth for the analytics dashboard HTML.
Used by:
  • Web route  /dashboard  (dynamic, served per request)
  • Per-turn    output/dashboard.html  (standalone, double-click to open)
  • Obsidian    vault 星痕纪元/剧情图谱.html  (optional)

No Obsidian dependency — writes to output/ directory by default.
"""

import json as _json
import logging
import re
from pathlib import Path

import config
from engine import io_utils
from engine.router import load_graph
from engine.analytics import compute_all

logger = logging.getLogger(__name__)


def _sanitize_mermaid(text: str) -> str:
    """Escape user-controlled text for safe Mermaid.js embedding.

    Mermaid.js has a history of XSS CVEs — unescaped text in node labels
    can inject JavaScript via event handlers, closing syntax, or HTML tags.
    This function neutralises the known attack vectors.
    """
    if not isinstance(text, str):
        return str(text)
    # 1. Backslashes first (they would escape our subsequent escaping)
    text = text.replace("\\", "\\\\")
    # 2. Double quotes → single quotes (Mermaid uses " for attribute boundaries)
    text = text.replace('"', "'")
    # 3. Collapse newlines — they can terminate Mermaid lines prematurely
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    # 4. HTML tag brackets — prevent injection of <script>, <img onerror=…>, etc.
    text = text.replace("<", "‹").replace(">", "›")
    # 5. Brackets / braces / pipe / hash — break node or edge label delimiters in Mermaid 11
    text = text.replace("[", "［").replace("]", "］")
    text = text.replace("{", "｛").replace("}", "｝")
    text = text.replace("|", "｜")
    text = text.replace("#", "＃")
    text = text.replace(";", "；")
    # 6. Mermaid arrow syntax — prevent label text from being parsed as graph edges
    text = re.sub(r"-{2,}>", "→", text)
    text = re.sub(r"<-{2,}", "←", text)
    # 7. Mermaid link syntax `-- text -->` already handled by arrow substitution above
    # 8. Truncate to reasonable length
    if len(text) > 200:
        text = text[:197] + "…"
    return text


def _sanitize_html(text: str) -> str:
    """Minimal HTML escape for inline text in dashboard HTML."""
    if not isinstance(text, str):
        return str(text)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

# CDN URLs & local filenames for offline bundling
_JS_LIBS = {
    "mermaid.min.js": "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js",
    "chart.umd.min.js": "https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js",
}


def ensure_local_js() -> None:
    """Download Chart.js & Mermaid.js to output/ so HTML works offline."""
    import urllib.request

    out = config.OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    for filename, url in _JS_LIBS.items():
        dest = out / filename
        if dest.exists():
            continue
        logger.info("Downloading %s → %s ...", filename, dest)
        try:
            urllib.request.urlretrieve(url, dest)
            logger.info("Downloaded %s (%d bytes)", filename, dest.stat().st_size)
        except Exception as exc:
            logger.warning("Failed to download %s: %s", filename, exc)


# ── Public API ──────────────────────────────────────────────────────

def collect_data() -> dict:
    """Gather all data needed by the dashboard into one dict."""
    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    except Exception:
        state = {}
    try:
        memory = io_utils.read_json(config.MEMORY_PATH)
    except Exception:
        memory = {}
    try:
        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
    except Exception:
        world_pack = {}
    graph = load_graph()
    analytics = compute_all()

    # API usage logs for total cost display
    api_logs = []
    if config.API_USAGE_PATH.exists():
        try:
            for line in config.API_USAGE_PATH.read_text(encoding="utf-8").strip().split("\n"):
                if line.strip():
                    api_logs.append(_json.loads(line))
        except Exception:
            pass

    prompt_t = sum(e.get("prompt_tokens", 0) for e in api_logs)
    comp_t = sum(e.get("completion_tokens", 0) for e in api_logs)
    cost = prompt_t / 1_000_000 * 0.14 + comp_t / 1_000_000 * 0.28

    return {
        "world_title": world_pack.get("world", {}).get("title", "Galgame"),
        "turn": state.get("turn", 0),
        "status": state.get("status", "SETUP"),
        "char_count": len(memory.get("characters", {})),
        "total_tokens": prompt_t + comp_t,
        "cost_usd": round(cost, 4),
        "memory": memory,
        "graph": graph,
        "analytics": analytics,
    }


def build_html(data: dict | None = None) -> str:
    """
    Build the complete dashboard HTML page.
    If data is None, collects fresh data internally.
    """
    if data is None:
        data = collect_data()

    world_title = data["world_title"]
    memory = data["memory"]
    graph = data["graph"]
    analytics = data["analytics"]
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])
    chars = memory.get("characters", {})
    factions = memory.get("factions", {})

    s = analytics.get("summary", {})
    au = analytics.get("api_usage", {}).get("totals", {})
    bs = analytics.get("branch_stats", {})
    analytics_json = _json.dumps(analytics, ensure_ascii=False)

    return _HTML_TEMPLATE.format(
        world_title=world_title,
        turn=s.get("turns", 0),
        status=s.get("status", "?"),
        char_count=s.get("characters", 0),
        total_words=s.get("total_words", 0),
        node_count=s.get("nodes", 0),
        edge_count=s.get("edges", 0),
        cost_usd=au.get("cost_usd", 0),
        total_tokens=au.get("total_tokens", 0),
        analytics_json=analytics_json,
        char_cards=_build_char_cards(chars),
        mermaid_src=_build_mermaid(nodes, edges, chars),
        node_rows=_build_node_rows(nodes, chars),
        faction_cards=_build_faction_cards(factions),
        faction_graph=_build_faction_graph(memory),
        bs_nodes=bs.get("total_nodes", 0),
        bs_leaves=bs.get("leaf_count", 0),
        bs_depth=bs.get("max_depth", 0),
        bs_avg=bs.get("avg_branches", 0),
    )


def write_standalone(output_path: Path | None = None) -> Path:
    """Write the dashboard HTML to disk. Returns the output path."""
    if output_path is None:
        output_path = config.DASHBOARD_HTML_PATH
    ensure_local_js()
    html = build_html()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    logger.info("Dashboard written → %s", output_path)
    return output_path


# ── Section builders ────────────────────────────────────────────────

def _build_mermaid(nodes: dict, edges: list, chars: dict) -> str:
    """Build Mermaid graph source with story nodes + character nodes."""
    mm = ["graph TD"]

    # Story nodes
    # Pre-compute character → node mapping (avoid O(n×m) nested loop)
    char_to_nodes: dict[str, list[str]] = {}
    for nid, node in nodes.items():
        node_text = node.get("text", "")
        for name in chars:
            if name in node_text:
                char_to_nodes.setdefault(name, []).append(nid)

    for nid, node in nodes.items():
        turn = node.get("turn", "?")
        text = _sanitize_mermaid(node.get("text", "")[:30])
        mm.append(f'  n{nid}["T{turn}: {text}"]')

    # Character nodes + connections
    char_ids = {}
    for i, (name, data) in enumerate(chars.items()):
        cid = f"c{i}"
        char_ids[name] = cid
        trust_pct = round(data.get("trust", 0.5) * 100)
        label = _sanitize_mermaid(f"{name} ({trust_pct}%)")
        mm.append(f'  {cid}["{label}"]')
        for nid in char_to_nodes.get(name, []):
            mm.append(f"  {cid} -.-> n{nid}")

    # Story edges
    for edge in edges:
        frm = edge["from"]
        to = edge["to"]
        choice = _sanitize_mermaid(edge.get("choice", ""))
        mm.append(f'  n{frm} -->|{choice}| n{to}')

    # Styles
    mm.append("")
    mm.append("  classDef story fill:#1f6feb,stroke:#58a6ff,color:#fff")
    mm.append("  classDef highTrust fill:#2ea043,stroke:#3fb950,color:#fff")
    mm.append("  classDef midTrust fill:#d29922,stroke:#e3b341,color:#fff")
    mm.append("  classDef lowTrust fill:#da3633,stroke:#f85149,color:#fff")
    mm.append("")

    story_ids = " ".join(f"n{nid}" for nid in nodes)
    if story_ids:
        mm.append(f"  class {story_ids} story")

    for name, data in chars.items():
        cid = char_ids[name]
        trust = data.get("trust", 0.5)
        if trust >= 0.7:
            mm.append(f"  class {cid} highTrust")
        elif trust >= 0.4:
            mm.append(f"  class {cid} midTrust")
        else:
            mm.append(f"  class {cid} lowTrust")

    return "\n".join(mm)


def _build_char_cards(chars: dict) -> str:
    """Build HTML character cards with trust bars."""
    if not chars:
        return '<p style="color:#484f58">暂无角色数据</p>'

    cards = ['<div class="char-cards">']
    for name, data in chars.items():
        trust = data.get("trust", 0.5)
        trust_pct = round(trust * 100)
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

        cards.append(f"""
<div class="char-card">
  <div class="name">{name}</div>
  <div class="rel">{rel or '关系未明'}</div>
  <div class="bar-bg" style="background:{bar_bg}">
    <div class="bar-fg" style="background:{bar_color};width:{trust_pct}%"></div>
  </div>
  <div class="trust-pct" style="color:{bar_color}">信任度 {trust_pct}%</div>
  <div class="flags">{flags_html}</div>
</div>""")

    cards.append('</div>')
    return "".join(cards)


def _build_node_rows(nodes: dict, chars: dict) -> str:
    """Build HTML table rows for node detail panel."""
    rows = []
    for nid in sorted(nodes.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        node = nodes[nid]
        text = _sanitize_html(node.get("text", "")[:60])
        for name in chars:
            safe_name = _sanitize_html(name)
            if safe_name in text:
                text = text.replace(
                    safe_name,
                    f'<mark style="background:#1f6feb33;color:#58a6ff;border-radius:2px">{safe_name}</mark>'
                )
        rows.append(
            f"<tr><td>{nid}</td><td>{node.get('turn','?')}</td>"
            f"<td>{_sanitize_html(str(node.get('scene','?')))}</td><td>{_sanitize_html(str(node.get('status','?')))}</td>"
            f"<td>{text}</td></tr>"
        )
    return "\n".join(rows)


def _build_faction_cards(factions: dict) -> str:
    """Build HTML faction cards for the dashboard."""
    if not factions:
        return ""
    cards = []
    for name, data in factions.items():
        rep = int(data.get("reputation", 0.5) * 100)
        ftype = data.get("type", "other")
        goals = data.get("goals", [])
        resources = data.get("resources", [])
        influence = data.get("influence", 50)
        leader = data.get("leader", "")
        rel_player = data.get("relation_to_player", "neutral")
        if rep >= 70:
            color = "#2ea043"
        elif rep >= 40:
            color = "#d29922"
        else:
            color = "#da3633"
        rel_badge = {
            "ally": "#2ea043", "friendly": "#3fb950",
            "neutral": "#8b949e", "hostile": "#d29922", "enemy": "#da3633",
        }.get(rel_player, "#8b949e")
        goals_html = "".join(f'<li style="font-size:11px;color:#8b949e">{g}</li>' for g in goals[:3])
        res_html = ", ".join(resources[:4])
        cards.append(
            f'<div style="display:inline-block;background:#161b22;border:1px solid #21262d;'
            f'border-radius:8px;padding:14px;margin:6px;min-width:220px;vertical-align:top">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">'
            f'<div style="font-size:16px;font-weight:700">{name}</div>'
            f'<span style="background:{rel_badge}22;color:{rel_badge};border:1px solid {rel_badge}44;'
            f'border-radius:10px;padding:2px 8px;font-size:10px">{rel_player}</span>'
            f'</div>'
            f'<div style="color:#8b949e;font-size:11px;margin-bottom:2px">{ftype}</div>'
            f'<div style="background:{color}22;border-radius:4px;height:8px;margin-bottom:4px">'
            f'<div style="background:{color};border-radius:4px;height:100%;width:{rep}%"></div></div>'
            f'<div style="font-size:11px;color:{color};margin-bottom:4px">声望 {rep}% &nbsp;|&nbsp; 影响力 {influence}</div>'
            f'<div style="font-size:10px;color:#8b949e">资源: {res_html or "无"}</div>'
            f'<ul style="margin:4px 0 0 14px;padding:0">{goals_html or ""}</ul>'
            f'</div>'
        )
    return "".join(cards)


def _build_faction_graph(memory: dict) -> str:
    """Build Mermaid graph showing inter-faction attitude network."""
    factions = memory.get("factions", {})
    attitudes = memory.get("faction_attitudes", {})

    if not factions:
        return ""

    mm = ["graph LR"]

    # Faction nodes
    fid_map: dict[str, str] = {}
    for i, (name, data) in enumerate(factions.items()):
        fid = f"f{i}"
        fid_map[name] = fid
        rep = int(data.get("reputation", 0.5) * 100)
        label = _sanitize_mermaid(f"{name}\\n声望 {rep}%")
        # Styling: solid for high rep, dashed for low
        style = "fill:#161b22,stroke:#58a6ff,color:#c9d1d9"
        if rep >= 70:
            style = "fill:#0d3320,stroke:#2ea043,color:#2ea043"
        elif rep >= 40:
            style = "fill:#332a14,stroke:#d29922,color:#d29922"
        else:
            style = "fill:#331414,stroke:#da3633,color:#da3633"
        mm.append(f'  {fid}["{label}"]')
        mm.append(f"  style {fid} {style}")

    # Attitude edges (only show non-trivial ones)
    edge_count = 0
    for a, targets in attitudes.items():
        if a not in fid_map:
            continue
        for b, data in targets.items():
            if b not in fid_map:
                continue
            att = data.get("attitude", 0.5)
            if abs(att - 0.5) < 0.1:
                continue  # skip near-neutral
            fa = fid_map[a]
            fb = fid_map[b]
            label = f"{att:.0%}"
            # Edge style based on attitude
            if att >= 0.7:
                style = "stroke:#2ea043,stroke-width:2px"  # allied - thick green
            elif att >= 0.55:
                style = "stroke:#3fb950,stroke-width:1.5px"  # friendly
            elif att <= 0.3:
                style = "stroke:#da3633,stroke-width:2px,stroke-dasharray:5"  # hostile - dashed red
            elif att <= 0.45:
                style = "stroke:#d29922,stroke-width:1px,stroke-dasharray:3"  # cool
            else:
                style = "stroke:#484f58,stroke-width:1px"  # neutral
            flags_str = " | ".join(data.get("flags", [])[:2])
            edge_label = f"{label}"
            if flags_str:
                edge_label += f"\\n{_sanitize_mermaid(flags_str)}"
            edge_label = _sanitize_mermaid(edge_label)
            mm.append(f'  {fa} -->|{edge_label}| {fb}')
            mm.append(f"  linkStyle {edge_count} {style}")
            edge_count += 1

    if edge_count == 0:
        mm.append('  note["势力间暂无显著关系"]')

    return "\n".join(mm)


# ── HTML Template ───────────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{world_title} — 剧情仪表盘</title>
<script src="./mermaid.min.js"></script>
<script src="./chart.umd.min.js"></script>
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
<div style="display:flex;align-items:center;justify-content:space-between">
<h1>🌳 {world_title} — 剧情仪表盘</h1>
<a href="/" style="display:inline-block;padding:5px 14px;background:#1c2333;border:1px solid #58a6ff;border-radius:6px;color:#58a6ff;text-decoration:none;font-size:0.82em">← 返回游戏</a>
</div>
<div class="stats">
<div class="stat"><div class="val">{turn}</div><div class="lbl">轮次</div></div>
<div class="stat"><div class="val">{status}</div><div class="lbl">状态</div></div>
<div class="stat"><div class="val">{char_count}</div><div class="lbl">角色</div></div>
<div class="stat"><div class="val">{total_words:,}</div><div class="lbl">总字数</div></div>
<div class="stat"><div class="val">{node_count}</div><div class="lbl">节点</div></div>
<div class="stat"><div class="val">{edge_count}</div><div class="lbl">分支</div></div>
<div class="stat"><div class="val">${cost_usd:.4f}</div><div class="lbl">费用</div></div>
<div class="stat"><div class="val">{total_tokens:,}</div><div class="lbl">Tokens</div></div>
</div>
</div>

<div class="toggle-bar">
<button class="toggle-btn on" onclick="t('chars')">🎭 角色卡片</button>
<button class="toggle-btn" onclick="t('graph')">🌳 剧情图谱</button>
<button class="toggle-btn" onclick="t('trust')">📈 指标曲线</button>
<button class="toggle-btn" onclick="t('timeline')">⏱️ 状态时间线</button>
<button class="toggle-btn" onclick="t('words')">📊 字数趋势</button>
<button class="toggle-btn" onclick="t('choices')">🎯 选择偏好</button>
<button class="toggle-btn" onclick="t('api')">💰 API用量</button>
<button class="toggle-btn" onclick="t('charfreq')">👥 角色出场</button>
<button class="toggle-btn" onclick="t('nodes')">📋 节点详情</button>
<button class="toggle-btn" onclick="t('factions')">🏛️ 世界势力</button>
<button class="toggle-btn" onclick="t('factionGraph')">🕸️ 势力关系</button>
<button class="toggle-btn" onclick="t('factionPower')">⚔️ 势力实力</button>
<button class="toggle-btn" onclick="t('artifacts')">🗝️ 关键物品</button>
<button class="toggle-btn" onclick="t('branch')">🔀 分支统计</button>
</div>

<div id="sec-chars" class="section on">{char_cards}</div>

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
<div id="factionCards">{faction_cards}</div>
<div id="factionCharts"></div>
</div>

<div id="sec-factionPower" class="section">
<h2>⚔️ 势力实力对比（军事/经济/政治/科技）</h2>
<div class="chart-wrap wide"><canvas id="factionPowerChart"></canvas></div>
</div>

<div id="sec-artifacts" class="section">
<h2>🗝️ 关键物品</h2>
<div style="overflow-x:auto"><table id="artifactTable">
<tr><th>物品</th><th>类型</th><th>持有者</th><th>重要度</th><th>状态</th><th>转移次数</th></tr>
</table></div>
</div>

<div id="sec-factionGraph" class="section">
<h2>🕸️ 势力关系图谱</h2>
<div class="graph-wrap"><div class="mermaid">{faction_graph}</div></div>
<p style="text-align:center;color:#8b949e;font-size:12px;margin-top:8px">
<span style="color:#2ea043">━━</span> 同盟/友好 &nbsp;
<span style="color:#d29922">╌╌</span> 冷淡 &nbsp;
<span style="color:#da3633">┅┅</span> 敌对 &nbsp;
节点颜色=声望
</p>
<div id="factionAttitudeCharts"></div>
</div>

<div id="sec-branch" class="section"><h2>🔀 分支树统计</h2>
<div class="stats" style="justify-content:center">
<div class="stat"><div class="val">{bs_nodes}</div><div class="lbl">总节点</div></div>
<div class="stat"><div class="val">{bs_leaves}</div><div class="lbl">叶子节点</div></div>
<div class="stat"><div class="val">{bs_depth}</div><div class="lbl">最大深度</div></div>
<div class="stat"><div class="val">{bs_avg}</div><div class="lbl">平均分支</div></div>
</div></div>

<div class="footer">Prompt OS Galgame Runtime v1 · {world_title}<br>Mermaid.js + Chart.js · 双击 HTML 即可查看 · 每轮自动更新</div>

<script>
const A = {analytics_json};
function t(id){{var s=document.getElementById('sec-'+id);if(!s)return;var wasOn=s.classList.toggle('on');var btns=document.querySelectorAll('.toggle-btn');btns.forEach(function(b){{var m=b.getAttribute('onclick');if(m&&m.indexOf("'"+id+"'")>=0){{if(wasOn)b.classList.add('on');else b.classList.remove('on');}}}});}}

// Init: only chars visible, all other panels hidden
document.querySelectorAll('.section').forEach(function(s){{if(s.id!=='sec-chars')s.classList.remove('on');}});
document.querySelectorAll('.toggle-btn').forEach(function(b){{var m=b.getAttribute('onclick');if(m&&m.indexOf("'chars'")<0)b.classList.remove('on');}});

mermaid.initialize({{startOnLoad:true,theme:'dark',themeVariables:{{primaryColor:'#1f6feb',primaryTextColor:'#c9d1d9',lineColor:'#30363d',fontSize:'14px'}}}});

// ── Charts ──
Chart.defaults.color='#8b949e';Chart.defaults.borderColor='#21262d';
const colors=['#58a6ff','#3fb950','#d29922','#f85149','#bc8cff','#fea759','#7ee787'];

function makeChart(id,type,data,options){{return new Chart(document.getElementById(id),{{type:type,data:data,options:Object.assign({{responsive:true,maintainAspectRatio:true,plugins:{{legend:{{labels:{{color:'#8b949e'}}}}}},scales:type!=='pie'&&type!=='doughnut'?{{x:{{ticks:{{color:'#8b949e'}},grid:{{color:'#21262d'}}}},y:{{ticks:{{color:'#8b949e'}},grid:{{color:'#21262d'}}}}}}:{{}}}},options)}})}}

// Dynamic metric curves
(function(){{
  var mc=A.metrics_curves;if(!mc)return;
  var container=document.getElementById('metricCharts');
  var metrics=Object.keys(mc);
  metrics.forEach(function(metric,idx){{
    var curve=mc[metric];if(!curve||!curve.datasets||!curve.datasets.length)return;
    var label=curve.label||metric;
    var wrap=document.createElement('div');wrap.className='chart-wrap';wrap.style.marginBottom='24px';
    var h3=document.createElement('h3');
    h3.style.cssText='color:#8b949e;font-size:14px;margin-bottom:8px;font-weight:400';
    h3.textContent=label;
    var canvas=document.createElement('canvas');canvas.id='metricChart'+idx;
    wrap.appendChild(h3);wrap.appendChild(canvas);
    container.appendChild(wrap);
    new Chart(canvas,{{type:'line',data:{{labels:curve.labels,datasets:curve.datasets.map(function(d,i){{return{{label:d.name,data:d.data,borderColor:colors[i%7],backgroundColor:colors[i%7]+'22',tension:0.3,fill:false,pointRadius:4}}}})}},options:{{responsive:true,maintainAspectRatio:true,plugins:{{legend:{{labels:{{color:'#8b949e'}}}}}},scales:{{x:{{ticks:{{color:'#8b949e'}},grid:{{color:'#21262d'}}}},y:{{ticks:{{color:'#8b949e'}},grid:{{color:'#21262d'}},min:0,max:100}}}}}}}});
  }});
}})();

// Status timeline
(function(){{
  var tl=A.status_timeline;if(!tl||!tl.length)return;
  var statusColors={{'SETUP':'#58a6ff','BUILD':'#3fb950','TENSION':'#d29922','CLIMAX':'#f85149','COOLDOWN':'#bc8cff'}};
  var labels=tl.map(function(t){{return'T'+t.turn}});
  var datasets=[];
  ['SETUP','BUILD','TENSION','CLIMAX','COOLDOWN'].forEach(function(st){{
    datasets.push({{label:st,data:tl.map(function(t){{return t.status===st?1:0}}),backgroundColor:statusColors[st]||'#484f58',borderRadius:2,borderSkipped:false}});
  }});
  new Chart(document.getElementById('timelineChart'),{{type:'bar',data:{{labels:labels,datasets:datasets}},options:{{responsive:true,indexAxis:'y',stacked:true,plugins:{{legend:{{labels:{{color:'#8b949e'}}}},tooltip:{{callbacks:{{label:function(c){{var t=tl[c.dataIndex];return t.status+' — '+t.scene}}}}}}}},scales:{{x:{{stacked:true,display:false}},y:{{stacked:true,ticks:{{color:'#8b949e'}},grid:{{display:false}}}}}}}}}});
}})();

// Word counts
if(A.word_counts&&A.word_counts.length){{makeChart('wordsChart','bar',{{labels:A.word_counts.map(function(w){{return'T'+w.turn}}),datasets:[{{label:'字数',data:A.word_counts.map(function(w){{return w.chars}}),backgroundColor:'#58a6ff66',borderColor:'#58a6ff',borderRadius:3}},{{label:'词数',data:A.word_counts.map(function(w){{return w.words}}),backgroundColor:'#3fb95066',borderColor:'#3fb950',borderRadius:3}}]}},{{scales:{{y:{{beginAtZero:true}}}}}})}}

// Choice doughnut
if(A.choice_stats&&A.choice_stats.labels){{makeChart('choicesChart','doughnut',{{labels:A.choice_stats.labels,datasets:[{{data:A.choice_stats.counts,backgroundColor:['#58a6ff','#3fb950','#d29922','#f85149'],borderWidth:0}}]}})}}

// API usage
if(A.api_usage&&A.api_usage.per_turn&&A.api_usage.per_turn.length){{makeChart('apiChart','bar',{{labels:A.api_usage.per_turn.map(function(u){{return'T'+u.turn}}),datasets:[{{label:'Prompt',data:A.api_usage.per_turn.map(function(u){{return u.prompt_tokens}}),backgroundColor:'#58a6ff66',borderColor:'#58a6ff',borderRadius:3}},{{label:'Completion',data:A.api_usage.per_turn.map(function(u){{return u.completion_tokens}}),backgroundColor:'#3fb95066',borderColor:'#3fb950',borderRadius:3}}]}},{{scales:{{x:{{stacked:true}},y:{{stacked:true,beginAtZero:true}}}}}})}}

// Character frequency
if(A.character_frequency&&A.character_frequency.labels){{makeChart('charFreqChart','bar',{{labels:A.character_frequency.labels,datasets:[{{label:'出场轮次',data:A.character_frequency.counts,backgroundColor:['#58a6ff','#3fb950','#d29922','#f85149','#bc8cff'],borderRadius:3}}]}},{{scales:{{y:{{beginAtZero:true,ticks:{{stepSize:1}}}}}}}})}}

// Faction reputation charts
(function(){{
  var fc=A.faction_curves;if(!fc)return;
  var chartContainer=document.getElementById('factionCharts');
  var fIdx=0;
  Object.keys(fc).forEach(function(name){{
    var f=fc[name];if(!f||!f.datasets||!f.datasets[0])return;
    var rep=f.datasets[0].data;var lastRep=rep.length?rep[rep.length-1]:50;
    var c=colors[fIdx%7];fIdx++;
    var wrap=document.createElement('div');wrap.className='chart-wrap';wrap.style.marginTop='16px';
    var h3=document.createElement('h3');
    h3.style.cssText='color:#8b949e;font-size:14px;margin-bottom:8px;font-weight:400';
    h3.textContent=f.label;
    var canvas=document.createElement('canvas');
    wrap.appendChild(h3);wrap.appendChild(canvas);
    chartContainer.appendChild(wrap);
    new Chart(canvas,{{type:'line',data:{{labels:f.labels,datasets:[{{label:name,data:f.datasets[0].data,borderColor:c,backgroundColor:c+'22',tension:0.3,fill:false,pointRadius:4}}]}},options:{{responsive:true,maintainAspectRatio:true,plugins:{{legend:{{labels:{{color:'#8b949e'}}}}}},scales:{{x:{{ticks:{{color:'#8b949e'}},grid:{{color:'#21262d'}}}},y:{{ticks:{{color:'#8b949e'}},grid:{{color:'#21262d'}},min:0,max:100}}}}}}}});
  }});
}})();

// Faction attitude charts
(function(){{
  var fac=A.faction_attitude_curves;if(!fac)return;
  var chartContainer=document.getElementById('factionAttitudeCharts');
  var aIdx=0;
  Object.keys(fac).forEach(function(key){{
    var f=fac[key];if(!f||!f.datasets||!f.datasets[0])return;
    var rep=f.datasets[0].data;var lastRep=rep.length?rep[rep.length-1]:50;
    var c=lastRep>=70?'#2ea043':lastRep>=40?'#d29922':'#da3633';
    var wrap=document.createElement('div');wrap.className='chart-wrap';wrap.style.marginTop='16px';
    var h3=document.createElement('h3');
    h3.style.cssText='color:#8b949e;font-size:14px;margin-bottom:8px;font-weight:400';
    h3.textContent=f.label;
    var canvas=document.createElement('canvas');
    wrap.appendChild(h3);wrap.appendChild(canvas);
    chartContainer.appendChild(wrap);
    new Chart(canvas,{{type:'line',data:{{labels:f.labels,datasets:[{{label:key,data:f.datasets[0].data,borderColor:c,backgroundColor:c+'22',tension:0.3,fill:false,pointRadius:4}}]}},options:{{responsive:true,maintainAspectRatio:true,plugins:{{legend:{{labels:{{color:'#8b949e'}}}}}},scales:{{x:{{ticks:{{color:'#8b949e'}},grid:{{color:'#21262d'}}}},y:{{ticks:{{color:'#8b949e'}},grid:{{color:'#21262d'}},min:0,max:100}}}}}}}});
  }});
}})();

// Faction power chart (horizontal bar)
(function(){{
  var fp=A.faction_power;if(!fp||!fp.datasets||!fp.datasets.length)return;
  var canvas=document.getElementById('factionPowerChart');
  if(!canvas)return;
  var colors=['#58a6ff','#3fb950','#d29922','#da3633','#bc8cff','#79c0ff','#f0883e','#56d364'];
  new Chart(canvas,{{
    type:'bar',
    data:{{
      labels:fp.labels,
      datasets:fp.datasets.map(function(ds,i){{return{{
        label:ds.name,
        data:ds.data,
        backgroundColor:colors[i%8]+'88',
        borderColor:colors[i%8],
        borderWidth:1
      }};}})
    }},
    options:{{
      indexAxis:'y',
      responsive:true,
      maintainAspectRatio:true,
      plugins:{{legend:{{labels:{{color:'#8b949e',font:{{size:11}}}}}}}},
      scales:{{
        x:{{ticks:{{color:'#8b949e',font:{{size:10}}}},grid:{{color:'#21262d'}},max:100}},
        y:{{ticks:{{color:'#8b949e',font:{{size:10}}}},grid:{{color:'#21262d'}}}}
      }}
    }}
  }});
}})();

// Artifact table
(function(){{
  var arts=A.artifacts;if(!arts||!arts.length)return;
  var tbl=document.getElementById('artifactTable');
  if(!tbl)return;
  var typeLabels={{personal:'个人',faction:'势力资产',world:'世界级'}};
  var statusLabels={{active:'进行中',lost:'已遗失',destroyed:'已销毁',sealed:'已封印'}};
  arts.forEach(function(a){{
    var row=tbl.insertRow();
    row.innerHTML='<td style="font-weight:600">'+a.name+'</td>'+
      '<td>'+((a.type&&typeLabels[a.type])||a.type||'?')+'</td>'+
      '<td>'+(a.ownerId||'无')+'</td>'+
      '<td>'+('⭐'.repeat(Math.ceil(a.importance/20)))+' '+a.importance+'</td>'+
      '<td>'+((a.status&&statusLabels[a.status])||a.status||'?')+'</td>'+
      '<td>'+(a.transferCount||0)+'</td>';
  }});
}})();
</script>
</body></html>"""
