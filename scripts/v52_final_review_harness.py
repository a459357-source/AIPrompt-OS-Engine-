#!/usr/bin/env python3
"""
v52_final_review_harness.py — V5.2 Final Review 自动化采集（无 API）

在 prompt-os-engine/ 下运行:
  python scripts/v52_final_review_harness.py

输出: output/v52_final_review/metrics.json
"""
from __future__ import annotations

import json
import random
import shutil
import statistics
import sys
import tempfile
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config
from engine.context_compress import estimate_text_tokens
from engine.director_runtime import advance_director_after_turn, prepare_director_prompt, reset_director_state
from engine.director_state import ACTIVE, COOLDOWN, FAILED, RESOLVED, get_current_event, load_director_state
from engine.event_director import ensure_event_catalog, load_event_history
from engine.relationship_core import RelationshipEdge, init_graph_from_world, set_edge
from engine.relationship_dynamics import RelationshipDynamicsState, empty_dynamics_store, set_dynamics
from engine.relationship_memory import empty_store
from engine.relationship_recall import build_dynamics_prompt_context, build_prompt_context
from engine.builder import _relationship_context
from engine.character_brain import resolve_brain_character_names
from engine.relationship_core import read_api_for_brain
from engine.relationship_update import apply_turn_relationship_updates

OUT_DIR = ROOT / "output" / "v52_final_review"
OUT_DIR.mkdir(parents=True, exist_ok=True)

NPCS = ["长公主", "宰相", "皇后", "商会会长", "刺客", "导师", "李将军"]

RESOLVE_STORIES = [
    "夜色深沉，长公主与主角深夜谈心，彼此敞开心扉，完成了一次真正的对话。",
    "主角向长公主赠送信物，对方收下，关系更进一步，告一段落。",
    "调查取得突破，关键线索浮出水面，真相揭露在即。",
    "朝堂之上政治施压加剧，各方势力角力，局势尘埃落定。",
]

NEUTRAL_STORIES = [
    "主角在城中闲逛，观察市井百态。",
    "天气阴沉，众人各自忙碌。",
    "一场普通的会议，没有特别进展。",
]

OPTIONS = [
    "支持长公主|长公主好感+8信任+5",
    "安抚宰相|宰相信任+6",
    "与商会会长合作|商会会长信任+10",
]


def _patch_data_dir(tmp: Path) -> None:
    config.DATA_DIR = tmp
    config.DIRECTOR_STATE_PATH = tmp / "director_state.json"
    config.EVENT_HISTORY_PATH = tmp / "event_history.json"
    config.EVENT_CATALOG_PATH = tmp / "event_catalog.json"
    if config.EVENT_CATALOG_DEFAULT_PATH.exists():
        shutil.copy2(config.EVENT_CATALOG_DEFAULT_PATH, config.EVENT_CATALOG_PATH)


def _world_pack(seed: int) -> dict:
    rng = random.Random(seed)
    rels = {}
    for name in NPCS:
        rels[name] = {
            "trust": round(rng.uniform(0.35, 0.9), 2),
            "affection": round(rng.uniform(0.3, 0.85), 2),
            "hostility": round(rng.uniform(0, 0.35), 2),
        }
    chars = [{"name": "主角", "is_main": True}]
    for n in NPCS:
        chars.append({"name": n, "is_main": False})
    return {
        "world": {
            "main_goal": "调查灭门案",
            "characters": chars,
        },
        "custom": {"characterRelations": rels},
    }


def _memory(seed: int) -> dict:
    rng = random.Random(seed)
    factions = {
        "北境军": {
            "type": "military",
            "goals": ["夺取边境"],
            "relation_to_player": "hostile" if rng.random() > 0.5 else "neutral",
            "influence": 85,
        },
        "王庭": {
            "type": "government",
            "goals": ["提高税率"],
            "relation_to_player": "neutral",
            "influence": 80,
        },
    }
    return {
        "characters": {n: {"trust": 0.5, "tier": "核心"} for n in NPCS},
        "factions": factions,
        "faction_attitudes": {
            "北境军": {"王庭": {"attitude": 0.15}},
            "王庭": {"北境军": {"attitude": 0.2}},
        },
    }


def _session(turn: int, progress: int = 0) -> dict:
    return {
        "turn": turn,
        "status": "BUILD",
        "scene": "测试场景",
        "characters": {},
        "history": [],
        "objectives": {
            "main": [{"id": "m1", "title": "调查灭门案", "status": "active", "progress": progress}],
            "side": [{"id": "s1", "title": "获得长公主信任", "status": "active", "progress": progress // 2}],
        },
    }


def _plot_state(progress: int) -> dict:
    return {
        "main_plot": {"name": "调查灭门案", "progress": progress, "stage": 1 + progress // 35},
        "unresolved_hooks": [{"kind": "mystery_event", "id": f"h{i}"} for i in range(min(5, progress // 15))],
        "last_progress_turn": max(0, progress - 3),
    }


def _json_size(obj: dict) -> int:
    return len(json.dumps(obj, ensure_ascii=False))


def simulate_director_runtime(turns: int, seed: int = 0) -> dict:
    """Simulate prepare + advance loop without API."""
    tmp = Path(tempfile.mkdtemp(prefix="v52dir_"))
    try:
        _patch_data_dir(tmp)
        reset_director_state()
        rng = random.Random(seed)
        world = _world_pack(seed)
        memory = _memory(seed)
        state = _session(0)
        graph = init_graph_from_world(world, memory, state, persist=False)
        mem_store = empty_store()
        dyn_store = empty_dynamics_store()

        set_edge(graph, RelationshipEdge(source="主角", target="长公主", trust=82, affection=70))
        set_dynamics(dyn_store, "主角", "长公主", RelationshipDynamicsState(momentum=18, bond_level=4))

        stuck_events = 0
        max_active_streak = 0
        current_streak = 0
        last_event_id = ""
        active_turns = 0
        resolved_count = 0
        failed_count = 0
        finalize_turns: list[tuple[int, str]] = []

        for t in range(1, turns + 1):
            progress = min(95, t * 100 // turns)
            state = _session(t, progress)
            plot_state = _plot_state(progress)

            prepare_director_prompt(
                state, world,
                memory=memory,
                graph=graph,
                relationship_memory=mem_store,
                relationship_dynamics=dyn_store,
                plot_state=plot_state,
            )

            current = get_current_event(load_director_state())
            if current and current.state == ACTIVE:
                active_turns += 1
                if current.event_id == last_event_id:
                    current_streak += 1
                else:
                    current_streak = 1
                    last_event_id = current.event_id
                max_active_streak = max(max_active_streak, current_streak)
                if current_streak > config.DIRECTOR_EVENT_MAX_ACTIVE_TURNS + 1:
                    stuck_events += 1

            story_pool = RESOLVE_STORIES if rng.random() < 0.55 else NEUTRAL_STORIES
            story = rng.choice(story_pool)
            before = deepcopy(load_director_state())
            advance_director_after_turn(state, story)

            after = load_director_state()
            lifecycle = after.get("lifecycle") or []
            if len(lifecycle) > len(before.get("lifecycle") or []):
                last = lifecycle[-1]
                if last.get("state") == COOLDOWN:
                    hist = load_event_history().get("records") or []
                    hist_reason = str(hist[-1].get("reason", "")) if hist else ""
                    if hist_reason.startswith("resolved:"):
                        resolved_count += 1
                    else:
                        failed_count += 1
                    finalize_turns.append((t, str(last.get("event_id", ""))))

            graph, mem_store, dyn_store = apply_turn_relationship_updates(
                {"story": story},
                state,
                rng.choice(["A", "B", "C"]),
                memory,
                world,
                prev_options=OPTIONS,
                relationship_graph=graph,
                relationship_memory=mem_store,
                relationship_dynamics=dyn_store,
                persist=False,
            )

        director_state = load_director_state()
        current_end = get_current_event(director_state)
        lifecycle = director_state.get("lifecycle") or []

        return {
            "seed": seed,
            "turns": turns,
            "director_state_bytes": _json_size(director_state),
            "event_history_bytes": _json_size(load_event_history()),
            "lifecycle_count": len(lifecycle),
            "resolved_count": resolved_count,
            "failed_count": failed_count,
            "active_turns": active_turns,
            "active_turn_ratio": round(active_turns / max(turns, 1), 3),
            "stuck_events": stuck_events,
            "max_active_streak": max_active_streak,
            "end_has_active": bool(current_end and current_end.state == ACTIVE),
            "finalize_turns": finalize_turns[-20:],
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def measure_cooldown_effectiveness(turns: int = 200, seed: int = 7) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="v52cd_"))
    try:
        _patch_data_dir(tmp)
        reset_director_state()
        rng = random.Random(seed)
        world = _world_pack(seed)
        memory = _memory(seed)
        graph = init_graph_from_world(world, memory, _session(0), persist=False)
        mem_store = empty_store()
        dyn_store = empty_dynamics_store()
        catalog = ensure_event_catalog()
        violations: list[dict] = []
        last_finalize: dict[str, int] = {}

        for t in range(1, turns + 1):
            state = _session(t, min(90, t // 2))
            prepare_director_prompt(
                state, world, memory=memory, graph=graph,
                relationship_memory=mem_store, relationship_dynamics=dyn_store,
                plot_state=_plot_state(state["objectives"]["main"][0]["progress"]),
            )
            advance_director_after_turn(state, rng.choice(RESOLVE_STORIES + NEUTRAL_STORIES))

            ds = load_director_state()
            for item in ds.get("lifecycle") or []:
                eid = str(item.get("event_id", ""))
                lt = int(item.get("last_turn", 0) or 0)
                if eid and lt == t:
                    prev = last_finalize.get(eid)
                    if prev is not None:
                        cd = int((catalog.get("events", {}).get(eid, {}) or {}).get("cooldown", 0) or 0)
                        gap = t - prev
                        if cd > 0 and gap < cd:
                            violations.append({"event_id": eid, "gap": gap, "cooldown": cd, "turn": t})
                    last_finalize[eid] = t

        romance_spam = Counter(
            eid for eid, _ in [
                (x["event_id"], x["turn"])
                for x in violations
                if x["event_id"] in ("confession", "gift_exchange", "midnight_talk")
            ]
        )
        return {
            "turns": turns,
            "violations": violations,
            "violation_count": len(violations),
            "pass": len(violations) == 0,
            "romance_spam_violations": dict(romance_spam),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def measure_prompt_budget_worst_case() -> dict:
    """V5.1 relationship worst-case + V5.2 ACTIVE director block."""
    from engine.relationship_memory import RelationshipMemoryEvent, append_memory_event

    tmp = Path(tempfile.mkdtemp(prefix="v52pb_"))
    try:
        _patch_data_dir(tmp)
        world = _world_pack(99)
        memory = _memory(99)
        state = _session(100, progress=85)
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
            set_dynamics(dyn_store, "主角", npc, RelationshipDynamicsState(
                last_interaction_turn=100,
                momentum=25,
                bond_level=4,
                conflict_level=1,
            ))

        set_edge(graph, RelationshipEdge(source="主角", target="长公主", trust=90, affection=80))
        plot_state = _plot_state(85)

        brain_names = set(NPCS[: config.RELATIONSHIP_MEMORY_MAX_CHARACTERS])
        rel_parts = {
            "RELATIONSHIP_SYSTEM": _relationship_context(world),
            "RELATIONSHIP_MEMORY_CONTEXT": build_prompt_context(
                mem_store, graph, state, world, names=brain_names,
            ),
            "RELATIONSHIP_DYNAMICS_CONTEXT": build_dynamics_prompt_context(
                dyn_store, graph, state, world, names=brain_names,
            ),
            "CHARACTER_BRAIN_relationship_block": read_api_for_brain(
                brain_names, world, state, memory_store=mem_store, dynamics_store=dyn_store,
            ),
        }
        rel_tokens = sum(estimate_text_tokens(v) for v in rel_parts.values())

        director_text = prepare_director_prompt(
            state, world,
            memory=memory,
            graph=graph,
            relationship_memory=mem_store,
            relationship_dynamics=dyn_store,
            plot_state=plot_state,
        )
        director_tokens = estimate_text_tokens(director_text)
        total = rel_tokens + director_tokens

        return {
            "relationship_tokens": rel_tokens,
            "director_plan_tokens": director_tokens,
            "director_plan_chars": len(director_text),
            "total_tokens": total,
            "target_tokens": 1800,
            "within_budget": total <= 1800,
            "relationship_breakdown": {k: estimate_text_tokens(v) for k, v in rel_parts.items()},
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def measure_narrative_influence(turns: int = 100, seed: int = 3) -> dict:
    """
    Reuse full runtime simulation (relationship + director).
    LLM obedience cannot be measured without API — listed as observation.
    """
    run = simulate_director_runtime(turns, seed=seed)
    finalized = run["resolved_count"] + run["failed_count"]
    return {
        "turns": turns,
        "active_turn_ratio": run["active_turn_ratio"],
        "lifecycle_count": run["lifecycle_count"],
        "resolved_count": run["resolved_count"],
        "failed_count": run["failed_count"],
        "scheduler_engaged": run["active_turn_ratio"] >= 0.5,
        "events_finalized": finalized >= turns * 0.2,
        "llm_obedience_measurable": False,
        "pass": run["active_turn_ratio"] >= 0.5 and finalized >= turns * 0.2,
    }


def main() -> None:
    long_runs = [simulate_director_runtime(n, seed=0) for n in (50, 100, 200)]
    cooldown = measure_cooldown_effectiveness(200, seed=7)
    prompt = measure_prompt_budget_worst_case()
    narrative = measure_narrative_influence(100, seed=3)

    runtime_pass = all(
        r["stuck_events"] == 0 and r["lifecycle_count"] <= r["turns"]
        for r in long_runs
    )

    metrics = {
        "long_runs": long_runs,
        "cooldown": cooldown,
        "prompt_budget": prompt,
        "narrative_influence": narrative,
        "summary": {
            "runtime_stability_pass": runtime_pass,
            "cooldown_pass": cooldown["pass"],
            "prompt_budget_pass": prompt["within_budget"],
            "narrative_pass": narrative["pass"],
            "all_pass": runtime_pass and cooldown["pass"] and prompt["within_budget"] and narrative["pass"],
        },
    }

    out_path = OUT_DIR / "metrics.json"
    out_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")
    print(json.dumps(metrics["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
