"""
io_utils.py — YAML / JSON read & write
=======================================
All file I/O goes through these helpers so the rest of the engine
never touches open() directly.
"""

import json
import yaml
from pathlib import Path
from datetime import datetime


# ── YAML ───────────────────────────────────────────────────────────

def read_yaml(path: Path) -> dict:
    """Read a YAML file, return a dict.  Never returns None."""
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if data is not None else {}


def write_yaml(path: Path, data: dict) -> None:
    """Write a dict to a YAML file (human-readable, UTF-8)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ── JSON ───────────────────────────────────────────────────────────

def read_json(path: Path) -> dict:
    """Read a JSON file, return a dict."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: dict) -> None:
    """Write a dict to a JSON file (pretty-printed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


# ── Markdown ───────────────────────────────────────────────────────

def write_markdown(path: Path, content: str, frontmatter: dict | None = None) -> None:
    """Write a Markdown file, optionally with Obsidian-compatible YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        if frontmatter:
            fh.write("---\n")
            yaml.dump(frontmatter, fh, allow_unicode=True, default_flow_style=False, sort_keys=False)
            fh.write("---\n\n")
        fh.write(content)


def append_markdown(path: Path, content: str, frontmatter: dict | None = None) -> None:
    """Append to a Markdown file (for multi-turn chapter accumulation).

    Only writes YAML frontmatter when the file is empty (first turn).
    Subsequent appends skip frontmatter to avoid violating the Markdown
    spec which allows at most one YAML frontmatter block per file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    is_empty = not path.exists() or path.stat().st_size == 0
    with open(path, "a", encoding="utf-8") as fh:
        if frontmatter and is_empty:
            fh.write("---\n")
            yaml.dump(frontmatter, fh, allow_unicode=True, default_flow_style=False, sort_keys=False)
            fh.write("---\n\n")
        fh.write(content)


# ── Turn log ───────────────────────────────────────────────────────

def append_turn_log(log_path: Path, entry: dict) -> None:
    """Append one entry to a JSON-lines turn log."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry["logged_at"] = datetime.now().isoformat()
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
