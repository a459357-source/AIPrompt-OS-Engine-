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

        # 4b. Write dashboard HTML to vault
        _write_dashboard_to_vault(vault)

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
    """Append the latest chapter to the full-story file.

    Previously rewrote the entire file every turn (O(n²) I/O after N turns).
    Now only appends the newest chapter, rewriting the header + character
    summary section each time (O(1) per turn for the body).
    """
    chapters_dir = vault / CHAPTERS_DIR
    path = vault / STORY_DIR / "完整叙事.md"

    state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    memory = io_utils.read_json(config.MEMORY_PATH)
    turn = state.get("turn", 0)

    # If we already have the file, just append the latest chapter
    if path.exists() and turn > 1:
        latest_chapter = chapters_dir / _chapter_filename(turn)
        if latest_chapter.exists():
            text = latest_chapter.read_text(encoding="utf-8")
            clean = _strip_frontmatter(text)
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n" + clean + "\n")
        # Update header metadata in-place (first ~15 lines)
        _update_story_header(path, state)
        return

    # First turn — create the full file
    lines: list[str] = []
    lines.append("---")
    lines.append("title: 星痕纪元 — 完整叙事")
    lines.append(f"turns: {turn}")
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
            clean = _strip_frontmatter(text)
            lines.append(clean)
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def _update_story_header(path: Path, state: dict) -> None:
    """Update turns/status/updated in the YAML frontmatter of the full story."""
    try:
        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")
        new_lines: list[str] = []
        for line in lines:
            if line.startswith("turns:"):
                new_lines.append(f"turns: {state.get('turn', 0)}")
            elif line.startswith("status:"):
                new_lines.append(f"status: {state.get('status', '?')}")
            elif line.startswith("updated:"):
                new_lines.append(f"updated: {datetime.now().isoformat()}")
            else:
                new_lines.append(line)
        path.write_text("\n".join(new_lines), encoding="utf-8")
    except Exception:
        pass  # best-effort


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
    from engine.dashboard import _format_mermaid_edge, _sanitize_mermaid

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
        text = _sanitize_mermaid(node.get("text", "")[:40])
        label = f"T{turn}: {text}"
        lines.append(f'  n{nid}["{label}"]')

    for edge in edges:
        lines.append(_format_mermaid_edge(edge["from"], edge["to"], edge.get("choice", "")))

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


def _write_dashboard_to_vault(vault: Path) -> None:
    """Write the unified dashboard HTML to the Obsidian vault."""
    from engine.dashboard import build_html

    html = build_html()
    path = vault / STORY_DIR / "剧情图谱.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


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
    """Remove YAML frontmatter from markdown text.

    Only toggles frontmatter mode on the FIRST two `---` delimiters.
    Subsequent `---` lines in the body (e.g. horizontal rules) are
    left in place, fixing the bug where story-body `---` would
    re-enter frontmatter mode and discard content.
    """
    lines = text.split("\n")
    result: list[str] = []
    fm_count = 0
    in_fm = False
    for line in lines:
        if line.strip() == "---" and fm_count < 2:
            in_fm = not in_fm
            fm_count += 1
            continue
        if not in_fm:
            result.append(line)
    return "\n".join(result)
