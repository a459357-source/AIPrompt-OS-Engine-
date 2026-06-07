"""
analytics.py — Dashboard Analytics Engine
===========================================
Reads all data files and computes chart-ready JSON for the
dashboard HTML.  Pure computation — no side effects.

Every function returns a dict suitable for JSON serialization
and Chart.js consumption.
"""

import json
import logging
from collections import Counter
from pathlib import Path

import config
from engine import io_utils
from engine.router import load_graph

logger = logging.getLogger(__name__)

# DeepSeek pricing (per 1M tokens, input/output)
PRICING = {
    "deepseek-chat":     (0.14, 0.28),   # $0.14/M input, $0.28/M output
    "deepseek-reasoner": (0.55, 2.19),   # $0.55/M input, $2.19/M output
}

# Dashboard data size limit: keep at most N data points per metric curve.
# Beyond this, older points are downsampled to prevent HTML bloat (>1MB).
MAX_HISTORY_POINTS = 50


def compute_all() -> dict:
    """Compute all analytics and return a single serializable dict."""
    return {
        "metrics_curves": metrics_curves(),  # dynamic: detects all character metrics
        "trust_curve": trust_curve(),        # backward compat alias
        "faction_curves": faction_curves(),  # faction reputation curves
        "faction_power": faction_power_stats(),  # faction power scores
        "faction_attitude_curves": faction_attitude_curves(),  # inter-faction attitude curves
        "artifacts": artifact_stats(),  # key artifacts
        "status_timeline": status_timeline(),
        "word_counts": word_counts(),
        "choice_stats": choice_stats(),
        "api_usage": api_usage_summary(),
        "character_frequency": character_frequency(),
        "branch_stats": branch_stats(),
        "scene_summary": scene_summary(),
        "summary": summary_stats(),
    }


# ── Individual analytics ───────────────────────────────────────────

def trust_curve() -> dict:
    """Backward-compat alias for metrics_curves()["trust"]."""
    return metrics_curves().get("trust", _empty_curve())


def metrics_curves() -> dict[str, dict]:
    """
    Detect ALL numeric character metrics and return a curve for each.
    Returns {metric_name: {labels: [...], datasets: [...]}}
    e.g. {"trust": {...}, "好感度": {...}, "fear": {...}}
    """
    memory = io_utils.read_json(config.MEMORY_PATH)
    chars = memory.get("characters", {})

    # Discover all metrics from metric_history + top-level numeric fields
    all_metrics: dict[str, dict] = {}  # metric_name → {char_name → [[turn, val], ...]}

    for name, data in chars.items():
        if not isinstance(data, dict):
            continue
        # 1. Check new-style metric_history
        mh = data.get("metric_history", {})
        for metric, history in mh.items():
            if isinstance(history, list) and history:
                all_metrics.setdefault(metric, {})[name] = history

        # 2. Also check backward-compat trust_history
        th = data.get("trust_history", [])
        if th and "trust" not in all_metrics.get("trust", {}).get(name, []):
            all_metrics.setdefault("trust", {})[name] = th

        # 3. Check top-level numeric fields as fallback
        for key, val in data.items():
            if isinstance(val, (int, float)) and key not in ("trust",):
                # Only if no history exists yet, create a baseline
                if key not in all_metrics:
                    all_metrics.setdefault(key, {})[name] = []

    # Build chart data for each metric
    result = {}
    # Human-readable labels for common metrics
    METRIC_LABELS = {
        "trust": "信任度", "好感度": "好感度", "affection": "好感度",
        "fear": "恐惧值", "恐惧": "恐惧值",
        "bond": "羁绊值", "羁绊": "羁绊值",
        "reputation": "声望", "声望": "声望",
        "sanity": "理智值", "理智": "理智值",
        "respect": "敬意", "hostility": "敌意",
    }

    for metric, char_data in all_metrics.items():
        all_turns: set[int] = set()
        datasets = []
        for name, history in char_data.items():
            if history:
                history = _downsample_history(history)
                turns = [h[0] for h in history]
                vals = [int(h[1] * 100) for h in history]
                all_turns.update(turns)
                datasets.append({"name": name, "data": vals})
            else:
                # No history — use current value from data
                current = chars.get(name, {}).get(metric, 0.5)
                datasets.append({"name": name, "data": [int(current * 100)]})
                all_turns.add(0)

        labels = sorted(all_turns) if all_turns else [0]
        label = METRIC_LABELS.get(metric, metric)
        result[metric] = {"labels": labels, "datasets": datasets, "label": label}

    return result


def faction_curves() -> dict:
    """
    Faction reputation curves from memory.json factions.
    Returns {faction_name: {labels, datasets, label, role}}
    """
    memory = io_utils.read_json(config.MEMORY_PATH)
    factions = memory.get("factions", {})

    result = {}
    for name, data in factions.items():
        mh = data.get("metric_history", {}).get("reputation", [])
        if mh:
            mh = _downsample_history(mh)
            turns = [h[0] for h in mh]
            vals = [int(h[1] * 100) for h in mh]
        else:
            # No history — use current value
            turns = [0]
            vals = [int(data.get("reputation", 0.5) * 100)]

        result[name] = {
            "labels": turns,
            "datasets": [{"name": name, "data": vals}],
            "label": f"{name} 声望",
            "role": data.get("role", ""),
        }

    return result


def faction_power_stats() -> dict:
    """
    Faction power radar data: military, economic, political, technology.
    Returns {labels: [...], datasets: [{name, data:[m,e,p,t]}, ...]}
    """
    memory = io_utils.read_json(config.MEMORY_PATH)
    factions = memory.get("factions", {})

    datasets = []
    for name, data in factions.items():
        power = data.get("power", {})
        datasets.append({
            "name": name,
            "data": [
                power.get("military", 0),
                power.get("economic", 0),
                power.get("political", 0),
                power.get("technology", 0),
            ],
        })

    return {
        "labels": ["军事", "经济", "政治", "科技"],
        "datasets": datasets,
    }


def artifact_stats() -> list[dict]:
    """Key artifact summary for dashboard display."""
    memory = io_utils.read_json(config.MEMORY_PATH)
    from engine.memory import get_artifact_stats_for_ui
    return get_artifact_stats_for_ui(memory)


def faction_attitude_curves() -> dict:
    """
    Inter-faction attitude curves from memory.json faction_attitudes.
    Returns {f"{a}→{b}": {labels, datasets, label}} for each non-trivial pair.
    """
    memory = io_utils.read_json(config.MEMORY_PATH)
    attitudes = memory.get("faction_attitudes", {})

    result = {}
    for a, targets in attitudes.items():
        for b, data in targets.items():
            att = data.get("attitude", 0.5)
            mh = data.get("metric_history", {}).get("attitude", [])
            if mh:
                mh = _downsample_history(mh)
                turns = [h[0] for h in mh]
                vals = [int(h[1] * 100) for h in mh]
            else:
                turns = [0]
                vals = [int(att * 100)]

            key = f"{a}→{b}"
            result[key] = {
                "labels": turns,
                "datasets": [{"name": key, "data": vals}],
                "label": f"{a} 对 {b} 的态度",
            }

    return result


def _downsample_history(history: list, max_points: int = MAX_HISTORY_POINTS) -> list:
    """Keep at most *max_points* data points, preserving recent data.

    When the list exceeds max_points, we keep all points from the second
    half and downsample the first half uniformly.  This protects the
    dashboard HTML from ballooning past 1 MB after 200+ turns.
    """
    if len(history) <= max_points:
        return history
    # Keep all recent points (second half), downsample older half
    split = len(history) // 2
    older = history[:split]
    recent = history[split:]
    # Uniform downsample of older half
    keep_older = max_points - len(recent)
    if keep_older <= 0:
        return recent[-max_points:]
    step = max(1, len(older) // keep_older)
    sampled = older[::step][-keep_older:]
    return sampled + recent


def _empty_curve() -> dict:
    return {"labels": [0], "datasets": [], "label": ""}


def status_timeline() -> list[dict]:
    """
    Per-turn status + scene.  Returns list of {turn, status, scene}.
    """
    graph = load_graph()
    nodes = graph.get("nodes", {})

    timeline = []
    for nid in sorted(nodes.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        node = nodes[nid]
        timeline.append({
            "turn": node.get("turn", 0),
            "status": node.get("status", "?"),
            "scene": node.get("scene", "?"),
        })

    return timeline


def word_counts() -> list[dict]:
    """
    Word & character count per turn.
    Returns [{turn, words, chars}]
    """
    graph = load_graph()
    nodes = graph.get("nodes", {})

    counts = []
    for nid in sorted(nodes.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        node = nodes[nid]
        text = node.get("text", "")
        counts.append({
            "turn": node.get("turn", 0),
            "words": len(text.split()) if text else 0,
            "chars": len(text),
        })

    return counts


def choice_stats() -> dict:
    """
    Choice distribution.  Returns {labels: [A,B,C,D], counts: [n, ...]}.
    """
    graph = load_graph()
    edges = graph.get("edges", [])

    counter: Counter = Counter()
    for edge in edges:
        choice = edge.get("choice", "?")
        if choice and choice != "auto" and len(choice) == 1:
            counter[choice] += 1

    labels = ["A", "B", "C", "D"]
    counts = [counter.get(c, 0) for c in labels]

    return {"labels": labels, "counts": counts}


def api_usage_summary() -> dict:
    """
    Aggregate API usage from api_usage.jsonl.
    Returns {
      per_turn: [{turn, prompt_tokens, completion_tokens, total_tokens, chars}],
      totals: {calls, prompt_tokens, completion_tokens, total_tokens, cost_usd}
    }
    """
    path = Path(config.API_USAGE_PATH)
    per_turn = []
    totals = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
              "total_tokens": 0, "cost_usd": 0.0}

    if not path.exists():
        return {"per_turn": per_turn, "totals": totals}

    model = getattr(config, "DEEPSEEK_MODEL", "deepseek-chat")
    price_in, price_out = PRICING.get(model, (0.14, 0.28))

    try:
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                if not line.strip():
                    continue
                entry = json.loads(line)
                pt = entry.get("prompt_tokens", 0)
                ct = entry.get("completion_tokens", 0)
                tt = entry.get("total_tokens", 0)

                per_turn.append({
                    "turn": i,
                    "prompt_tokens": pt,
                    "completion_tokens": ct,
                    "total_tokens": tt,
                    "chars": entry.get("story_chars", 0),
                })

                totals["calls"] += 1
                totals["prompt_tokens"] += pt
                totals["completion_tokens"] += ct
                totals["total_tokens"] += tt

        # Calculate cost
        totals["cost_usd"] = round(
            (totals["prompt_tokens"] / 1_000_000) * price_in +
            (totals["completion_tokens"] / 1_000_000) * price_out,
            4,
        )
    except Exception:
        pass

    return {"per_turn": per_turn, "totals": totals}


def character_frequency() -> dict:
    """
    How often each character appears in story nodes.
    Returns {labels: [names], counts: [appearance_count]}.
    """
    memory = io_utils.read_json(config.MEMORY_PATH)
    chars = memory.get("characters", {})
    graph = load_graph()
    nodes = graph.get("nodes", {})

    labels = list(chars.keys())
    counts = []
    for name in labels:
        count = sum(1 for n in nodes.values() if name in n.get("text", ""))
        counts.append(count)

    return {"labels": labels, "counts": counts}


def branch_stats() -> dict:
    """
    Story tree statistics.
    Returns {total_nodes, leaf_count, max_depth, avg_branch_factor}.
    """
    graph = load_graph()
    nodes = graph.get("nodes", {})

    total = len(nodes)
    if total == 0:
        return {"total_nodes": 0, "leaf_count": 0, "max_depth": 0, "avg_branches": 0}

    # Leaves: nodes with no outgoing filled choices
    leaves = 0
    for nid, node in nodes.items():
        choices = node.get("choices", {})
        if not choices or all(v is None for v in choices.values()):
            leaves += 1

    # Max depth: longest path to root
    def depth(nid, visited=None):
        if visited is None:
            visited = set()
        if nid in visited or nid not in nodes:
            return 0
        visited.add(nid)
        parent = nodes[nid].get("parent")
        if parent is None or parent == nid:
            return 1
        return 1 + depth(parent, visited)

    max_d = max(depth(nid) for nid in nodes) if nodes else 0

    # Average branch factor (choices per node)
    total_branches = sum(
        len([v for v in n.get("choices", {}).values() if v is not None])
        for n in nodes.values()
    )
    avg_b = round(total_branches / total, 1) if total > 0 else 0

    return {
        "total_nodes": total,
        "leaf_count": leaves,
        "max_depth": max_d,
        "avg_branches": avg_b,
    }


def scene_summary() -> list[dict]:
    """
    Scene frequency. Returns [{scene, count}].
    """
    graph = load_graph()
    nodes = graph.get("nodes", {})

    counter: Counter = Counter()
    for n in nodes.values():
        scene = n.get("scene", "?")
        if scene != "?":
            counter[scene] += 1

    return [{"scene": s, "count": c} for s, c in counter.most_common(10)]


def summary_stats() -> dict:
    """Top-level summary numbers for the dashboard header."""
    state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    memory = io_utils.read_json(config.MEMORY_PATH)
    graph = load_graph()

    # Total words across all story nodes
    total_words = sum(
        len(n.get("text", "").split())
        for n in graph.get("nodes", {}).values()
    )
    total_chars = sum(
        len(n.get("text", ""))
        for n in graph.get("nodes", {}).values()
    )

    return {
        "turns": state.get("turn", 0),
        "status": state.get("status", "?"),
        "characters": len(memory.get("characters", {})),
        "total_words": total_words,
        "total_chars": total_chars,
        "nodes": len(graph.get("nodes", {})),
        "edges": len(graph.get("edges", [])),
    }
