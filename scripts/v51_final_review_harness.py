#!/usr/bin/env python3
"""
v51_final_review_harness.py — V5.1 Final Review 自动化采集（无 API）

在 prompt-os-engine/ 下运行:
  python scripts/v51_final_review_harness.py

输出: output/v51_final_review/metrics.json
"""
from __future__ import annotations

import json
import random
import statistics
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from engine.builder import _relationship_context
from engine.relationship_recall import build_dynamics_prompt_context, build_prompt_context
from engine.character_brain import resolve_brain_character_names
from engine.context_compress import estimate_text_tokens
from engine.relationship_core import init_graph_from_world, read_api_for_brain
from engine.relationship_dynamics import empty_dynamics_store, get_dynamics
from engine.relationship_memory import empty_store
from engine.relationship_update import apply_turn_relationship_updates

OUT_DIR = ROOT / "output" / "v51_final_review"
OUT_DIR.mkdir(parents=True, exist_ok=True)

NPCS = ["长公主", "宰相", "皇后", "商会会长", "刺客", "导师", "李将军"]


def _world_pack(seed: int) -> dict:
    rng = random.Random(seed)
    rels = {}
    for name in NPCS:
        rels[name] = {
            "trust": round(rng.uniform(0.25, 0.75), 2),
            "affection": round(rng.uniform(0.2, 0.8), 2),
            "hostility": round(rng.uniform(0, 0.4), 2),
            "respect": round(rng.uniform(0.3, 0.7), 2),
        }
    chars = [{"name": "主角", "is_main": True}]
    for n in NPCS:
        chars.append({"name": n, "is_main": False})
    return {
        "world": {"characters": chars},
        "custom": {"characterRelations": rels},
    }


def _memory() -> dict:
    return {
        "characters": {
            n: {"trust": 0.5, "tier": "核心", "last_appearance_turn": 0}
            for n in NPCS
        },
    }


def _session(turn: int) -> dict:
    return {
        "turn": turn,
        "status": "BUILD",
        "scene": "测试场景",
        "characters": {},
        "history": [],
        "objectives": {
            "main": [{"id": "m1", "title": "获得长公主信任", "status": "active", "progress": 0}],
            "side": [{"id": "s1", "title": "说服商会会长", "status": "active", "progress": 0}],
        },
    }


STORIES = [
    "主角公开维护长公主，朝堂侧目。宰相冷眼旁观。",
    "长公主与主角夜谈，信任加深。皇后在远处观察。",
    "宰相公开羞辱主角，长公主挺身维护。",
    "主角救下刺客，商会会长表示赞赏。",
    "李将军与宰相争执，主角居中调解。",
    "导师传授秘术，长公主在场。",
]

OPTIONS = [
    "支持长公主|长公主好感+8信任+5",
    "安抚宰相|宰相信任+6",
    "与商会会长合作|商会会长信任+10",
    "拒绝刺客请求|刺客敌意+8",
    "向导师请教|导师好感+5",
    "公开指责宰相|宰相敌意+10长公主好感+3",
]


def simulate_turns(turns: int, seed: int = 0) -> dict:
    rng = random.Random(seed)
    world = _world_pack(seed)
    memory = _memory()
    state = _session(0)
    graph = init_graph_from_world(world, memory, state, persist=False)
    mem_store = empty_store()
    dyn_store = empty_dynamics_store()

    decay_triggers = 0
    influence_deltas = 0
    bond_hist: list[int] = []
    conflict_hist: list[int] = []
    momentum_hist: list[float] = []
    triangle_counts: list[int] = []

    for t in range(1, turns + 1):
        state["turn"] = t
        npc = rng.choice(NPCS)
        story = rng.choice(STORIES)
        if npc not in story:
            story = f"{story} {npc}也在场。"
        opt = rng.choice(OPTIONS)
        if npc not in opt:
            opt = f"{opt.split('|')[0]}|{npc}好感+5"
        choice = rng.choice(["A", "B", "C"])
        prev = [opt, OPTIONS[(t + 1) % len(OPTIONS)], OPTIONS[(t + 2) % len(OPTIONS)]]

        trust_before = deepcopy(graph)
        graph, mem_store, dyn_store = apply_turn_relationship_updates(
            {"story": story},
            state,
            choice,
            memory,
            world,
            prev_options=prev,
            relationship_graph=graph,
            relationship_memory=mem_store,
            relationship_dynamics=dyn_store,
            persist=False,
        )

        for n in NPCS:
            dyn = get_dynamics(dyn_store, "主角", n)
            if dyn.last_interaction_turn < t and t - dyn.last_interaction_turn > config.RELATIONSHIP_DECAY_INACTIVE_TURNS:
                decay_triggers += 1
            bond_hist.append(dyn.bond_level)
            conflict_hist.append(dyn.conflict_level)
            momentum_hist.append(dyn.momentum)

        triangle_counts.append(len(dyn_store.get("triangles") or []))

        for key in graph.get("edges", {}):
            if key not in trust_before.get("edges", {}):
                influence_deltas += 1
            elif graph["edges"][key] != trust_before["edges"].get(key):
                pass

    def _json_size(obj: dict) -> int:
        return len(json.dumps(obj, ensure_ascii=False))

    return {
        "seed": seed,
        "turns": turns,
        "graph_edges": len(graph.get("edges") or {}),
        "memory_events": sum(len(v) for v in (mem_store.get("edges") or {}).values()),
        "dynamics_edges": len(dyn_store.get("edges") or {}),
        "graph_bytes": _json_size(graph),
        "memory_bytes": _json_size(mem_store),
        "dynamics_bytes": _json_size(dyn_store),
        "bond_dist": dict(Counter(bond_hist[-len(NPCS):])),
        "conflict_dist": dict(Counter(conflict_hist[-len(NPCS):])),
        "momentum_avg": round(statistics.mean(momentum_hist[-len(NPCS):]), 2) if momentum_hist else 0,
        "momentum_max": max(momentum_hist) if momentum_hist else 0,
        "triangles_final": triangle_counts[-1] if triangle_counts else 0,
        "triangles_max": max(triangle_counts) if triangle_counts else 0,
        "decay_checks": decay_triggers,
    }


def measure_prompt_budget(turns: int, seed: int = 42) -> dict:
    world = _world_pack(seed)
    memory = _memory()
    state = _session(0)
    graph = init_graph_from_world(world, memory, state, persist=False)
    mem_store = empty_store()
    dyn_store = empty_dynamics_store()

    for t in range(1, turns + 1):
        state["turn"] = t
        graph, mem_store, dyn_store = apply_turn_relationship_updates(
            {"story": random.choice(STORIES)},
            state,
            "A",
            memory,
            world,
            prev_options=[OPTIONS[t % len(OPTIONS)]],
            relationship_graph=graph,
            relationship_memory=mem_store,
            relationship_dynamics=dyn_store,
            persist=False,
        )

    brain_names = resolve_brain_character_names(state, memory, world)
    rel_system = _relationship_context(world)
    rel_mem = build_prompt_context(mem_store, graph, state, world, names=brain_names)
    rel_dyn = build_dynamics_prompt_context(dyn_store, graph, state, world, names=brain_names)
    rel_brain = read_api_for_brain(
        brain_names, world, state, memory_store=mem_store, dynamics_store=dyn_store,
    )

    parts = {
        "RELATIONSHIP_SYSTEM": rel_system,
        "RELATIONSHIP_MEMORY_CONTEXT": rel_mem,
        "RELATIONSHIP_DYNAMICS_CONTEXT": rel_dyn,
        "CHARACTER_BRAIN_relationship_block": rel_brain,
    }
    tokens = {k: estimate_text_tokens(v) for k, v in parts.items()}
    chars = {k: len(v) for k, v in parts.items()}
    total = sum(tokens.values())
    return {
        "turns_simulated": turns,
        "chars": chars,
        "tokens_estimated": tokens,
        "total_relationship_tokens": total,
        "within_1500": total <= 1500,
    }


def measure_prompt_worst_case() -> dict:
    """Fill recall buffers to configured caps and measure token budget."""
    from engine.relationship_memory import RelationshipMemoryEvent, append_memory_event

    world = _world_pack(99)
    memory = _memory()
    state = _session(100)
    graph = init_graph_from_world(world, memory, state, persist=False)
    mem_store = empty_store()
    dyn_store = empty_dynamics_store()

    for i, npc in enumerate(NPCS[: config.RELATIONSHIP_MEMORY_MAX_CHARACTERS]):
        for j in range(config.RELATIONSHIP_MEMORY_MAX_EVENTS_PER_EDGE):
            append_memory_event(mem_store, RelationshipMemoryEvent(
                turn=90 + j,
                actor="主角",
                target=npc,
                type="support",
                summary=f"T{90+j} 与{npc}的重要事件记录片段{j}" * 2,
                trust_delta=6,
            ))
        from engine.relationship_dynamics import RelationshipDynamicsState, set_dynamics
        set_dynamics(dyn_store, "主角", npc, RelationshipDynamicsState(
            last_interaction_turn=100,
            momentum=25,
            bond_level=4,
            conflict_level=1,
        ))

    brain_names = set(NPCS[: config.RELATIONSHIP_MEMORY_MAX_CHARACTERS])
    rel_system = _relationship_context(world)
    rel_mem = build_prompt_context(mem_store, graph, state, world, names=brain_names)
    rel_dyn = build_dynamics_prompt_context(dyn_store, graph, state, world, names=brain_names)
    rel_brain = read_api_for_brain(
        brain_names, world, state, memory_store=mem_store, dynamics_store=dyn_store,
    )
    parts = {
        "RELATIONSHIP_SYSTEM": rel_system,
        "RELATIONSHIP_MEMORY_CONTEXT": rel_mem,
        "RELATIONSHIP_DYNAMICS_CONTEXT": rel_dyn,
        "CHARACTER_BRAIN_relationship_block": rel_brain,
    }
    tokens = {k: estimate_text_tokens(v) for k, v in parts.items()}
    total = sum(tokens.values())
    return {
        "label": "worst_case_caps",
        "chars": {k: len(v) for k, v in parts.items()},
        "tokens_estimated": tokens,
        "total_relationship_tokens": total,
        "within_1500": total <= 1500,
    }


def main() -> None:
    long_runs = [simulate_turns(n, seed=0) for n in (50, 100, 200)]
    quality_samples = [simulate_turns(100, seed=s) for s in range(10)]

    prompt_samples = [measure_prompt_budget(t, seed=42) for t in (10, 50, 100, 200)]
    prompt_samples.append(measure_prompt_worst_case())
    totals = [p["total_relationship_tokens"] for p in prompt_samples]

    metrics = {
        "long_runs": long_runs,
        "quality_samples": quality_samples,
        "prompt_budget": {
            "samples": prompt_samples,
            "avg_total_tokens": round(statistics.mean(totals), 1),
            "p95_total_tokens": sorted(totals)[int(len(totals) * 0.95)] if totals else 0,
            "max_total_tokens": max(totals) if totals else 0,
            "target_tokens": 1500,
            "pass": max(totals) <= 1500 if totals else False,
        },
        "quality_summary": {
            "bond_levels_all": dict(Counter(
                k for s in quality_samples for k, v in s["bond_dist"].items() for _ in range(v)
            )),
            "conflict_levels_all": dict(Counter(
                k for s in quality_samples for k, v in s["conflict_dist"].items() for _ in range(v)
            )),
            "all_max_bond": max(
                max((int(k) for k in s["bond_dist"]), default=0) for s in quality_samples
            ),
            "all_min_bond": min(
                min((int(k) for k in s["bond_dist"]), default=0) for s in quality_samples
            ),
            "seeds_with_triangles": sum(1 for s in quality_samples if s["triangles_final"] > 0),
        },
    }

    out_path = OUT_DIR / "metrics.json"
    out_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    print(json.dumps(metrics["prompt_budget"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
