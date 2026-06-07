"""
builder.py — Prompt constructor
=================================
Reads world-pack, session state, engine config, and the prompt
template, then interpolates everything into the final system + user
messages sent to DeepSeek.
"""

import logging

import config
from engine import io_utils
from engine.memory import load_memory
from engine.memory_layers import (
    build_hot_context,
    build_long_term_memory,
    build_recent_summaries,
    load_world_summary_text,
)
from engine.prompt_compact import (
    compact_engine_rules,
    compact_world_for_prompt,
)

logger = logging.getLogger(__name__)


def _player_choice_prompt(choice: str | None, session_state: dict) -> str:
    """Build LAST_CHOICE text; *choice* is what the player just picked this turn."""
    if not choice:
        return "这是故事的开始，没有上一轮选择。"

    history = session_state.get("history", [])
    prev_options = history[-1].get("options", []) if history else []
    letter = choice.strip().upper()
    count = config.OPTION_COUNT
    choice_map = {chr(65 + i): i for i in range(count)}

    if letter in choice_map and prev_options:
        idx = choice_map[letter]
        if 0 <= idx < len(prev_options):
            base = (
                f"玩家本轮选择了选项 {letter}：{prev_options[idx]}\n"
                "请在本轮 story 中直接写出该选择的行动与后果，不得推迟到下一轮。"
            )
            return base + config.adult_choice_execution_hint(prev_options[idx])
        return (
            f"玩家本轮选择了选项 {letter}。\n"
            "请在本轮 story 中直接写出该选择的行动与后果，不得推迟到下一轮。"
        )

    custom = choice.strip()
    return (
        f"玩家本轮自定义行动：{custom}\n"
        "请在本轮 story 中直接写出该行动与后果，不得推迟到下一轮。"
        + config.adult_choice_execution_hint(custom)
    )


def build_prompt(current_choice: str | None = None) -> tuple[str, str]:
    """
    Build the (system_prompt, user_prompt) tuple for the current turn.

    Steps:
      1. Read YAML data files.
      2. Check force-event triggers.
      3. Interpolate the prompt template.
    """
    config.reload_story_length()
    config.reload_max_tokens()
    config.reload_context_settings()
    config.reload_app_behavior()
    config.ensure_story_length_context_sync()

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
            stat_labels = "、".join(
                (s.get("label") or s.get("key") or "维度")
                for s in stats
                if isinstance(s, dict)
            )
            if stat_labels:
                custom_rules_text += f"【专属追踪维度】本故事追踪以下维度：{stat_labels}。在故事中自然体现这些维度的变化。\n"
        if stages:
            stage_chain = " → ".join(stages)
            custom_rules_text += f"【关系阶段】角色关系阶段为：{stage_chain}。重要事件推进阶段变化。\n"

    # ── Main goal ──────────────────────────────────────────────
    world_data = world_pack.get("world", {})
    main_goal = world_data.get("main_goal", "")
    if not main_goal:
        main_goal = "推进剧情发展，探索角色关系"

    # ── Characters context (active + main only for token budget) ─
    characters_list = world_data.get("characters", [])
    characters_context = ""
    session_chars = session_state.get("characters", {})
    active_names: set[str] = set()
    for _key, ch in session_chars.items():
        if isinstance(ch, dict) and ch.get("name"):
            active_names.add(str(ch["name"]))
    if characters_list:
        lines = ["【角色信息 — 当前相关】"]
        for ch in characters_list:
            name = ch.get("name", "?")
            is_main = ch.get("is_main", False)
            if not is_main and active_names and name not in active_names:
                # Include name-only for inactive NPCs when force event
                if not force_triggered:
                    continue
            role_tags = ch.get("role_tags", [])
            role_str = " / ".join(role_tags) if role_tags else ""
            personality_tags = ch.get("personality_tags", [])
            pers_str = "、".join(personality_tags) if personality_tags else ""
            appearance = ch.get("appearance", "")
            goal = ch.get("goal", "")
            parts = [f"{name}（{'⭐主角' if is_main else '👤NPC'}）"]
            if role_str:
                parts.append(f"身份：{role_str}")
            if appearance and (is_main or name in active_names):
                parts.append(f"外貌：{_clip_field(appearance, 80)}")
            if pers_str:
                parts.append(f"性格：{pers_str}")
            if goal and is_main:
                parts.append(f"目标：{_clip_field(goal, 80)}")
            lines.append("  " + " | ".join(parts))
        if len(lines) > 1:
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
    target_len = config.STORY_LENGTH
    min_len = config.min_story_length_for_target(target_len)
    max_len = config.max_story_length_for_target(target_len)
    system_raw = template.get("system", "")
    system_prompt = (
        system_raw
        .replace("{{FORCE_EVENT_NOTICE}}", force_notice)
        .replace("{{STORY_LENGTH}}", str(target_len))
        .replace("{{STORY_LENGTH_MIN}}", str(min_len))
        .replace("{{STORY_LENGTH_MAX}}", str(max_len))
        .replace("{{AI_BEHAVIOR_RULES}}", config.ai_behavior_rules_text())
        .replace("{{OPTION_COUNT}}", str(config.OPTION_COUNT))
        .replace("{{ADULT_OPTIONS_HINT}}", config.adult_options_hint_text())
        .replace("{{CUSTOM_RULES}}", custom_rules_text)
        .replace("{{MAIN_GOAL}}", main_goal)
    )

    # ── Memory layers (V2) ─────────────────────────────────────
    memory = load_memory()
    long_term = build_long_term_memory(memory, session_state)
    recent_summaries = build_recent_summaries(count=2)
    hot_context = build_hot_context(session_state, memory)

    # ── Player choice for THIS generation ───────────────────────
    last_choice_text = _player_choice_prompt(current_choice, session_state)

    world_text = load_world_summary_text()
    if not world_text:
        world_text = compact_world_for_prompt(world_pack)

    # ── Interpolate user prompt ────────────────────────────────
    user_raw = template.get("user", "")
    user_prompt = (
        user_raw
        .replace("{{WORLD}}", world_text)
        .replace("{{LONG_TERM_MEMORY}}", long_term)
        .replace("{{RECENT_SUMMARIES}}", recent_summaries)
        .replace("{{HOT_CONTEXT}}", hot_context)
        .replace("{{ENGINE_RULES}}", compact_engine_rules(engine_config))
        .replace("{{FORCE_EVENT_PROMPT}}", force_prompt)
        .replace("{{LAST_CHOICE}}", last_choice_text)
        .replace("{{CHARACTERS_CONTEXT}}", characters_context)
        .replace("{{RELATIONSHIP_SYSTEM}}", relationship_context)
        .replace("{{STORY_LENGTH}}", str(target_len))
        .replace("{{STORY_LENGTH_MIN}}", str(min_len))
        .replace("{{STORY_LENGTH_MAX}}", str(max_len))
        .replace("{{OPTION_COUNT}}", str(config.OPTION_COUNT))
        .replace("{{ADULT_TASK_HINT}}", config.adult_task_hint_text())
    )

    user_prompt = _apply_prompt_budget(user_prompt)

    # ── Estimate token usage and warn ───────────────────────────
    _warn_if_approaching_limit(system_prompt, user_prompt)

    logger.info(
        "Prompt built — force_event=%s current_choice=%s story_length=%d max_tokens=%d "
        "hot_turns=%d long_term_chars=%d",
        force_triggered,
        current_choice or "none",
        target_len,
        config.MAX_TOKENS,
        config.HOT_CONTEXT_TURNS,
        len(long_term),
    )
    return system_prompt, user_prompt


def _clip_field(text: str, limit: int) -> str:
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _apply_prompt_budget(user_prompt: str) -> str:
    """Trim user prompt if estimated tokens exceed V2 budget."""
    budget = config.PROMPT_TOKEN_BUDGET
    est = int(len(user_prompt) * 0.6)
    if est <= budget:
        return user_prompt
    ratio = budget / max(est, 1)
    trimmed = user_prompt[: int(len(user_prompt) * ratio * 0.95)]
    logger.warning(
        "Prompt trimmed for budget: ~%d → ~%d tokens (cap=%d)",
        est,
        int(len(trimmed) * 0.6),
        budget,
    )
    return trimmed + "\n…（上下文已按预算裁剪，请依据以上信息续写）"


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

    thresholds = config.force_event_thresholds()

    if same_scene_count >= thresholds["same_scene"]:
        reasons.append(f"同场景已达 {same_scene_count} 轮（阈值 {thresholds['same_scene']}）")

    # ── Same-status detection ──────────────────────────────────
    same_status_count = 1
    for entry in reversed(history):
        if entry.get("status") == current_status:
            same_status_count += 1
        else:
            break

    if same_status_count >= thresholds["same_status"]:
        reasons.append(f"状态 {current_status} 已持续 {same_status_count} 轮（阈值 {thresholds['same_status']}）")

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

    if stagnant_count >= thresholds["interaction"]:
        reasons.append(f"互动等级停滞已达 {stagnant_count} 轮（阈值 {thresholds['interaction']}）")

    if reasons:
        return True, "；".join(reasons)
    return False, ""


def _min_level_index(levels: list[str]) -> int:
    """Convert a list of interaction level strings to the minimum ordinal."""
    try:
        return min(config.INTERACTION_LEVELS.index(lv) for lv in levels)
    except ValueError:
        return 0


def _warn_if_approaching_limit(system_prompt: str, user_prompt: str) -> None:
    """Estimate total prompt tokens and warn if approaching context limit."""
    total_chars = len(system_prompt) + len(user_prompt)
    estimated_tokens = int(total_chars * 0.6)

    ctx_limit = config.DEEPSEEK_CONTEXT_TOKENS
    v2_budget = config.PROMPT_TOKEN_BUDGET
    danger_threshold = int(ctx_limit * 0.9)

    if estimated_tokens > v2_budget:
        logger.info(
            "Prompt ~%d tokens (V2 target ≤%d)",
            estimated_tokens,
            v2_budget,
        )
    if estimated_tokens > danger_threshold:
        logger.warning(
            "⚠️ Prompt ~%d tokens — approaching %dK context limit.",
            estimated_tokens,
            ctx_limit // 1000,
        )
