"""
builder.py — Prompt constructor
=================================
Reads world-pack, session state, engine config, and the prompt
template, then interpolates everything into the final system + user
messages sent to DeepSeek.
"""

import json
import logging

import config
from engine import io_utils
from engine.memory import (
    load_memory, get_context_for_prompt,
    build_character_tier_context, get_faction_attitude_context,
)

logger = logging.getLogger(__name__)


def build_prompt() -> tuple[str, str]:
    """
    Build the (system_prompt, user_prompt) tuple for the current turn.

    Steps:
      1. Read YAML data files.
      2. Check force-event triggers.
      3. Interpolate the prompt template.
    """

    world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
    session_state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    engine_config = io_utils.read_yaml(config.ENGINE_CONFIG_PATH)
    template = io_utils.read_yaml(config.PROMPT_TEMPLATE_PATH)

    # ── Force-event detection ──────────────────────────────────
    # Priority 1: explicit flag set by state_manager last turn
    # Priority 2: independent detection from history
    if session_state.get("force_event_pending"):
        force_triggered = True
        force_reason = "上一轮 state_manager 标记的强制事件"
    else:
        force_triggered, force_reason = _detect_force_event(session_state)

    if force_triggered:
        force_notice = (
            "⚠️ FORCE_EVENT 已触发！原因：" + force_reason +
            "。本轮必须强制推进剧情：改变场景、推进状态、或插入重大事件。"
        )
        force_prompt = (
            "⚠️ FORCE_EVENT ACTIVE — Reason: " + force_reason + "\n"
            "You MUST advance the plot aggressively this turn: "
            "change the scene, advance the status, or insert a major event."
        )
    else:
        force_notice = "当前无强制事件。正常叙事节奏。"
        force_prompt = ""

    # ── Custom rules from world_pack ───────────────────────────
    custom = world_pack.get("custom", {})
    custom_rules_text = ""
    if custom:
        stats = custom.get("stats", [])
        stages = custom.get("stages", [])
        if stats:
            stat_labels = "、".join(s["label"] for s in stats)
            custom_rules_text += f"【专属追踪维度】本故事追踪以下维度：{stat_labels}。在故事中自然体现这些维度的变化。\n"
        if stages:
            stage_chain = " → ".join(stages)
            custom_rules_text += f"【关系阶段】角色关系阶段为：{stage_chain}。重要事件推进阶段变化。\n"

    # ── Main goal ──────────────────────────────────────────────
    world_data = world_pack.get("world", {})
    main_goal = world_data.get("main_goal", "")
    if not main_goal:
        main_goal = "推进剧情发展，探索角色关系"

    # ── Characters context ─────────────────────────────────────
    characters_list = world_data.get("characters", [])
    characters_context = ""
    if characters_list:
        lines = ["【角色信息】"]
        for ch in characters_list:
            name = ch.get("name", "?")
            is_main = "⭐主角" if ch.get("is_main") else "👤NPC"
            role_tags = ch.get("role_tags", [])
            role_str = " / ".join(role_tags) if role_tags else ""
            personality_tags = ch.get("personality_tags", [])
            pers_str = "、".join(personality_tags) if personality_tags else ""
            appearance = ch.get("appearance", "")
            relationship = ch.get("relationship", [])
            rel_str = "、".join(relationship) if relationship else ""
            goal = ch.get("goal", "")
            secret = ch.get("secret", "")
            background = ch.get("background", "")
            special_ability = ch.get("special_ability", "")
            parts = [f"{name}（{is_main}）"]
            if role_str: parts.append(f"身份：{role_str}")
            if appearance: parts.append(f"外貌：{appearance}")
            if pers_str: parts.append(f"性格：{pers_str}")
            if rel_str: parts.append(f"关系：{rel_str}")
            if goal: parts.append(f"目标：{goal}")
            if secret: parts.append(f"🔒秘密：{secret}")
            if background: parts.append(f"背景：{background}")
            if special_ability: parts.append(f"能力：{special_ability}")
            lines.append("  " + " | ".join(parts))
        characters_context = "\n".join(lines)

    # ── Relationship system ────────────────────────────────────
    rel_system = world_data.get("relationship_system", {})
    relationship_context = ""
    if rel_system:
        stages = rel_system.get("stages", [])
        affection = rel_system.get("affection", 0)
        if stages:
            stage_chain = " → ".join(stages)
            relationship_context = f"【关系系统】阶段递进：{stage_chain}。初始好感度：{affection}/100。角色关系应随剧情自然推进。"
        else:
            relationship_context = "【关系系统】使用默认7阶段好感度系统（陌生→认识→熟悉→朋友→暧昧→恋人→灵魂伴侣）。"
    if not relationship_context:
        relationship_context = "【关系系统】使用默认好感度系统。"

    # ── Interpolate system prompt ──────────────────────────────
    system_raw = template.get("system", "")
    system_prompt = (
        system_raw
        .replace("{{FORCE_EVENT_NOTICE}}", force_notice)
        .replace("{{STORY_LENGTH}}", str(config.STORY_LENGTH))
        .replace("{{CUSTOM_RULES}}", custom_rules_text)
        .replace("{{MAIN_GOAL}}", main_goal)
    )

    # ── Memory context ─────────────────────────────────────────
    memory = load_memory()
    memory_context = get_context_for_prompt(memory)

    # ── Character tier context ────────────────────────────────
    tier_context = build_character_tier_context(memory)

    # ── Faction attitude context ──────────────────────────────
    faction_attitude_context = get_faction_attitude_context(memory)

    # ── Last choice context ────────────────────────────────────
    last_choice = session_state.get("last_choice", "")
    if last_choice:
        last_choice_text = f"玩家上一轮选择了选项 {last_choice}。请基于此选择继续故事。"
    else:
        last_choice_text = "这是故事的开始，没有上一轮选择。"

    # ── Interpolate user prompt ────────────────────────────────
    user_raw = template.get("user", "")
    user_prompt = (
        user_raw
        .replace("{{WORLD}}", json.dumps(world_pack, ensure_ascii=False, indent=2))
        .replace("{{STATE_JSON}}", json.dumps(session_state, ensure_ascii=False, indent=2))
        .replace("{{ENGINE_RULES}}", json.dumps(engine_config, ensure_ascii=False, indent=2))
        .replace("{{FORCE_EVENT_PROMPT}}", force_prompt)
        .replace("{{LAST_CHOICE}}", last_choice_text)
        .replace("{{CHARACTERS_CONTEXT}}", characters_context)
        .replace("{{RELATIONSHIP_SYSTEM}}", relationship_context)
        .replace("{{MEMORY_CONTEXT}}", memory_context)
        .replace("{{TIER_CONTEXT}}", tier_context)
        .replace("{{FACTION_CONTEXT}}", faction_attitude_context)
    )

    logger.info("Prompt built — force_event=%s last_choice=%s", force_triggered, last_choice or "none")
    return system_prompt, user_prompt


def _detect_force_event(state: dict) -> tuple[bool, str]:
    """
    Check the three force-event triggers from the spec:

      1. Same scene ≥ 3 turns
      2. Same status ≥ 2 turns  (stagnation)
      3. Interaction stagnation ≥ 2 turns

    Returns (triggered: bool, reason: str).
    """
    reasons: list[str] = []

    history: list = state.get("history", [])
    current_scene = state.get("scene", "")
    current_status = state.get("status", "SETUP")

    # ── Same-scene detection ───────────────────────────────────
    same_scene_count = 1  # current turn counts
    for entry in reversed(history):
        if entry.get("scene") == current_scene:
            same_scene_count += 1
        else:
            break

    if same_scene_count >= config.MAX_TURNS_SAME_SCENE:
        reasons.append(f"同场景已达 {same_scene_count} 轮（阈值 {config.MAX_TURNS_SAME_SCENE}）")

    # ── Same-status detection ──────────────────────────────────
    same_status_count = 1
    for entry in reversed(history):
        if entry.get("status") == current_status:
            same_status_count += 1
        else:
            break

    if same_status_count >= config.MAX_TURNS_SAME_STATUS:
        reasons.append(f"状态 {current_status} 已持续 {same_status_count} 轮（阈值 {config.MAX_TURNS_SAME_STATUS}）")

    # ── Interaction stagnation detection ───────────────────────
    chars: dict = state.get("characters", {})
    levels = [c.get("level", "L0") for c in chars.values()]
    # Convert to ordinal for comparison
    level_idx = _min_level_index(levels)

    stagnant_count = 0
    for entry in reversed(history):
        hist_chars: dict = entry.get("characters", {})
        hist_levels = [c.get("level", "L0") for c in hist_chars.values()]
        if _min_level_index(hist_levels) >= level_idx:
            stagnant_count += 1
        else:
            break

    if stagnant_count >= config.MAX_TURNS_INTERACTION_STAGNANT:
        reasons.append(f"互动等级停滞已达 {stagnant_count} 轮（阈值 {config.MAX_TURNS_INTERACTION_STAGNANT}）")

    if reasons:
        return True, "；".join(reasons)
    return False, ""


def _min_level_index(levels: list[str]) -> int:
    """Convert a list of interaction level strings to the minimum ordinal."""
    try:
        return min(config.INTERACTION_LEVELS.index(lv) for lv in levels)
    except ValueError:
        return 0
