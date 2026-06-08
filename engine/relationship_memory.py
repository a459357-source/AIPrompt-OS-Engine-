"""
relationship_memory.py — V5.1 relationship event log (Phase A minimal).
Full persistence/recall expansion deferred to Phase B.
"""

from __future__ import annotations

from engine.relationship_core import load_graph, save_graph


def append_event(
    title: str,
    *,
    source: str,
    target: str,
    kind: str,
    turn: int,
    persist: bool = True,
) -> None:
    from engine.relationship_core import enqueue_relationship_event

    graph = load_graph()
    enqueue_relationship_event(
        graph,
        title=title,
        source=source,
        target=target,
        kind=kind,
        turn=turn,
    )
    save_graph(graph, persist=persist)


def recent_events(limit: int = 10) -> list[dict]:
    graph = load_graph()
    events = graph.get("events") or []
    if not isinstance(events, list):
        return []
    return [e for e in events[-limit:] if isinstance(e, dict)]


def format_events_for_prompt(limit: int = 5) -> str:
    events = recent_events(limit)
    if not events:
        return ""
    lines = ["【关系重要事件 — 引擎记录】"]
    for e in events:
        lines.append(
            f"- T{e.get('turn', '?')} {e.get('title', '')} "
            f"({e.get('kind', '')})"
        )
    return "\n".join(lines)
