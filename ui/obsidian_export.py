"""
obsidian_export.py — Enhanced Obsidian Markdown Export
========================================================
Generates Obsidian-compatible Markdown output:
  • Full story export with frontmatter
  • Mermaid.js story graph visualization
  • Chapter-by-chapter narrative view
"""

from datetime import datetime
from pathlib import Path
import sys

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config
from engine import io_utils
from engine.router import load_graph


def export_full_story(output_path: Path | None = None) -> Path:
    """
    Export the complete story from chapter.md + frontmatter
    to a clean Obsidian note.

    Returns the output path.
    """
    if output_path is None:
        output_path = config.OUTPUT_DIR / "full_story.md"

    # Read session state for metadata
    state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    memory = io_utils.read_json(config.MEMORY_PATH)

    lines: list[str] = []

    # Frontmatter
    lines.append("---")
    lines.append(f"title: 星痕纪元 — 完整叙事")
    lines.append(f"turns: {state.get('turn', 0)}")
    lines.append(f"status: {state.get('status', '?')}")
    lines.append(f"exported: {datetime.now().isoformat()}")
    lines.append("tags: [galgame, narrative, ai-generated]")
    lines.append("---")
    lines.append("")

    # Character summary from memory
    chars = memory.get("characters", {})
    if chars:
        lines.append("## 角色关系")
        lines.append("")
        for name, data in chars.items():
            trust = data.get("trust", 0.5)
            rel = data.get("relationship", "")
            flags = data.get("flags", [])
            lines.append(f"- **{name}**: 信任度 {trust:.0%}, {rel}")
            if flags:
                lines.append(f"  - 事件: {', '.join(flags)}")
        lines.append("")

    # Story graph in Mermaid
    lines.append("## 剧情分支图")
    lines.append("")
    lines.extend(_generate_mermaid())
    lines.append("")

    # Full story from chapter.md
    lines.append("## 完整叙事")
    lines.append("")

    # Copy chapter content (strip per-chapter frontmatter for clean output)
    try:
        raw = config.CHAPTER_PATH.read_text(encoding="utf-8")
        # Remove YAML frontmatter blocks (between --- markers)
        cleaned = _strip_frontmatter_blocks(raw)
        lines.append(cleaned)
    except FileNotFoundError:
        lines.append("*尚无章节内容*")
    lines.append("")

    # Write
    content = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    return output_path


def export_graph_view(output_path: Path | None = None) -> Path:
    """
    Export a standalone Mermaid graph visualization of the story tree.

    Returns the output path.
    """
    if output_path is None:
        output_path = config.OUTPUT_DIR / "graph_view.md"

    lines: list[str] = [
        "---",
        "title: 剧情分支图 — Story Graph",
        f"exported: {datetime.now().isoformat()}",
        "---",
        "",
        "# 剧情分支图",
        "",
        "```mermaid",
        *_generate_mermaid(),
        "```",
        "",
    ]

    # Add node details
    graph = load_graph()
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])

    lines.append("## 节点详情")
    lines.append("")
    for nid, node in nodes.items():
        lines.append(f"### Node {nid} — Turn {node.get('turn', '?')}")
        lines.append(f"- **场景**: {node.get('scene', '?')}")
        lines.append(f"- **状态**: {node.get('status', '?')}")
        lines.append(f"- **内容**: {node.get('text', '')}")
        choices = node.get("choices", {})
        if choices:
            lines.append("- **选项**:")
            for c, target in choices.items():
                lines.append(f"  - {c} → Node {target or '?'}")
        lines.append("")

    lines.append("## 边 (Edges)")
    lines.append("")
    lines.append("| From | Choice | To | Turn |")
    lines.append("|------|--------|----|------|")
    for edge in edges:
        lines.append(
            f"| {edge['from']} | {edge['choice']} | {edge['to']} | {edge['turn']} |"
        )
    lines.append("")

    content = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    return output_path


def _generate_mermaid() -> list[str]:
    """Build Mermaid flowchart lines from the story graph."""
    from engine.dashboard import _sanitize_mermaid

    graph = load_graph()
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])

    mm: list[str] = ["graph TD"]

    # Define nodes with labels
    for nid, node in nodes.items():
        turn = node.get("turn", "?")
        text = node.get("text", "")[:40]
        label = _sanitize_mermaid(f"T{turn}: {text}")
        mm.append(f'  n{nid}["{label}"]')

    # Define edges
    for edge in edges:
        frm = edge["from"]
        to = edge["to"]
        choice = _sanitize_mermaid(edge.get("choice", ""))
        mm.append(f'  n{frm} -->|{choice}| n{to}')

    return mm


def _strip_frontmatter_blocks(text: str) -> str:
    """Remove YAML frontmatter blocks (between --- markers) from Markdown."""
    lines = text.split("\n")
    result: list[str] = []
    in_frontmatter = False

    for line in lines:
        if line.strip() == "---":
            in_frontmatter = not in_frontmatter
            continue
        if not in_frontmatter:
            result.append(line)

    return "\n".join(result)


def export_graph_html(output_path: Path | None = None) -> Path:
    """
    Export a standalone HTML file that renders the story graph
    using Mermaid.js (loaded from CDN).  No Obsidian needed —
    just open the file in any browser.

    Returns the output path.
    """
    if output_path is None:
        output_path = config.OUTPUT_DIR / "story_graph.html"

    state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    graph = load_graph()
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])

    mermaid_lines = _generate_mermaid()
    mermaid_src = "\n".join(mermaid_lines)

    node_count = len(nodes)
    edge_count = len(edges)
    current_turn = state.get("turn", 0)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>星痕纪元 — 剧情分支图</title>
<script src="./mermaid.min.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    background: #0d1117;
    color: #c9d1d9;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    min-height: 100vh;
  }}
  .header {{
    padding: 24px 32px 16px;
    border-bottom: 1px solid #21262d;
  }}
  .header h1 {{ font-size: 24px; color: #58a6ff; margin-bottom: 4px; }}
  .header .meta {{ color: #8b949e; font-size: 14px; }}
  .header .meta span {{ margin-right: 20px; }}
  .graph-container {{
    padding: 32px;
    display: flex; justify-content: center;
    overflow: auto;
  }}
  .graph-container .mermaid {{
    background: #0d1117;
    padding: 24px;
    border-radius: 8px;
    border: 1px solid #21262d;
  }}
  .details {{
    padding: 0 32px 32px;
    max-width: 900px;
    margin: 0 auto;
  }}
  .details h2 {{ color: #58a6ff; font-size: 18px; margin: 20px 0 10px; border-bottom: 1px solid #21262d; padding-bottom: 6px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th {{ text-align: left; padding: 8px 12px; background: #161b22; color: #8b949e; font-weight: 600; }}
  td {{ padding: 8px 12px; border-top: 1px solid #21262d; }}
  tr:hover td {{ background: #161b22; }}
  .footer {{
    text-align: center; padding: 20px; color: #484f58; font-size: 12px;
    border-top: 1px solid #21262d;
  }}
  a {{ color: #58a6ff; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<div class="header">
  <h1>🌳 星痕纪元 — 剧情分支图</h1>
  <div class="meta">
    <span>📊 节点: {node_count}</span>
    <span>🔀 分支: {edge_count}</span>
    <span>🔄 当前轮次: {current_turn}</span>
  </div>
</div>

<div class="graph-container">
  <div class="mermaid">
{mermaid_src}
  </div>
</div>

<div class="details">
  <h2>📋 节点详情</h2>
  <table>
    <tr><th>Node</th><th>Turn</th><th>Scene</th><th>Status</th><th>Preview</th></tr>
"""

    for nid in sorted(nodes.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        node = nodes[nid]
        html += (
            f"    <tr>"
            f"<td>{nid}</td>"
            f"<td>{node.get('turn', '?')}</td>"
            f"<td>{node.get('scene', '?')}</td>"
            f"<td>{node.get('status', '?')}</td>"
            f"<td>{node.get('text', '')[:60]}</td>"
            f"</tr>\n"
        )

    html += """  </table>
</div>

<div class="footer">
  Prompt OS Galgame Runtime v1 · 星痕纪元 · Epoch of Starlight
  <br>Powered by <a href="https://mermaid.js.org" target="_blank">Mermaid.js</a>
</div>

<script>
  mermaid.initialize({ startOnLoad: true, theme: 'dark',
    themeVariables: {
      primaryColor: '#1f6feb',
      primaryTextColor: '#c9d1d9',
      lineColor: '#30363d',
      fontSize: '14px'
    }
  });
</script>
</body>
</html>"""

    # Ensure Mermaid.js is available locally for offline use
    try:
        from engine.dashboard import ensure_local_js
        ensure_local_js()
    except Exception:
        pass

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    return output_path


# ── CLI entry point ────────────────────────────────────────────────

def main() -> None:
    """Run the Obsidian exporter standalone."""
    story_path = export_full_story()
    graph_path = export_graph_view()
    print(f"✅ Full story → {story_path}")
    print(f"✅ Graph view  → {graph_path}")


if __name__ == "__main__":
    main()
