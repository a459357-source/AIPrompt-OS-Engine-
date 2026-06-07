"""
state_manager.py — State machine, interaction & force-event logic
==================================================================
Consumes the AI's output JSON and applies it to session_state.yaml,
enforcing the state-machine rules defined in the spec.

Responsibilities:
  • Validate & apply the AI's state update
  • Enforce status transitions (SETUP→BUILD→TENSION→CLIMAX→COOLDOWN)
  • Enforce interaction-level progression
  • Detect force-event conditions for the *next* turn
  • Append turn summary to history
"""

import copy
import logging
from datetime import datetime

import config
from engine import io_utils

logger = logging.getLogger(__name__)


# ── Public API ─────────────────────────────────────────────────────

def apply_turn(
    ai_response: dict,
    choice: str | None = None,
    *,
    session: dict | None = None,
    persist: bool = True,
) -> dict:
    """
    Apply one turn's AI output to session state.

    Args:
        ai_response: The parsed JSON dict from DeepSeek containing
                     "story", "state", and "options".
        choice:      The player's choice for this turn (A/B/C/D), or None
                     for auto-continue mode.
        session:     Existing session dict; reads from disk if omitted.
        persist:     Write session_state.yaml when True (default).

    Returns:
        The updated session_state dict.
    """
    current = session if session is not None else io_utils.read_yaml(config.SESSION_STATE_PATH)

    # Snapshot before mutation for history
    snapshot = _snapshot(current)

    # Extract the AI-proposed state
    proposed = ai_response.get("state", {})

    # Merge the proposed state into current, with rule enforcement
    new_state = _merge_and_enforce(current, proposed)

    # Persist the player's choice
    if choice:
        new_state["last_choice"] = choice

    # Append history entry
    full_story = ai_response.get("story", "")
    history_entry = {
        "turn": snapshot["turn"],
        "scene": snapshot["scene"],
        "status": snapshot["status"],
        "characters": snapshot.get("characters", {}),
        "story": full_story,
        "summary": full_story[:120],
        "options": ai_response.get("options", []),
        "choice": choice,
    }
    new_state.setdefault("history", []).append(history_entry)

    # Check force-event for *next* turn and set flag
    triggered, reason = _check_force_conditions(new_state)
    new_state["force_event_pending"] = triggered

    if triggered:
        logger.warning("⚡ FORCE_EVENT flagged for next turn: %s", reason)

    if persist:
        io_utils.write_yaml(config.SESSION_STATE_PATH, new_state)

    return new_state


def validate_response(ai_response: dict) -> list[str]:
    """
    Validate the AI's response against engine rules.
    Returns a list of warning/error strings (empty = valid).
    """
    warnings: list[str] = []

    proposed = ai_response.get("state", {})
    if not isinstance(proposed, dict):
        warnings.append("state field is not a dict")
        return warnings

    status = proposed.get("status", "")
    if status not in config.STATUS_ORDER:
        warnings.append(f"Unknown status '{status}'; must be one of {config.STATUS_ORDER}")

    if not isinstance(ai_response.get("story"), str) or len(ai_response["story"]) < 20:
        warnings.append("story field is too short or missing")

    opts = ai_response.get("options", [])
    expected = config.OPTION_COUNT
    if not isinstance(opts, list) or len(opts) != expected:
        warnings.append(
            f"options must be a list of {expected}; got "
            f"{len(opts) if isinstance(opts, list) else type(opts).__name__}"
        )

    return warnings


# ── Internal helpers ───────────────────────────────────────────────

def _snapshot(state: dict) -> dict:
    """Return a lightweight copy of the current state for history logging."""
    return {
        "turn": state.get("turn", 0),
        "scene": state.get("scene", ""),
        "status": state.get("status", "SETUP"),
        "characters": copy.deepcopy(state.get("characters", {})),
    }


def _merge_and_enforce(current: dict, proposed: dict) -> dict:
    """
    Merge the AI's proposed state into current, applying hard rules.

    Rules enforced here:
      1. turn must increment by 1
      2. status can only advance forward (never backward)
      3. CLIMAX → COOLDOWN is mandatory if AI proposes CLIMAX
      4. Interaction level can only stay or increase
    """
    merged = copy.deepcopy(current)

    # ── Turn ────────────────────────────────────────────────────
    merged["turn"] = current.get("turn", 0) + 1

    # ── Scene ───────────────────────────────────────────────────
    if proposed.get("scene"):
        merged["scene"] = proposed["scene"]

    # ── Status — enforce forward-only progression ───────────────
    old_status = current.get("status", "SETUP")
    new_status = proposed.get("status", old_status)

    old_idx = config.STATUS_ORDER.index(old_status) if old_status in config.STATUS_ORDER else 0
    new_idx = config.STATUS_ORDER.index(new_status) if new_status in config.STATUS_ORDER else old_idx

    if new_idx < old_idx:
        logger.warning(
            "AI attempted backward status move %s → %s; keeping %s",
            old_status, new_status, old_status,
        )
        new_idx = old_idx
        new_status = old_status

    # CLIMAX → COOLDOWN enforcement (spec: "CLIMAX后必须进入COOLDOWN")
    if old_status == "CLIMAX":
        if new_status != "COOLDOWN":
            logger.warning(
                "Previous turn was CLIMAX — forcing status COOLDOWN (AI proposed %s)",
                new_status,
            )
            new_status = "COOLDOWN"
            new_idx = config.STATUS_ORDER.index("COOLDOWN")

    # COOLDOWN → SETUP is allowed (new chapter cycle)
    if old_status == "COOLDOWN" and new_status == "SETUP":
        chapter = current.get("chapter", 1) + 1
        merged["chapter"] = chapter
        logger.info("📖 New chapter %d started", chapter)
        new_idx = 0  # SETUP

    if new_status == "CLIMAX":
        logger.info("CLIMAX reached — next turn will be forced to COOLDOWN")

    merged["status"] = new_status

    # ── Characters — enforce interaction level monotonicity ─────
    old_chars: dict = current.get("characters", {})
    new_chars: dict = proposed.get("characters", {})

    merged_chars: dict = {}
    for key in old_chars:
        old_char = old_chars[key]
        new_char = new_chars.get(key, old_char)

        old_level = old_char.get("level", "L0")
        new_level = new_char.get("level", old_level)

        old_lvl_idx = _level_idx(old_level)
        new_lvl_idx = _level_idx(new_level)

        if new_lvl_idx < old_lvl_idx:
            logger.warning(
                "AI attempted to decrease interaction level for %s (%s → %s); keeping %s",
                key, old_level, new_level, old_level,
            )
            new_level = old_level

        merged_chars[key] = {**old_char, **new_char, "level": new_level}

    # Keep any new characters the AI introduced
    for key in new_chars:
        if key not in merged_chars:
            merged_chars[key] = new_chars[key]

    merged["characters"] = merged_chars

    return merged


def _level_idx(level: str) -> int:
    """Convert L0-L4 string to integer index."""
    try:
        return config.INTERACTION_LEVELS.index(level)
    except ValueError:
        return 0


def _check_force_conditions(state: dict) -> tuple[bool, str]:
    """
    Post-turn check: should the NEXT turn be a force-event?

    Mirrors builder.py's detection but runs after state is persisted
    so the flag is available for the next build_prompt() call.
    """
    from engine.builder import _detect_force_event
    return _detect_force_event(state)
