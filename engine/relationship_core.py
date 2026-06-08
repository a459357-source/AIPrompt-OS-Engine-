"""
relationship_core.py — V5.1 Relationship Dynamics (Phase A Core)
================================================================
Directed relationship graph (Shared System). Replaces nested per-character
metrics as the source of truth; memory.json player→NPC metrics are mirrored
for backward compatibility only.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

import config
from engine import io_utils

logger = logging.getLogger(__name__)

METRIC_KEYS = ("trust", "affection", "respect", "dependence", "hostility", "attraction")

RELATION_TYPES = frozenset({
    "neutral",
    "friend",
    "ally",
    "mentor",
    "student",
    "family",
    "lover",
    "enemy",
    "rival",
    "fear",
    "obsession",
    "dependency",
    "political",
})

RELATIONSHIP_EVENT_KINDS = frozenset({
    "告白", "背叛", "结盟", "婚约", "决裂", "和解", "求助", "羞辱", "拯救",
})


@dataclass
class RelationshipEdge:
    source: str
    target: str
    trust: float = 50.0
    affection: float = 50.0
    respect: float = 50.0
    dependence: float = 0.0
    hostility: float = 0.0
    attraction: float = 0.0
    relation_type: str = "neutral"
    last_update_turn: int = 0
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["flags"] = list(self.flags)
        return d

    @classmethod
    def from_dict(cls, raw: dict) -> RelationshipEdge:
        rt = str(raw.get("relation_type", "neutral") or "neutral").strip().lower()
        if rt not in RELATION_TYPES:
            rt = "neutral"
        flags = raw.get("flags") or []
        if not isinstance(flags, list):
            flags = []
        return cls(
            source=str(raw.get("source", "")).strip(),
            target=str(raw.get("target", "")).strip(),
            trust=_clamp100(raw.get("trust", 50)),
            affection=_clamp100(raw.get("affection", 50)),
            respect=_clamp100(raw.get("respect", 50)),
            dependence=_clamp100(raw.get("dependence", 0)),
            hostility=_clamp100(raw.get("hostility", 0)),
            attraction=_clamp100(raw.get("attraction", 0)),
            relation_type=rt,
            last_update_turn=int(raw.get("last_update_turn", 0) or 0),
            flags=[str(f) for f in flags if str(f).strip()],
        )


def _clamp100(value: Any, default: float = 50.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = default
    return round(max(0.0, min(100.0, v)), 1)


def edge_key(source: str, target: str) -> str:
    return f"{source.strip()}→{target.strip()}"


def load_graph() -> dict:
    """Load relationship_graph.json; return empty scaffold if missing."""
    try:
        data = io_utils.read_json(config.RELATIONSHIP_GRAPH_PATH)
        if isinstance(data, dict) and "edges" in data:
            return data
    except Exception:
        pass
    return {"version": 1, "nodes": {}, "edges": {}, "events": [], "pending_events": []}


def save_graph(graph: dict, *, persist: bool = True) -> None:
    if persist:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        io_utils.write_json(config.RELATIONSHIP_GRAPH_PATH, graph)


def get_edge(graph: dict, source: str, target: str) -> RelationshipEdge | None:
    raw = (graph.get("edges") or {}).get(edge_key(source, target))
    if not isinstance(raw, dict):
        return None
    return RelationshipEdge.from_dict(raw)


def set_edge(graph: dict, edge: RelationshipEdge) -> None:
    if not edge.source or not edge.target:
        return
    nodes = graph.setdefault("nodes", {})
    nodes[edge.source] = {"name": edge.source}
    nodes[edge.target] = {"name": edge.target}
    edge.relation_type = infer_relation_type(edge)
    graph.setdefault("edges", {})[edge_key(edge.source, edge.target)] = edge.to_dict()


def infer_relation_type(edge: RelationshipEdge) -> str:
    """Derive relation_type from six metrics (fixed vocabulary)."""
    t = edge.trust
    a = edge.affection
    r = edge.respect
    d = edge.dependence
    h = edge.hostility
    at = edge.attraction

    if h >= 60 and t < 35:
        return "enemy"
    if h >= 40 and r >= 40:
        return "rival"
    if h >= 50 and t < 40:
        return "fear"
    if a >= 70 and at >= 60:
        return "lover"
    if d >= 70 and at >= 50:
        return "obsession"
    if d >= 65:
        return "dependency"
    if r >= 65 and t >= 45 and a < 55:
        return "mentor"
    if r >= 55 and t >= 40 and a >= 45:
        return "student"
    if t >= 60 and h < 25:
        return "ally"
    if a >= 50 or t >= 55:
        return "friend"
    if r >= 55 and t < 50:
        return "political"
    for flag in edge.flags:
        if "家人" in flag or "family" in flag.lower():
            return "family"
    return "neutral"


def resolve_player_name(world_pack: dict, session: dict | None = None) -> str:
    world = world_pack.get("world", world_pack) if world_pack else {}
    for ch in world.get("characters") or []:
        if isinstance(ch, dict) and ch.get("is_main"):
            name = str(ch.get("name", "")).strip()
            if name:
                return name
    if session:
        for ch in (session.get("characters") or {}).values():
            if isinstance(ch, dict):
                note = str(ch.get("note", ""))
                if "主角" in note or ch.get("level") == "L0":
                    name = str(ch.get("name", "")).strip()
                    if name:
                        return name
        for ch in (session.get("characters") or {}).values():
            if isinstance(ch, dict):
                name = str(ch.get("name", "")).strip()
                if name:
                    return name
    return "主角"


def _metric_from_rel_dict(rel: dict, key: str, default: float = 50.0) -> float:
    raw = rel.get(key)
    if isinstance(raw, (int, float)):
        v = float(raw)
        if 0.0 <= v <= 1.0:
            return _clamp100(v * 100.0, default)
        return _clamp100(v, default)
    return default


def init_graph_from_world(
    world_pack: dict,
    memory: dict | None = None,
    session: dict | None = None,
    *,
    persist: bool = True,
) -> dict:
    """Build or refresh graph nodes/edges from world_pack + memory."""
    graph = load_graph()
    if graph.get("edges") and not graph.get("_force_reinit"):
        return graph

    world = world_pack.get("world", world_pack) if world_pack else {}
    player = resolve_player_name(world_pack, session)
    custom = world_pack.get("custom") or {}
    char_relations = custom.get("characterRelations") or {}

    for ch in world.get("characters") or []:
        if not isinstance(ch, dict):
            continue
        name = str(ch.get("name", "")).strip()
        if not name or name == player:
            continue
        graph.setdefault("nodes", {})[name] = {"name": name, "is_main": False}

        rel = char_relations.get(name) if isinstance(char_relations, dict) else {}
        if not isinstance(rel, dict):
            rel = {}

        edge = RelationshipEdge(
            source=player,
            target=name,
            trust=_metric_from_rel_dict(rel, "trust", 50),
            affection=_metric_from_rel_dict(rel, "affection", 50),
            respect=_metric_from_rel_dict(rel, "respect", 50),
            dependence=_metric_from_rel_dict(rel, "dependence", 0),
            hostility=_metric_from_rel_dict(rel, "hostility", 0),
            attraction=_metric_from_rel_dict(rel, "attraction", 0),
            last_update_turn=0,
        )
        rel_type = str(rel.get("relationshipType", "") or "").strip().lower()
        if rel_type in RELATION_TYPES:
            edge.relation_type = rel_type
        else:
            edge.relation_type = infer_relation_type(edge)
        tags = rel.get("tags") or []
        if isinstance(tags, list):
            edge.flags.extend(f"关系：{t}" for t in tags if str(t).strip())
        set_edge(graph, edge)

        # Optional reverse edge (asymmetric default: slightly lower affection)
        rev = get_edge(graph, name, player)
        if rev is None:
            rev_edge = RelationshipEdge(
                source=name,
                target=player,
                trust=max(30.0, edge.trust - 10),
                affection=max(25.0, edge.affection - 15),
                respect=edge.respect,
                dependence=0.0,
                hostility=edge.hostility,
                attraction=max(20.0, edge.attraction - 10),
                last_update_turn=0,
            )
            rev_edge.relation_type = infer_relation_type(rev_edge)
            set_edge(graph, rev_edge)

    if memory:
        _mirror_graph_to_memory(graph, player, memory, persist=False)

    graph.pop("_force_reinit", None)
    save_graph(graph, persist=persist)
    logger.info("Relationship graph initialized (%d edges)", len(graph.get("edges") or {}))
    return graph


def ensure_graph(
    world_pack: dict | None = None,
    memory: dict | None = None,
    session: dict | None = None,
    *,
    persist: bool = True,
) -> dict:
    if not config.RELATIONSHIP_ENGINE_ENABLED:
        return load_graph()
    graph = load_graph()
    if not graph.get("edges"):
        if world_pack is None:
            world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
        if memory is None:
            from engine.memory import load_memory
            memory = load_memory()
        return init_graph_from_world(world_pack, memory, session, persist=persist)
    return graph


def apply_metric_delta(
    graph: dict,
    source: str,
    target: str,
    metric: str,
    delta: float,
    turn: int,
) -> RelationshipEdge | None:
    """Apply delta on 0–100 scale to an edge (creates if missing)."""
    if metric not in METRIC_KEYS:
        return None
    edge = get_edge(graph, source, target)
    if edge is None:
        edge = RelationshipEdge(source=source, target=target)
    old = getattr(edge, metric)
    setattr(edge, metric, _clamp100(old + delta * 100.0 if abs(delta) <= 1.0 else old + delta))
    edge.last_update_turn = turn
    set_edge(graph, edge)
    return edge


def _mirror_graph_to_memory(
    graph: dict,
    player: str,
    memory: dict,
    *,
    persist: bool = False,
) -> None:
    """Sync player→NPC edges into memory characters (0–1 scale) for legacy readers."""
    from engine.memory import save_memory

    chars = memory.setdefault("characters", {})
    for key, raw in (graph.get("edges") or {}).items():
        if not isinstance(raw, dict):
            continue
        if raw.get("source") != player:
            continue
        target = str(raw.get("target", "")).strip()
        if not target or target not in chars:
            continue
        entry = chars[target]
        for m in METRIC_KEYS:
            if m in raw:
                entry[m] = round(float(raw[m]) / 100.0, 2)
        entry["relationship_type"] = raw.get("relation_type", "neutral")
    if persist:
        save_memory(memory, persist=True)


def build_relationship_context_for_brain(
    names: set[str],
    graph: dict,
    player: str,
    world_pack: dict,
) -> str:
    """Relationship graph excerpt for Character Brain prompt block."""
    if not names or not graph.get("edges"):
        return ""

    lines = ["【关系图谱 — 引擎维护】"]
    count = 0
    for name in sorted(names):
        if name == player:
            continue
        edge = get_edge(graph, player, name)
        rev = get_edge(graph, name, player)
        if not edge and not rev:
            continue
        parts = [f"  {player}→{name}:"]
        if edge:
            parts.append(
                f"    类型={edge.relation_type} "
                f"信任{edge.trust:.0f} 好感{edge.affection:.0f} "
                f"尊重{edge.respect:.0f} 依赖{edge.dependence:.0f} "
                f"敌意{edge.hostility:.0f} 吸引{edge.attraction:.0f}"
            )
            if edge.flags:
                parts.append(f"    标记: {' / '.join(edge.flags[:4])}")
        if rev:
            parts.append(
                f"    {name}→{player}: 类型={rev.relation_type} "
                f"好感{rev.affection:.0f} 信任{rev.trust:.0f}"
            )
        desire = _npc_desire(world_pack, name)
        if desire and edge and "信任" in desire and edge.trust >= 80:
            parts.append(f"    ✓ 欲望「{desire[:40]}」关系条件已达成（trust≥80）")
        lines.extend(parts)
        count += 1

    return "\n".join(lines) if count else ""


def _npc_desire(world_pack: dict, name: str) -> str:
    world = world_pack.get("world", world_pack) if world_pack else {}
    for ch in world.get("characters") or []:
        if isinstance(ch, dict) and str(ch.get("name", "")).strip() == name:
            pers = ch.get("personality") or {}
            return str(pers.get("desire", ch.get("goal", "")) or "").strip()
    return ""


def relationship_progress_for_objective(
    title: str,
    graph: dict,
    player: str,
    world_pack: dict,
) -> int | None:
    """
    If objective title references an NPC, return 0–100 progress from graph metrics.
    """
    title = (title or "").strip()
    if not title:
        return None
    world = world_pack.get("world", world_pack) if world_pack else {}
    for ch in world.get("characters") or []:
        if not isinstance(ch, dict) or ch.get("is_main"):
            continue
        name = str(ch.get("name", "")).strip()
        if not name or name not in title:
            continue
        edge = get_edge(graph, player, name)
        if not edge:
            return None
        if any(k in title for k in ("支持", "信任", "说服", "结盟", "盟友")):
            return int((edge.trust + edge.respect) / 2)
        if any(k in title for k in ("好感", "亲密", "爱", "婚", "告白")):
            return int((edge.affection + edge.attraction) / 2)
        if any(k in title for k in ("修复", "关系", "师徒")):
            return int((edge.trust + edge.affection + edge.respect) / 3)
        return int((edge.trust + edge.affection) / 2)
    return None


def sync_objectives_from_graph(session: dict, graph: dict, world_pack: dict) -> dict:
    """Update side/main objective progress when title matches relationship goals."""
    if not config.OBJECTIVE_SYSTEM_ENABLED or not config.RELATIONSHIP_ENGINE_ENABLED:
        return session
    player = resolve_player_name(world_pack, session)
    objectives = copy.deepcopy(session.get("objectives") or {})
    changed = False
    for scope in ("main", "side"):
        for item in objectives.get(scope) or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("status", "")).lower() != "active":
                continue
            title = str(item.get("title", "")).strip()
            prog = relationship_progress_for_objective(title, graph, player, world_pack)
            if prog is None:
                continue
            old = int(item.get("progress", 0) or 0)
            if prog > old:
                item["progress"] = min(100, prog)
                changed = True
    if changed:
        session["objectives"] = objectives
    return session


def read_api_for_brain(
    names: set[str],
    world_pack: dict,
    session: dict | None = None,
) -> str:
    """Public Brain Read API."""
    graph = ensure_graph(world_pack, session=session)
    player = resolve_player_name(world_pack, session)
    return build_relationship_context_for_brain(names, graph, player, world_pack)


def read_api_for_objective(session: dict, world_pack: dict) -> dict:
    """Return relationship-derived progress hints per active objective id."""
    graph = ensure_graph(world_pack, session=session)
    player = resolve_player_name(world_pack, session)
    out: dict[str, int] = {}
    objectives = session.get("objectives") or {}
    for scope in ("main", "side"):
        for item in objectives.get(scope) or []:
            if not isinstance(item, dict):
                continue
            oid = str(item.get("id", "")).strip()
            title = str(item.get("title", "")).strip()
            prog = relationship_progress_for_objective(title, graph, player, world_pack)
            if prog is not None and oid:
                out[oid] = prog
    return out


def enqueue_relationship_event(
    graph: dict,
    *,
    title: str,
    source: str,
    target: str,
    kind: str,
    turn: int,
) -> None:
    events = graph.setdefault("events", [])
    events.append({
        "turn": turn,
        "title": title[:120],
        "source": source,
        "target": target,
        "kind": kind,
    })
    graph.setdefault("pending_events", []).append({
        "turn": turn,
        "title": title[:80],
        "kind": kind,
    })


def consume_pending_events_for_director(graph: dict) -> list[dict]:
    pending = graph.pop("pending_events", []) or []
    return [e for e in pending if isinstance(e, dict)]


def build_relationship_director_hint(graph: dict) -> str:
    pending = graph.get("pending_events") or []
    if not pending:
        return ""
    titles = [str(e.get("title", "")).strip() for e in pending[:3] if isinstance(e, dict)]
    titles = [t for t in titles if t]
    if not titles:
        return ""
    return (
        "【关系事件待推进】"
        + "、".join(titles)
        + "（Plot Director 可据此生成关系节拍，勿生硬打断场景）"
    )
