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
    parse_option_trust_deltas, parse_option_metric_deltas,
    detect_new_characters_from_story,
    get_initial_trust,
    init_factions, update_faction_reputation,
    init_faction_attitudes, update_faction_attitude,
    assign_character_tier, degrade_inactive_characters,
    init_artifacts, transfer_artifact,
)
from engine.constants import (
    ARTIFACT_TRANSFER_KEYWORDS,
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

def init_world_state(memory: dict, world_pack: dict, turn: int = 0, *, persist: bool = True) -> None:
    """
    One-time world state setup: register factions, attitudes, events.
    Idempotent — factions/attitudes/events are only created once.
    Saves memory after each initialization step.
    """
    # Factions
    existing_factions = memory.get("factions", {})
    init_factions(memory)
    if memory.get("factions", {}) != existing_factions:
        save_memory(memory, persist=persist)

    # Inter-faction attitudes
    existing_attitudes = memory.get("faction_attitudes", {})
    init_faction_attitudes(memory)
    if memory.get("faction_attitudes", {}) != existing_attitudes:
        save_memory(memory, persist=persist)

    # Events
    init_events(memory)
    if not memory.get("world_events"):
        seed_default_events(memory, world_pack)
        save_memory(memory, persist=persist)
        logger.info("Memory updater: seeded default events (turn %d)", turn)

    # Check triggers
    triggered = check_event_triggers(memory, turn)
    for evt in triggered:
        logger.info("Event triggered: %s (turn %d)", evt.get("title"), turn)

    # Artifacts
    existing_artifacts = memory.get("artifacts", {})
    init_artifacts(memory)
    if memory.get("artifacts", {}) != existing_artifacts:
        save_memory(memory, persist=persist)


# ── 2. NPC Auto-Registration ───────────────────────────────────────

def auto_register_npcs(memory: dict, state: dict, world_pack: dict,
                        turn: int = 0, story: str = "", *, persist: bool = True) -> None:
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
        save_memory(memory, persist=persist)

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

    save_memory(memory, persist=persist)


# ── 3. Trust Delta Application ─────────────────────────────────────

def _resolve_chosen_option(choice: str | None, prev_options: list[str]) -> list[str]:
    """Map player choice (A/B/C/D, action text, or custom) to option strings to parse."""
    if not choice:
        return []
    texts: list[str] = []
    choice_map = {"A": 0, "B": 1, "C": 2, "D": 3}
    if choice.upper() in choice_map and prev_options:
        idx = choice_map[choice.upper()]
        if 0 <= idx < len(prev_options):
            texts.append(prev_options[idx])
    elif prev_options:
        stripped = choice.strip()
        for opt in prev_options:
            action = opt.split("→")[0].split("|")[0].strip()
            if stripped == action or stripped in opt or action in stripped:
                texts.append(opt)
                break
    # Custom / freeform: parse hints embedded in the choice itself
    texts.append(choice)
    return texts


def _apply_metric_deltas(memory: dict, deltas: list[tuple[str, str, float]], turn: int, source: str) -> None:
    mem_chars = memory.setdefault("characters", {})
    for char_name, metric, delta in deltas:
        matched = False
        for mem_name in list(mem_chars.keys()):
            if char_name in mem_name or mem_name in char_name:
                update_trust(memory, mem_name, delta, turn, metric=metric)
                matched = True
                logger.info(
                    "Memory updater: %s %s %s %+.2f (matched '%s')",
                    source, mem_name, metric, delta, char_name,
                )
        if not matched:
            update_trust(memory, char_name, delta, turn, metric=metric)
            logger.info(
                "Memory updater: %s %s %s %+.2f (new char)",
                source, char_name, metric, delta,
            )


def apply_trust_deltas(memory: dict, story: str, choice: str | None,
                        turn: int, prev_options: list[str], *, persist: bool = True) -> None:
    """
    Apply trust changes from two sources:
      a) Player's chosen option from the *previous* turn (explicit deltas)
      b) Heuristic keyword scanning of the current story text
    """
    mem_chars = memory.setdefault("characters", {})

    # (a) Option-based deltas — preset A-D, matched action text, or custom input
    if choice:
        for opt_text in _resolve_chosen_option(choice, prev_options):
            deltas = parse_option_metric_deltas([opt_text])
            if deltas:
                _apply_metric_deltas(memory, deltas, turn, f"choice[{choice[:12]}]")

    # (b) Heuristic trust deltas from story keywords (covers custom narrative outcomes)
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

    save_memory(memory, persist=persist)


# ── 4. Faction Dynamics ────────────────────────────────────────────

def update_factions(memory: dict, story: str, turn: int, *, persist: bool = True) -> None:
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

    # (d) Artifact transfer detection
    detect_artifact_transfers(memory, story, turn)

    save_memory(memory, persist=persist)


# ── 5. Artifact Transfer Detection ─────────────────────────────────

def detect_artifact_transfers(memory: dict, story: str, turn: int) -> None:
    """
    Scan story text for artifact names near transfer keywords.
    If a transfer is detected, update the artifact's owner.

    Uses ARTIFACT_TRANSFER_KEYWORDS from constants.py.
    """
    arts = memory.get("artifacts", {})
    if not arts or not story:
        return

    for art_name, art_data in arts.items():
        if art_data.get("status") != "active":
            continue
        if art_name not in story:
            continue

        # Find the keyword closest to the artifact mention
        art_idx = story.find(art_name)
        if art_idx < 0:
            continue

        # Search 80 chars around the artifact mention for transfer keywords
        window_start = max(0, art_idx - 40)
        window_end = min(len(story), art_idx + len(art_name) + 40)
        window = story[window_start:window_end]

        for kw, (action, direction) in ARTIFACT_TRANSFER_KEYWORDS.items():
            if kw not in window:
                continue

            if action == "destroy":
                from engine.memory import set_artifact_status
                set_artifact_status(memory, art_name, "destroyed")
                logger.info("Artifact updater: '%s' destroyed (turn %d, keyword: %s)",
                            art_name, turn, kw)
                break

            if action == "seal":
                from engine.memory import set_artifact_status
                set_artifact_status(memory, art_name, "sealed")
                logger.info("Artifact updater: '%s' sealed (turn %d, keyword: %s)",
                            art_name, turn, kw)
                break

            # Detect who gained/lost the artifact
            # Only match REAL characters (tier assigned, not story fragments)
            chars = memory.get("characters", {})
            real_names = [n for n, d in chars.items()
                          if d.get("tier") in ("主角", "核心", "重要")
                          and len(n) >= 2 and len(n) <= 4
                          and not any(c in '的是了我也就把能倒吸盯着露出' for c in n)]
            for char_name in real_names:
                if char_name in window and char_name != art_data.get("ownerId", ""):
                    if direction in ("acquire",):
                        transfer_artifact(memory, art_name, "character", char_name, turn,
                                          f"关键词检测: {kw}")
                        logger.info("Artifact updater: '%s' → %s (turn %d, keyword: %s)",
                                    art_name, char_name, turn, kw)
                        break
                    elif direction == "lose":
                        art_data["ownerType"] = "none"
                        art_data["ownerId"] = ""
                        art_data["status"] = "lost"
                        logger.info("Artifact updater: '%s' lost (turn %d, keyword: %s)",
                                    art_name, turn, kw)
                        break
            break  # Only apply first matching keyword per artifact
