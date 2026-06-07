"""
stress_validator.py — 自动剧情压力测试校验
检查：人设、memory、story_graph、token 控制
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import config
from engine import io_utils
from engine.analytics import _canonical_character_names
from engine.memory_names import is_valid_character_name as _is_valid_character_name
from engine.router import load_graph


@dataclass
class StressCheckResult:
    ok: bool
    category: str
    message: str
    severity: str = "error"  # error | warn | info
    details: dict[str, Any] = field(default_factory=dict)


def _load_all() -> tuple[dict, dict, dict, dict]:
    state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    memory = io_utils.read_json(config.MEMORY_PATH)
    graph = load_graph()
    world = io_utils.read_yaml(config.WORLD_PACK_PATH)
    return state, memory, graph, world.get("world", world)


def check_memory_integrity(memory: dict, world: dict) -> list[StressCheckResult]:
    results: list[StressCheckResult] = []
    mem_chars = memory.get("characters", {})
    canonical = set(_canonical_character_names(memory))
    garbage: list[str] = []

    for name, data in mem_chars.items():
        if not _is_valid_character_name(name) and name not in canonical:
            garbage.append(name)
        trust = data.get("trust")
        if trust is not None and not (0 <= float(trust) <= 1):
            results.append(StressCheckResult(
                False, "memory", f"角色 {name} trust 越界: {trust}", "error",
            ))
        for metric in ("affection", "respect", "dependence", "hostility", "attraction"):
            val = data.get(metric)
            if val is not None and not (0 <= float(val) <= 1):
                results.append(StressCheckResult(
                    False, "memory", f"角色 {name} {metric} 越界: {val}", "error",
                ))

    wp_names = {c.get("name", "") for c in world.get("characters", []) if c.get("name")}
    core_missing = wp_names - set(mem_chars.keys())
    if core_missing and len(wp_names) >= 2:
        results.append(StressCheckResult(
            False, "memory",
            f"world_pack 主角/核心角色未在 memory 中: {sorted(core_missing)[:5]}",
            "warn",
            {"missing": list(core_missing)[:10]},
        ))

    if garbage:
        results.append(StressCheckResult(
            len(garbage) <= 5, "memory",
            f"memory 含 {len(garbage)} 个疑似叙事碎片角色名",
            "warn" if len(garbage) <= 10 else "error",
            {"garbage_sample": garbage[:15]},
        ))
    else:
        results.append(StressCheckResult(True, "memory", "memory 角色名无异常碎片", "info"))

    factions = memory.get("factions", {})
    if not isinstance(factions, dict):
        results.append(StressCheckResult(False, "memory", "factions 非 dict", "error"))
    else:
        for fname, fdata in factions.items():
            rep = fdata.get("reputation", 0.5)
            if not (0 <= float(rep) <= 1):
                results.append(StressCheckResult(
                    False, "memory", f"势力 {fname} reputation 越界", "error",
                ))

    events = memory.get("world_events", [])
    if not isinstance(events, list):
        results.append(StressCheckResult(False, "memory", "world_events 非 list", "error"))
    else:
        results.append(StressCheckResult(
            True, "memory", f"world_events 共 {len(events)} 条", "info",
            {"active": sum(1 for e in events if e.get("status") == "active")},
        ))

    try:
        json.dumps(memory)
        results.append(StressCheckResult(True, "memory", "memory JSON 可序列化", "info"))
    except (TypeError, ValueError) as exc:
        results.append(StressCheckResult(False, "memory", f"memory 序列化失败: {exc}", "error"))

    return results


def check_story_graph(state: dict, graph: dict, *, start_nodes: int | None = None) -> list[StressCheckResult]:
    results: list[StressCheckResult] = []
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])
    current = graph.get("current_node")
    turn = state.get("turn", 0)

    if not nodes:
        return [StressCheckResult(False, "graph", "story_graph 无节点", "error")]

    if current not in nodes:
        results.append(StressCheckResult(
            False, "graph", f"current_node={current} 不存在", "error",
        ))

    if len(nodes) < 2 and turn > 0:
        results.append(StressCheckResult(False, "graph", "有回合但节点过少", "warn"))

    if start_nodes is not None:
        growth = len(nodes) - start_nodes
        if turn > 0 and growth < max(1, turn // 3):
            results.append(StressCheckResult(
                False, "graph",
                f"节点增长偏慢: +{growth} nodes（turn={turn}）",
                "warn",
                {"nodes": len(nodes), "start": start_nodes, "turn": turn},
            ))
        else:
            results.append(StressCheckResult(
                True, "graph",
                f"节点 {len(nodes)}（+{growth}），边 {len(edges)}",
                "info",
            ))

    for nid, node in list(nodes.items())[:3]:
        if node.get("turn", 0) > turn:
            results.append(StressCheckResult(
                False, "graph", f"节点 {nid} turn 超前于 session", "error",
            ))
            break
    else:
        results.append(StressCheckResult(True, "graph", "节点 turn 与 session 一致", "info"))

    return results


def check_persona(state: dict, world: dict, memory: dict) -> list[StressCheckResult]:
    """人设：session 角色 note 仍含 world_pack 中的身份/性格关键词。"""
    results: list[StressCheckResult] = []
    wp_chars = {c.get("name"): c for c in world.get("characters", []) if c.get("name")}
    session_chars = state.get("characters", {})

    drifted: list[str] = []
    for key, sc in session_chars.items():
        name = sc.get("name", "")
        wp = wp_chars.get(name)
        if not wp or wp.get("isMain"):
            continue
        role = (wp.get("role") or sc.get("role") or "")[:20]
        note = sc.get("note") or ""
        if role and role not in note and name not in note:
            drifted.append(name)
        tags = wp.get("personality_tags") or []
        if tags and not any(t in note for t in tags[:2]):
            if sc.get("level") != "L0" or len(note) > 50:
                pass  # 仅 warn 非空 note 缺标签

    main_chars = [c for c in wp_chars.values() if c.get("isMain")]
    for mc in main_chars:
        name = mc.get("name", "")
        sc = next((s for s in session_chars.values() if s.get("name") == name), None)
        if sc:
            note = sc.get("note") or ""
            role = mc.get("role", "")
            if len(note) < 20:
                results.append(StressCheckResult(
                    False, "persona", f"主角 {name} note 过短", "warn",
                ))
            elif role and role.split("/")[0].strip() not in note:
                results.append(StressCheckResult(
                    False, "persona", f"主角 {name} note 可能丢失身份描述", "warn",
                ))

    if drifted:
        results.append(StressCheckResult(
            len(drifted) <= 2, "persona",
            f"{len(drifted)} 个角色 note 与初始设定偏离",
            "warn", {"drifted": drifted[:8]},
        ))
    else:
        results.append(StressCheckResult(True, "persona", "核心角色 note 基本保留设定", "info"))

    return results


def check_token_control(
    *,
    story_length: int,
    recent_usage: list[dict] | None = None,
) -> list[StressCheckResult]:
    results: list[StressCheckResult] = []
    max_out = config.MAX_TOKENS
    ctx = config.DEEPSEEK_CONTEXT_TOKENS
    matched = config.tokens_for_story_length(story_length, option_count=config.OPTION_COUNT)

    if config.MAX_TOKENS != matched:
        results.append(StressCheckResult(
            False, "token",
            f"max_tokens={config.MAX_TOKENS} 与 story_length={story_length} 不同步（期望≈{matched}）",
            "warn",
        ))
    else:
        results.append(StressCheckResult(
            True, "token",
            f"max_tokens={max_out} 与目标字数 {story_length} 同步",
            "info",
        ))

    if recent_usage:
        over = [u for u in recent_usage if u.get("total_tokens", 0) > ctx * 0.9]
        if over:
            results.append(StressCheckResult(
                False, "token",
                f"{len(over)} 次调用 total_tokens 接近上下文上限",
                "warn",
            ))
        comp_max = max((u.get("completion_tokens", 0) for u in recent_usage), default=0)
        if comp_max > config.DEEPSEEK_MAX_OUTPUT_TOKENS * 0.95:
            results.append(StressCheckResult(
                False, "token", f"completion_tokens 峰值 {comp_max} 接近输出上限", "error",
            ))

    return results


def run_all_checks(
    *,
    story_length: int = 600,
    start_nodes: int | None = None,
    recent_usage: list[dict] | None = None,
) -> list[StressCheckResult]:
    state, memory, graph, world = _load_all()
    out: list[StressCheckResult] = []
    out.extend(check_memory_integrity(memory, world))
    out.extend(check_story_graph(state, graph, start_nodes=start_nodes))
    out.extend(check_persona(state, world, memory))
    out.extend(check_token_control(story_length=story_length, recent_usage=recent_usage))
    return out


def summarize(results: list[StressCheckResult]) -> dict:
    errors = [r for r in results if not r.ok and r.severity == "error"]
    warns = [r for r in results if not r.ok and r.severity == "warn"]
    return {
        "passed": len(errors) == 0,
        "error_count": len(errors),
        "warn_count": len(warns),
        "total": len(results),
        "errors": [{"category": r.category, "message": r.message} for r in errors],
        "warnings": [{"category": r.category, "message": r.message} for r in warns],
    }
