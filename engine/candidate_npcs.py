"""
candidate_npcs.py — Candidate NPC 池（第一次见只进池，第二次正式注册，第三次激活关系）
"""

from __future__ import annotations

import logging

import config
from engine import io_utils
from engine.memory import get_initial_trust, save_memory
from engine.memory_names import (
    NameVerdict,
    assess_npc_name,
    is_memory_active_npc,
    is_valid_character_name,
)
from engine.memory import assign_character_tier

logger = logging.getLogger(__name__)

PROMOTE_COUNT_NORMAL = 2
PROMOTE_COUNT_LOW_WEIGHT = 3
ACTIVATE_AFTER_PROMOTE_NORMAL = 1  # 第 3 次总出现
ACTIVATE_AFTER_PROMOTE_LOW = 2     # 低权重：第 4 次总出现


def load_pool() -> dict[str, dict]:
    path = config.CANDIDATE_NPCS_PATH
    if not path.exists():
        return {}
    try:
        data = io_utils.read_json(path)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_pool(pool: dict, *, persist: bool = True) -> None:
    if not persist:
        return
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    io_utils.write_json(config.CANDIDATE_NPCS_PATH, pool)


def _promote_threshold(entry: dict) -> int:
    return PROMOTE_COUNT_LOW_WEIGHT if entry.get("low_weight") else PROMOTE_COUNT_NORMAL


def _activate_threshold(entry: dict) -> int:
    if entry.get("low_weight"):
        return PROMOTE_COUNT_LOW_WEIGHT + ACTIVATE_AFTER_PROMOTE_LOW
    return PROMOTE_COUNT_NORMAL + ACTIVATE_AFTER_PROMOTE_NORMAL


def try_register_sighting(
    name: str,
    turn: int,
    memory: dict,
    world_pack: dict,
    *,
    persist: bool = True,
) -> str | None:
    """
    Record a NPC name sighting. Returns action: 'candidate' | 'promoted' | 'activated' | None.
    """
    name = (name or "").strip()
    verdict = assess_npc_name(name)
    if verdict == NameVerdict.REJECT:
        logger.debug("Candidate NPC rejected: '%s'", name)
        return None

    world = world_pack.get("world", world_pack)
    for ch in world.get("characters", []):
        if ch.get("name") == name:
            return None

    if name in memory.get("characters", {}):
        entry = memory["characters"][name]
        if entry.get("npc_stage") == "incubating":
            pool = load_pool()
            if name in pool:
                pool[name]["appear_count"] = pool[name].get("appear_count", 0) + 1
                pool[name]["last_turn"] = turn
                save_pool(pool, persist=persist)
                if pool[name]["appear_count"] >= _activate_threshold(pool[name]):
                    entry["npc_stage"] = "active"
                    pool[name]["activated"] = True
                    save_pool(pool, persist=persist)
                    save_memory(memory, persist=persist)
                    logger.info("Candidate NPC '%s' activated (turn %d)", name, turn)
                    return "activated"
        return None

    pool = load_pool()
    low_weight = verdict == NameVerdict.LOW_WEIGHT

    if name not in pool:
        pool[name] = {
            "appear_count": 1,
            "first_turn": turn,
            "last_turn": turn,
            "low_weight": low_weight,
            "promoted": False,
            "activated": False,
        }
        save_pool(pool, persist=persist)
        logger.info("Candidate NPC '%s' first sighting (turn %d)", name, turn)
        return "candidate"

    entry = pool[name]
    entry["appear_count"] = int(entry.get("appear_count", 0)) + 1
    entry["last_turn"] = turn
    entry.setdefault("low_weight", low_weight)

    threshold = _promote_threshold(entry)
    if not entry.get("promoted") and entry["appear_count"] >= threshold:
        _promote_to_memory(name, memory, world_pack, turn, entry, persist=persist)
        entry["promoted"] = True
        save_pool(pool, persist=persist)
        return "promoted"

    if entry.get("promoted") and entry["appear_count"] >= _activate_threshold(entry):
        mem_entry = memory.get("characters", {}).get(name)
        if mem_entry and mem_entry.get("npc_stage") == "incubating":
            mem_entry["npc_stage"] = "active"
            entry["activated"] = True
            save_memory(memory, persist=persist)
            save_pool(pool, persist=persist)
            logger.info("Candidate NPC '%s' activated (turn %d)", name, turn)
            return "activated"

    save_pool(pool, persist=persist)
    return "candidate"


def _promote_to_memory(
    name: str,
    memory: dict,
    world_pack: dict,
    turn: int,
    pool_entry: dict,
    *,
    persist: bool,
) -> None:
    mem_chars = memory.setdefault("characters", {})
    init_trust = round(get_initial_trust(name, world_pack) * 0.8, 2)
    mem_chars[name] = {
        "trust": init_trust,
        "flags": [],
        "relationship": "",
        "role": "story-detected",
        "faction": "",
        "npc_stage": "incubating",
        "promoted_turn": turn,
        "metric_history": {"trust": [[turn, init_trust]]},
    }
    assign_character_tier(memory, name, world_pack)
    save_memory(memory, persist=persist)
    logger.info(
        "Candidate NPC '%s' promoted to memory (turn %d, appearances=%d)",
        name, turn, pool_entry.get("appear_count"),
    )


def scan_story_sightings(
    story: str,
    turn: int,
    memory: dict,
    world_pack: dict,
    known_from_detection: list[str] | None = None,
    *,
    persist: bool = True,
) -> list[str]:
    """
    Bump candidate pool for names appearing in story + explicit detections.
    Returns list of actions taken.
    """
    from engine.memory import detect_new_characters_from_story

    actions: list[str] = []
    mem_names = set(memory.get("characters", {}))
    pool = load_pool()
    candidates = set(known_from_detection or [])
    candidates.update(detect_new_characters_from_story(story, mem_names | set(pool.keys())))

    # Names explicitly in story (full roster from pool + valid 2-8 char names)
    for n in list(pool.keys()):
        if n in story:
            candidates.add(n)

    for name in sorted(candidates):
        if not is_valid_character_name(name):
            continue
        action = try_register_sighting(name, turn, memory, world_pack, persist=persist)
        if action:
            actions.append(f"{name}:{action}")

    return actions


def reset_pool(*, persist: bool = True) -> None:
    save_pool({}, persist=persist)
