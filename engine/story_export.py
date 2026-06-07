"""Export a single turn's story to markdown / text / html."""

from __future__ import annotations

import html
import logging
from datetime import datetime
from pathlib import Path

import config

logger = logging.getLogger(__name__)

EXPORTS_DIR = config.OUTPUT_DIR / "exports"


def _option_lines(options: list, letters: bool = True) -> list[str]:
    lines: list[str] = []
    for idx, opt in enumerate(options, 1):
        prefix = chr(64 + idx) if letters else str(idx)
        lines.append(f"{prefix}. {opt}")
    return lines


def format_turn_content(
    response: dict,
    state: dict,
    choice: str | None,
    fmt: str,
) -> str:
    turn = state.get("turn", 0)
    status = state.get("status", "?")
    scene = state.get("scene", "?")
    story = response.get("story", "")
    options = response.get("options", [])

    if fmt == "text":
        parts = [
            f"第 {turn} 轮 [{status}] {scene}",
            "-" * 40,
            story,
        ]
        if choice:
            parts.append(f"\n玩家选择: {choice}")
        if options:
            parts.append("\n选项:")
            parts.extend(f"  {line}" for line in _option_lines(options))
        return "\n".join(parts) + "\n"

    if fmt == "html":
        opts_html = "".join(
            f"<li><strong>{html.escape(chr(64 + i))}.</strong> {html.escape(opt)}</li>"
            for i, opt in enumerate(options, 1)
        )
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>Turn {turn}</title></head><body>"
            f"<h1>第 {turn} 轮</h1>"
            f"<p><strong>状态:</strong> {html.escape(status)} | "
            f"<strong>场景:</strong> {html.escape(scene)}</p>"
            f"<div>{html.escape(story).replace(chr(10), '<br>')}</div>"
            + (f"<p><strong>玩家选择:</strong> {html.escape(choice)}</p>" if choice else "")
            + (f"<h2>选项</h2><ul>{opts_html}</ul>" if opts_html else "")
            + "</body></html>"
        )

    # markdown (default)
    parts = [
        f"# 第 {turn} 轮",
        "",
        f"**状态:** `{status}` | **场景:** {scene}",
        "",
        "---",
        "",
        story,
        "",
        "---",
        "",
    ]
    if choice:
        parts.append(f"**玩家选择:** `{choice}`")
        parts.append("")
    if options:
        parts.append("## 选项")
        parts.append("")
        for idx, opt in enumerate(options, 1):
            parts.append(f"- **{chr(64 + idx)}.** {opt}")
        parts.append("")
    return "\n".join(parts)


def export_turn(
    response: dict,
    state: dict,
    choice: str | None,
    *,
    fmt: str | None = None,
    suffix: str = "",
) -> Path | None:
    """Write one turn export file under output/exports/."""
    fmt = fmt or config.EXPORT_FORMAT
    if fmt not in ("markdown", "text", "html"):
        fmt = "markdown"

    turn = state.get("turn", 0)
    ext = {"markdown": "md", "text": "txt", "html": "html"}[fmt]
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    name = f"turn_{turn:04d}{suffix}.{ext}"
    path = EXPORTS_DIR / name
    body = format_turn_content(response, state, choice, fmt)
    path.write_text(body, encoding="utf-8")
    logger.info("Exported turn %s → %s", turn, path)
    return path
