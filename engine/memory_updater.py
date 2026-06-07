"""
memory_updater.py — Incremental Memory Update Helpers
=======================================================
Splits the monolithic _update_memory() from run.py into focused,
independently-saveable helpers.  Each helper saves memory after
its own work, so a mid-function exception only loses that step's
changes — not everything from the current turn.

Responsibilities:
  1. init_world_state    — factions, attitudes, events seeding (once)
  2. auto_register_npcs  — NPC discovery, tier assignment, migration
  3. apply_trust_deltas  — option deltas + heuristic keyword trust
  4. update_factions     — reputation, inter-faction attitudes, drift
"""

import logging
import re

import config
from engine import io_utils
from engine.memory import (
    load_memory, save_memory, update_trust, set_flag,
    guess_trust_delta_from_story,
    parse_option_trust_deltas, detect_new_characters_from_story,
    get_initial_trust,
    init_factions, update_faction_reputation,
    init_faction_attitudes, update_faction_attitude,
    assign_character_tier, degrade_inactive_characters,
)
from engine.events import init_events, check_event_triggers, seed_default_events
from engine.world_driver import passive_faction_drift
from engine.constants import (
    FACTION_REPUTATION_DELTA,
    INTER_FACTION_ATTITUDE_DELTA, INTER_FACTION_ATTITUDE_DELTA_REVERSE,
    INTER_FACTION_ATTITUDE_DELTA_NEG, INTER_FACTION_ATTITUDE_DELTA_NEG_REVERSE,
)

logger = logging.getLogger(__name__)


# ── 1. World State Initialization ──────────────────────────────────

def init_world_state(memory: dict, world_pack: dict, turn: int = 0) -> None:
    """
    One-time world state setup: register factions, attitudes, events.
    Idempotent — factions/attitudes/events are only created once.
    Saves memory after each initialization step.
    """
    # Factions
    existing_factions = memory.get("factions", {})
    init_factions(memory)
    if memory.get("factions", {}) != existing_factions:
        save_memory(memory)

    # Inter-faction attitudes
    existing_attitudes = memory.get("faction_attitudes", {})
    init_faction_attitudes(memory)
    if memory.get("faction_attitudes", {}) != existing_attitudes:
        save_memory(memory)

    # Events
    init_events(memory)
    if not memory.get("world_events"):
        seed_default_events(memory, world_pack)
        save_memory(memory)
        logger.info("Memory updater: seeded default events (turn %d)", turn)

    # Check triggers
    triggered = check_event_triggers(memory, turn)
    for evt in triggered:
        logger.info("Event triggered: %s (turn %d)", evt.get("title"), turn)


# ── 2. NPC Auto-Registration ───────────────────────────────────────

def auto_register_npcs(memory: dict, state: dict, world_pack: dict,
                        turn: int = 0, story: str = "") -> None:
    """
    Discover and register NPCs from session state and story text.

    Steps:
      a) Register NPCs from state.characters
      b) Assign character tiers (core / important / background)
      c) One-time trust migration for legacy data
      d) Detect new characters from story text (fallback)
      e) Track last_appearance_turn + degrade inactive characters
    """
    mem_chars = memory.setdefault("characters", {})
    world_chars = world_pack.get("world", {}).get("characters", [])

    # (a) Register from session state
    state_chars = state.get("characters", {})
    for key, sc in state_chars.items():
        name = sc.get("name", key)
        if name not in mem_chars:
            init_trust = get_initial_trust(name, world_pack)
            char_faction = ""
            for wc in world_chars:
                if wc.get("name") == name:
                    char_faction = wc.get("faction", "")
                    break
            mem_chars[name] = {
                "trust": init_trust,
                "flags": [],
                "relationship": sc.get("relation", ""),
                "role": sc.get("role", ""),
                "faction": char_faction,
            }
            mem_chars[name].setdefault("metric_history", {}).setdefault(
                "trust", []
            ).append([turn, init_trust])
            logger.info(
                "Memory updater: auto-registered '%s' (turn %d, trust=%.2f)",
                name, turn, init_trust,
            )

    # (b) Tier assignment for unclassified characters
    for name in list(mem_chars.keys()):
        if not mem_chars[name].get("tier"):
            is_main = any(
                wc.get("name") == name and wc.get("is_main")
                for wc in world_chars
            )
            assign_character_tier(memory, name, world_pack, is_main=is_main)

    # (c) One-time trust migration
    if not memory.get("_trust_migrated"):
        for name in list(mem_chars.keys()):
            old_trust = mem_chars[name].get("trust", 0.5)
            if old_trust in (0.5, 0.0):
                new_trust = get_initial_trust(name, world_pack)
                if abs(new_trust - old_trust) > 0.01:
                    mem_chars[name]["trust"] = new_trust
                    logger.info(
                        "Memory updater: migrated '%s' trust %.2f → %.2f",
                        name, old_trust, new_trust,
                    )
        memory["_trust_migrated"] = True
        save_memory(memory)

    # (d) Detect new characters from story text (fallback)
    known = set(mem_chars.keys())
    story_newcomers = detect_new_characters_from_story(story, known)
    for name in story_newcomers:
        init_trust = get_initial_trust(name, world_pack)
        init_trust = round(init_trust * 0.8, 2)  # story-detected = lower trust
        mem_chars[name] = {
            "trust": init_trust,
            "flags": [],
            "relationship": "",
            "role": "story-detected",
            "faction": "",
        }
        mem_chars[name].setdefault("metric_history", {}).setdefault(
            "trust", []
        ).append([turn, init_trust])
        assign_character_tier(memory, name, world_pack)
        logger.info(
            "Memory updater: story-detected '%s' (turn %d, trust=%.2f)",
            name, turn, init_trust,
        )

    # (e) Track appearance + degrade inactive
    for name in list(mem_chars.keys()):
        if name in story:
            mem_chars[name]["last_appearance_turn"] = turn

    degrade_messages = degrade_inactive_characters(memory, turn)
    for msg in degrade_messages:
        logger.info(msg)

    save_memory(memory)


# ── 3. Trust Delta Application ─────────────────────────────────────

def apply_trust_deltas(memory: dict, story: str, choice: str | None,
                        turn: int, prev_options: list[str]) -> None:
    """
    Apply trust changes from two sources:
      a) Player's chosen option from the *previous* turn (explicit deltas)
      b) Heuristic keyword scanning of the current story text
    """
    mem_chars = memory.setdefault("characters", {})

    # (a) Option-based deltas from the chosen previous-turn option
    if choice and prev_options:
        choice_map = {"A": 0, "B": 1, "C": 2, "D": 3}
        idx = choice_map.get(choice.upper(), -1)
        if 0 <= idx < len(prev_options):
            chosen_opt = prev_options[idx]
            option_deltas = parse_option_trust_deltas([chosen_opt])
            for char_name, delta in option_deltas:
                matched = False
                for mem_name in list(mem_chars.keys()):
                    if char_name in mem_name or mem_name in char_name:
                        update_trust(memory, mem_name, delta, turn)
                        matched = True
                        logger.info(
                            "Memory updater: choice %s trust delta %s %+.2f (matched '%s')",
                            choice, mem_name, delta, char_name,
                        )
                if not matched:
                    update_trust(memory, char_name, delta, turn)
                    logger.info(
                        "Memory updater: choice %s trust delta %s %+.2f (new char)",
                        choice, char_name, delta,
                    )

    # (b) Heuristic trust deltas from story keywords
    deltas = guess_trust_delta_from_story(story)
    for char_name, delta, flag in deltas:
        if char_name == "__all_present__":
            for name in list(mem_chars.keys()):
                if name in story:
                    update_trust(memory, name, delta, turn)
        else:
            update_trust(memory, char_name, delta, turn)

        if flag:
            if char_name != "__all_present__":
                set_flag(memory, char_name, flag)
            else:
                applied = False
                for name in list(mem_chars.keys()):
                    if name in story:
                        set_flag(memory, name, flag)
                        applied = True
                        break
                if not applied:
                    set_flag(memory, None, flag)

    save_memory(memory)


# ── 4. Faction Dynamics ────────────────────────────────────────────

def update_factions(memory: dict, story: str, turn: int) -> None:
    """
    Update faction reputation, inter-faction attitudes, and passive drift
    based on the current turn's story content.
    """
    mem_factions = memory.get("factions", {})

    # (a) Faction reputation from story keywords
    for fname in list(mem_factions.keys()):
        if fname in story:
            pos = any(kw in story for kw in [
                "合作", "支援", "友好", "结盟", "信任",
            ])
            neg = any(kw in story for kw in [
                "敌对", "攻击", "背叛", "威胁", "警告",
            ])
            if pos and not neg:
                update_faction_reputation(memory, fname, FACTION_REPUTATION_DELTA, turn)
            elif neg and not pos:
                update_faction_reputation(memory, fname, -FACTION_REPUTATION_DELTA, turn)

    # (b) Inter-faction attitudes from story
    fnames = list(mem_factions.keys())
    if len(fnames) >= 2:
        sentences = re.split(r'[。！？\n]', story)
        for sent in sentences:
            mentioned = [f for f in fnames if f in sent]
            for i, fa in enumerate(mentioned):
                for fb in mentioned[i + 1:]:
                    pos = any(kw in sent for kw in [
                        "合作", "结盟", "支援", "友好", "信任", "联手",
                        "和解", "协议", "共同", "协助",
                    ])
                    neg = any(kw in sent for kw in [
                        "敌对", "攻击", "背叛", "威胁", "警告", "打压",
                        "冲突", "对抗", "撕毁", "决裂", "宣战",
                    ])
                    if pos and not neg:
                        update_faction_attitude(memory, fa, fb, INTER_FACTION_ATTITUDE_DELTA, turn)
                        update_faction_attitude(memory, fb, fa, INTER_FACTION_ATTITUDE_DELTA_REVERSE, turn)
                    elif neg and not pos:
                        update_faction_attitude(memory, fa, fb, INTER_FACTION_ATTITUDE_DELTA_NEG, turn)
                        update_faction_attitude(memory, fb, fa, INTER_FACTION_ATTITUDE_DELTA_NEG_REVERSE, turn)

    # (c) Passive drift
    passive_faction_drift(memory, turn)

    save_memory(memory)
