"""
io_utils.py — YAML / JSON read & write with in-memory caching
===============================================================
All file I/O goes through these helpers so the rest of the engine
never touches open() directly.

The optional file cache avoids redundant disk reads within a single
turn — build_prompt reads 4 files, step() reads 3 more, _update_memory
reads again.  With the cache, each file hits disk at most once per turn.
"""

import json
import threading
import yaml
from pathlib import Path
from datetime import datetime


# ── Per-thread file cache ──────────────────────────────────────────
# Each thread (web worker) gets its own cache so concurrent requests
# never share stale data.  The cache is invalidated at the end of a turn.

_thread_local = threading.local()


def _get_cache() -> dict:
    """Return the current thread's file cache dict, creating it lazily."""
    cache = getattr(_thread_local, "file_cache", None)
    if cache is None:
        cache = {}
        _thread_local.file_cache = cache
    return cache


def clear_cache() -> None:
    """Discard the current thread's file cache — call at the end of each turn."""
    _thread_local.file_cache = {}


def _cached_read(path: Path, reader) -> dict:
    """Return cached data or read + cache + return."""
    cache = _get_cache()
    key = str(path)
    if key in cache:
        return cache[key]
    data = reader(path)
    cache[key] = data
    return data


# ── YAML ───────────────────────────────────────────────────────────

def read_yaml(path: Path, use_cache: bool = True) -> dict:
    """Read a YAML file, return a dict.  Never returns None."""
    def _read(p: Path) -> dict:
        with open(p, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return data if data is not None else {}
    if use_cache:
        return _cached_read(path, _read)
    return _read(path)


def write_yaml(path: Path, data: dict) -> None:
    """Write a dict to a YAML file (human-readable, UTF-8).

    Also updates the cache so subsequent reads within the same turn
    see the fresh data without hitting disk.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, allow_unicode=True, default_flow_style=False, sort_keys=False)
    # Invalidate cache for this path
    _get_cache().pop(str(path), None)


# ── JSON ───────────────────────────────────────────────────────────

def read_json(path: Path, use_cache: bool = True) -> dict:
    """Read a JSON file, return a dict."""
    def _read(p: Path) -> dict:
        with open(p, "r", encoding="utf-8") as fh:
            return json.load(fh)
    if use_cache:
        return _cached_read(path, _read)
    return _read(path)


def write_json(path: Path, data: dict) -> None:
    """Write a dict to a JSON file (pretty-printed).

    Also updates the cache so subsequent reads see the fresh data.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    _get_cache().pop(str(path), None)


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
