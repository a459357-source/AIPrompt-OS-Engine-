"""
state_store.py — RuntimeState transactional load / commit
==========================================================
Single commit point for session_state.yaml, memory.json, and story_graph.json.
Uses staging files + os.replace for atomic updates within a single process.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path

import yaml

import config
from engine import io_utils

logger = logging.getLogger(__name__)

_COMMIT_LOCK = threading.Lock()
_thread_local = threading.local()


def _staging_path(target: Path) -> Path:
    """Staging file colocated with target (required for os.replace on Windows)."""
    staging_dir = target.parent / ".staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    return staging_dir / target.name


@dataclass
class RuntimeState:
    session: dict
    memory: dict
    graph: dict
    chapter: str = ""
    relationship: dict | None = None


def _in_transaction() -> bool:
    return getattr(_thread_local, "active", False)


def begin_transaction() -> None:
    """Mark the current thread as inside a runtime transaction (skip mid-turn disk writes)."""
    _thread_local.active = True


def end_transaction() -> None:
    _thread_local.active = False


def is_transactional() -> bool:
    """True when engine code should defer persistence to commit_runtime()."""
    return _in_transaction()


def load_runtime(*, clear_cache: bool = False) -> RuntimeState:
    """Load session, memory, graph (and chapter text) into a RuntimeState snapshot."""
    if clear_cache:
        io_utils.clear_cache(session_only=True)
    chapter = ""
    if config.CHAPTER_PATH.exists():
        try:
            chapter = config.CHAPTER_PATH.read_text(encoding="utf-8")
        except OSError:
            chapter = ""
    relationship: dict | None = None
    if config.RELATIONSHIP_GRAPH_PATH.exists():
        try:
            relationship = io_utils.read_json(
                config.RELATIONSHIP_GRAPH_PATH, use_cache=not clear_cache,
            )
        except Exception:
            relationship = None
    if not isinstance(relationship, dict) or "edges" not in relationship:
        relationship = {
            "version": 1, "nodes": {}, "edges": {}, "events": [], "pending_events": [],
        }

    return RuntimeState(
        session=io_utils.read_yaml(config.SESSION_STATE_PATH, use_cache=not clear_cache),
        memory=io_utils.read_json(config.MEMORY_PATH, use_cache=not clear_cache),
        graph=io_utils.read_json(config.STORY_GRAPH_PATH, use_cache=not clear_cache),
        chapter=chapter,
        relationship=relationship,
    )


def _write_staging(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _validate_yaml(text: str) -> None:
    data = yaml.safe_load(text)
    if data is None:
        raise ValueError("YAML parsed to None")
    if not isinstance(data, dict):
        raise ValueError("YAML root must be a dict")


def _validate_json(text: str) -> None:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("JSON root must be a dict")


def commit_runtime(state: RuntimeState, *, chapter: str | None = None) -> None:
    """
    Atomically persist session / memory / graph (and optional chapter) to disk.
    On failure, original files are left untouched and the error is logged.
    """
    chapter_text = chapter if chapter is not None else state.chapter

    session_yaml = yaml.dump(
        state.session,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    memory_json = json.dumps(state.memory, ensure_ascii=False, indent=2)
    graph_json = json.dumps(state.graph, ensure_ascii=False, indent=2)

    _validate_yaml(session_yaml)
    _validate_json(memory_json)
    _validate_json(graph_json)

    targets = [
        config.SESSION_STATE_PATH,
        config.MEMORY_PATH,
        config.STORY_GRAPH_PATH,
    ]
    staged_paths = [_staging_path(t) for t in targets]
    payloads = {
        staged_paths[0]: session_yaml,
        staged_paths[1]: memory_json,
        staged_paths[2]: graph_json,
    }

    if state.relationship is not None:
        relationship_json = json.dumps(state.relationship, ensure_ascii=False, indent=2)
        _validate_json(relationship_json)
        rel_staged = _staging_path(config.RELATIONSHIP_GRAPH_PATH)
        targets.append(config.RELATIONSHIP_GRAPH_PATH)
        staged_paths.append(rel_staged)
        payloads[rel_staged] = relationship_json

    chapter_staging: Path | None = None
    if chapter_text is not None:
        chapter_staging = _staging_path(config.CHAPTER_PATH)
        payloads[chapter_staging] = chapter_text

    with _COMMIT_LOCK:
        try:
            for path, content in payloads.items():
                _write_staging(path, content)

            for target, staged in zip(targets, staged_paths):
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged, target)

            if chapter_staging is not None:
                config.CHAPTER_PATH.parent.mkdir(parents=True, exist_ok=True)
                os.replace(chapter_staging, config.CHAPTER_PATH)

            io_utils.clear_cache(session_only=True)
            logger.debug("RuntimeState committed (turn=%s)", state.session.get("turn", "?"))
        except Exception as exc:
            logger.error("commit_runtime failed — originals preserved: %s", exc, exc_info=True)
            try:
                err_path = config.DATA_DIR / "error.log"
                with open(err_path, "a", encoding="utf-8") as fh:
                    fh.write(f"[state_store] commit_runtime failed: {exc}\n")
            except OSError:
                pass
            raise


def commit_bundle(
    session: dict,
    memory: dict,
    graph: dict,
    *,
    chapter: str = "",
    relationship: dict | None = None,
) -> None:
    """Convenience wrapper for one-shot commits from save/load/reset/new."""
    commit_runtime(RuntimeState(
        session=session,
        memory=memory,
        graph=graph,
        chapter=chapter,
        relationship=relationship,
    ))
