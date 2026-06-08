"""
relationship_memory.py — V5.1 Relationship Memory (Phase B)
===========================================================
Long-term directed relationship event history (Shared System).
Graph holds current state; this file holds why/when/how it changed.
"""

from __future__ import annotations

import copy
import logging
import re
from dataclasses import asdict, dataclass, field

import config

logger = logging.getLogger(__name__)

RELATION_EVENT_TYPES = frozenset({
    "first_meeting",
    "support",
    "betrayal",
    "rescue",
    "protect",
    "confession",
    "romance",
    "argument",
    "conflict",
    "gift",
    "cooperation",
    "separation",
    "reunion",
})

_STORY_TYPE_KEYWORDS: list[tuple[str, str]] = [
    ("告白", "confession"),
    ("表白", "confession"),
    ("背叛", "betrayal"),
    ("救", "rescue"),
    ("维护", "support"),
    ("支持", "support"),
    ("保护", "protect"),
    ("争吵", "argument"),
    ("争执", "argument"),
    ("决裂", "conflict"),
    ("合作", "cooperation"),
    ("结盟", "cooperation"),
    ("礼物", "gift"),
    ("赠", "gift"),
    ("分离", "separation"),
    ("重逢", "reunion"),
    ("初见", "first_meeting"),
]


@dataclass
class RelationshipMemoryEvent:
    turn: int
    actor: str
    target: str
    type: str
    summary: str
    trust_delta: float = 0.0
    affection_delta: float = 0.0
    respect_delta: float = 0.0
    hostility_delta: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type
        return d

    @classmethod
    def from_dict(cls, raw: dict) -> RelationshipMemoryEvent:
        et = str(raw.get("type", "support") or "support").strip().lower()
        if et not in RELATION_EVENT_TYPES:
            et = "support"
        return cls(
            turn=int(raw.get("turn", 0) or 0),
            actor=str(raw.get("actor", "")).strip(),
            target=str(raw.get("target", "")).strip(),
            type=et,
            summary=str(raw.get("summary", "")).strip()[:120],
            trust_delta=_f(raw.get("trust_delta", 0)),
            affection_delta=_f(raw.get("affection_delta", 0)),
            respect_delta=_f(raw.get("respect_delta", 0)),
            hostility_delta=_f(raw.get("hostility_delta", 0)),
        )


def _f(value) -> float:
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return 0.0


def memory_edge_key(actor: str, target: str) -> str:
    return f"{actor.strip()}->{target.strip()}"


def empty_store() -> dict:
    return {"version": 1, "edges": {}}


def load_relationship_memory_store() -> dict:
    from engine import io_utils
    try:
        data = io_utils.read_json(config.RELATIONSHIP_MEMORY_PATH)
        if isinstance(data, dict) and "edges" in data:
            return data
    except Exception:
        pass
    return empty_store()


def get_edge_events(store: dict, actor: str, target: str) -> list[dict]:
    key = memory_edge_key(actor, target)
    events = (store.get("edges") or {}).get(key) or []
    return [e for e in events if isinstance(e, dict)]


def append_memory_event(store: dict, event: RelationshipMemoryEvent) -> None:
    if not event.actor or not event.target:
        return
    if event.type not in RELATION_EVENT_TYPES:
        event.type = "support"
    key = memory_edge_key(event.actor, event.target)
    store.setdefault("edges", {}).setdefault(key, []).append(event.to_dict())
    logger.debug(
        "Relationship memory: T%d %s→%s [%s] %s",
        event.turn, event.actor, event.target, event.type, event.summary[:40],
    )


def _metric_deltas(before: dict, after: dict) -> dict[str, float]:
    keys = ("trust", "affection", "respect", "hostility", "dependence", "attraction")
    out: dict[str, float] = {}
    for k in keys:
        b = _f(before.get(k, 0))
        a = _f(after.get(k, 0))
        d = round(a - b, 1)
        if d != 0:
            out[k] = d
    return out


def _story_hint(story: str, actor: str, target: str) -> tuple[str | None, str | None]:
    text = story or ""
    if target not in text and actor not in text:
        return None, None
    for kw, etype in _STORY_TYPE_KEYWORDS:
        if kw in text:
            snippet = text.strip()
            if len(snippet) > 48:
                idx = snippet.find(kw)
                start = max(0, idx - 12)
                snippet = snippet[start:start + 48]
            return etype, snippet
    return None, None


def _infer_type_and_summary(
    deltas: dict[str, float],
    old_type: str,
    new_type: str,
    *,
    story: str = "",
    actor: str = "",
    target: str = "",
) -> tuple[str, str]:
    story_type, story_summary = _story_hint(story, actor, target)
    if story_type and story_summary:
        return story_type, story_summary

    trust_d = deltas.get("trust", 0.0)
    aff_d = deltas.get("affection", 0.0)
    host_d = deltas.get("hostility", 0.0)
    resp_d = deltas.get("respect", 0.0)

    if old_type != new_type:
        type_summaries = {
            "lover": ("romance", "关系升级为恋人"),
            "enemy": ("betrayal", "关系恶化为敌对"),
            "ally": ("cooperation", "关系升级为盟友"),
            "friend": ("support", "关系发展为朋友"),
            "rival": ("conflict", "关系转为竞争对立"),
            "fear": ("conflict", "关系转为畏惧"),
        }
        if new_type in type_summaries:
            return type_summaries[new_type]

    if trust_d <= -config.RELATIONSHIP_MEMORY_DELTA_THRESHOLD:
        return "betrayal", f"双方信任下降{abs(int(trust_d))}"
    if host_d >= config.RELATIONSHIP_MEMORY_DELTA_THRESHOLD:
        return "conflict", f"敌意上升{int(host_d)}"
    if aff_d >= 10:
        return "romance", "双方关系明显升温"
    if aff_d >= config.RELATIONSHIP_MEMORY_DELTA_THRESHOLD:
        return "romance", "好感有所提升"
    if trust_d >= config.RELATIONSHIP_MEMORY_DELTA_THRESHOLD:
        return "support", f"信任提升{int(trust_d)}"
    if resp_d >= config.RELATIONSHIP_MEMORY_DELTA_THRESHOLD:
        return "support", f"尊重提升{int(resp_d)}"
    if host_d <= -config.RELATIONSHIP_MEMORY_DELTA_THRESHOLD:
        return "reunion", "敌意缓和"
    if aff_d <= -config.RELATIONSHIP_MEMORY_DELTA_THRESHOLD:
        return "argument", f"好感下降{abs(int(aff_d))}"

    dominant = max(
        (
            ("trust", trust_d),
            ("affection", aff_d),
            ("hostility", host_d),
            ("respect", resp_d),
        ),
        key=lambda x: abs(x[1]),
    )
    metric, val = dominant
    if abs(val) < config.RELATIONSHIP_MEMORY_DELTA_THRESHOLD:
        return "support", "关系发生小幅变化"
    sign = "+" if val > 0 else ""
    return "support", f"{metric}变化{sign}{int(val)}"


def should_record_memory(
    deltas: dict[str, float],
    old_type: str,
    new_type: str,
) -> bool:
    if old_type != new_type:
        return True
    threshold = config.RELATIONSHIP_MEMORY_DELTA_THRESHOLD
    for k in ("trust", "affection", "respect", "hostility"):
        if abs(deltas.get(k, 0.0)) >= threshold:
            return True
    return False


def record_edge_memory(
    store: dict,
    *,
    turn: int,
    actor: str,
    target: str,
    before: dict,
    after: dict,
    story: str = "",
) -> RelationshipMemoryEvent | None:
    """Record one memory event when deltas or relation_type warrant it."""
    old_type = str(before.get("relation_type", "neutral") or "neutral")
    new_type = str(after.get("relation_type", "neutral") or "neutral")
    deltas = _metric_deltas(before, after)
    if not should_record_memory(deltas, old_type, new_type):
        return None

    etype, summary = _infer_type_and_summary(
        deltas, old_type, new_type,
        story=story, actor=actor, target=target,
    )
    event = RelationshipMemoryEvent(
        turn=turn,
        actor=actor,
        target=target,
        type=etype,
        summary=summary,
        trust_delta=deltas.get("trust", 0.0),
        affection_delta=deltas.get("affection", 0.0),
        respect_delta=deltas.get("respect", 0.0),
        hostility_delta=deltas.get("hostility", 0.0),
    )
    append_memory_event(store, event)
    return event


def record_turn_memories(
    store: dict,
    *,
    turn: int,
    player: str,
    snapshots: dict[str, dict],
    graph: dict,
    story: str = "",
) -> list[RelationshipMemoryEvent]:
    """Compare pre-turn snapshots to current graph; append memory events."""
    recorded: list[RelationshipMemoryEvent] = []
    edges = graph.get("edges") or {}
    for target, before in snapshots.items():
        key = f"{player.strip()}→{target.strip()}"
        after_raw = edges.get(key)
        if not isinstance(after_raw, dict):
            continue
        evt = record_edge_memory(
            store,
            turn=turn,
            actor=player,
            target=target,
            before=before,
            after=after_raw,
            story=story,
        )
        if evt:
            recorded.append(evt)
    return recorded


def snapshot_player_edges(graph: dict, player: str, targets: set[str]) -> dict[str, dict]:
    """Capture player→target edge state before turn updates."""
    from engine.relationship_core import edge_key

    out: dict[str, dict] = {}
    edges = graph.get("edges") or {}
    for name in targets:
        raw = edges.get(edge_key(player, name))
        if isinstance(raw, dict):
            out[name] = copy.deepcopy(raw)
        else:
            out[name] = {
                "source": player,
                "target": name,
                "trust": 50.0,
                "affection": 50.0,
                "respect": 50.0,
                "dependence": 0.0,
                "hostility": 0.0,
                "attraction": 0.0,
                "relation_type": "neutral",
            }
    return out
