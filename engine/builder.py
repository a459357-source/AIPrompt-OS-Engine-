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
from engine.character_brain import (
    build_character_brain_context,
    ensure_personalities,
    resolve_brain_character_names,
)
from engine.experience.prompt_strategy import get_prompt_strategy
from engine.memory import load_memory
from engine.memory_layers import (
    build_hot_context,
    build_long_term_memory,
    build_recent_summaries,
    load_world_summary_text,
)
from engine.plot_director import build_director_advice, ensure_plot_state
from engine.objective_system import build_objectives_context, ensure_objectives
from engine.prompt_compact import (
    compact_engine_rules,
    compact_world_for_prompt,
)

logger = logging.getLogger(__name__)


def _player_choice_prompt(
    choice: str | None,
    session_state: dict,
    *,
    strategy=None,
) -> str:
    """Build LAST_CHOICE text; *choice* is what the player just picked this turn."""
    if strategy is None:
        strategy = get_prompt_strategy()

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
            return base + strategy.get_choice_execution_hint(prev_options[idx])
        return (
            f"玩家本轮选择了选项 {letter}。\n"
            "请在本轮 story 中直接写出该选择的行动与后果，不得推迟到下一轮。"
        )

    custom = choice.strip()
    return (
        f"玩家本轮自定义行动：{custom}\n"
        "请在本轮 story 中直接写出该行动与后果，不得推迟到下一轮。"
        + strategy.get_choice_execution_hint(custom)
    )


def build_prompt(current_choice: str | None = None) -> tuple[str, str]:
    """
    Build the (system_prompt, user_prompt) tuple for the current turn.

    Uses unified Base Prompt + Mode Context (PromptStrategy).
    Legacy extreme yaml available via PROMPTOS_USE_LEGACY_EXTREME_TEMPLATE=1.
    """
    config.reload_story_length()
    config.reload_max_tokens()
    config.reload_context_settings()
    config.reload_app_behavior()
    config.ensure_story_length_context_sync()

    if config.use_legacy_extreme_template_file() and config.is_extreme_tier():
        return _build_prompt_legacy_extreme(current_choice)

    return _build_prompt_unified(current_choice)


def _build_prompt_unified(current_choice: str | None) -> tuple[str, str]:
    world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
    session_state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    engine_config = io_utils.read_yaml(config.ENGINE_CONFIG_PATH)
    template = io_utils.read_yaml(config.PROMPT_TEMPLATE_PATH)
    strategy = get_prompt_strategy()
    mode_ctx = strategy.build_mode_context(
        world_pack=world_pack,
        session_state=session_state,
        engine_config=engine_config,
    )

    force_notice, force_prompt = _force_event_blocks(session_state)
    force_triggered = force_notice != "当前无强制事件。正常叙事节奏。"
    custom_rules_text = _custom_rules_text(world_pack)
    main_goal = _main_goal_text(world_pack) + mode_ctx.main_goal_suffix

    target_len = config.STORY_LENGTH
    min_len = config.min_story_length_for_target(target_len)
    max_len = config.max_story_length_for_target(target_len)
    char_a = config.sample_char_a_name(world_pack, session_state)

    system_raw = template.get("system", "")
    system_prompt = (
        system_raw
        .replace("{{MODE_CONTEXT_SYSTEM}}", mode_ctx.system_block)
        .replace("{{NARRATIVE_STYLE_LINE}}", mode_ctx.narrative_style_line)
        .replace("{{FORCE_EVENT_NOTICE}}", force_notice)
        .replace("{{STORY_LENGTH}}", str(target_len))
        .replace("{{STORY_LENGTH_MIN}}", str(min_len))
        .replace("{{STORY_LENGTH_MAX}}", str(max_len))
        .replace("{{BEHAVIOR_RULES}}", mode_ctx.behavior_rules)
        .replace("{{CHAR_A}}", char_a)
        .replace("{{OPTION_COUNT}}", str(config.OPTION_COUNT))
        .replace("{{OPTIONS_SCHEMA_HINT}}", mode_ctx.options_hint)
        .replace("{{CUSTOM_RULES}}", custom_rules_text)
        .replace("{{MAIN_GOAL}}", main_goal)
    )

    memory = load_memory()
    ensure_personalities(memory, world_pack)
    brain_names = resolve_brain_character_names(session_state, memory, world_pack)
    character_brain = ""
    if config.CHARACTER_BRAIN_ENABLED:
        character_brain = build_character_brain_context(
            brain_names, memory, world_pack, session_state,
        )

    long_term = build_long_term_memory(memory, session_state)
    recent_summaries = build_recent_summaries(count=2)
    hot_context = build_hot_context(session_state, memory)
    last_choice_text = _player_choice_prompt(current_choice, session_state, strategy=strategy)

    world_text = load_world_summary_text(session_state=session_state)
    if not world_text:
        world_text = compact_world_for_prompt(world_pack)

    director_advice = ""
    if config.PLOT_DIRECTOR_ENABLED:
        plot_state = ensure_plot_state(world_pack)
        director_advice = build_director_advice(plot_state, session_state)

    objectives_context = ""
    if config.OBJECTIVE_SYSTEM_ENABLED:
        ensure_objectives(session_state, world_pack)
        objectives_context = build_objectives_context(session_state, world_pack)
        if objectives_context:
            objectives_context = objectives_context + "\n"

    characters_context = _characters_context(world_pack, session_state, force_triggered)
    relationship_context = _relationship_context(world_pack)
    rel_memory_context = _relationship_memory_context(session_state, world_pack, brain_names)
    rel_dynamics_context = _relationship_dynamics_context(session_state, world_pack, brain_names)
    rel_event_candidates = _relationship_event_candidates(session_state, world_pack)
    if rel_event_candidates:
        force_prompt = (
            f"{force_prompt}\n{rel_event_candidates}".strip()
            if force_prompt
            else rel_event_candidates
        )

    user_raw = template.get("user", "")
    user_prompt = (
        user_raw
        .replace("{{WORLD}}", world_text)
        .replace("{{LONG_TERM_MEMORY}}", long_term)
        .replace("{{RECENT_SUMMARIES}}", recent_summaries)
        .replace("{{HOT_CONTEXT}}", hot_context)
        .replace("{{OBJECTIVES_CONTEXT}}", objectives_context)
        .replace("{{DIRECTOR_ADVICE}}", director_advice)
        .replace("{{MODE_CONTEXT_USER}}", mode_ctx.user_block)
        .replace("{{ENGINE_RULES}}", compact_engine_rules(engine_config))
        .replace("{{FORCE_EVENT_PROMPT}}", force_prompt)
        .replace("{{RELATIONSHIP_MEMORY_CONTEXT}}", rel_memory_context)
        .replace("{{RELATIONSHIP_DYNAMICS_CONTEXT}}", rel_dynamics_context)
        .replace("{{LAST_CHOICE}}", last_choice_text)
        .replace("{{CHARACTERS_CONTEXT}}", characters_context)
        .replace("{{CHARACTER_BRAIN}}", character_brain)
        .replace("{{RELATIONSHIP_SYSTEM}}", relationship_context)
        .replace("{{STORY_LENGTH}}", str(target_len))
        .replace("{{STORY_LENGTH_MIN}}", str(min_len))
        .replace("{{STORY_LENGTH_MAX}}", str(max_len))
        .replace("{{OPTION_COUNT}}", str(config.OPTION_COUNT))
        .replace("{{TASK_HINT}}", mode_ctx.task_hint)
    )

    user_prompt = _apply_prompt_budget(user_prompt)
    _warn_if_approaching_limit(system_prompt, user_prompt)

    logger.info(
        "Prompt built — template=unified force_event=%s current_choice=%s story_length=%d max_tokens=%d "
        "hot_turns=%d long_term_chars=%d mode=%s tier=%s",
        force_notice != "当前无强制事件。正常叙事节奏。",
        current_choice or "none",
        target_len,
        config.MAX_TOKENS,
        config.HOT_CONTEXT_TURNS,
        len(long_term),
        config.get_experience_mode(),
        strategy.get_intensity_tier(),
    )
    return system_prompt, user_prompt


def _build_prompt_legacy_extreme(current_choice: str | None) -> tuple[str, str]:
    """Emergency rollback path using prompt_template_adult_extreme.yaml."""
    world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
    session_state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    engine_config = io_utils.read_yaml(config.ENGINE_CONFIG_PATH)
    template_path = config.resolve_prompt_template_path()
    template = io_utils.read_yaml(template_path)

    force_notice, force_prompt = _force_event_blocks(session_state)
    force_triggered = force_notice != "当前无强制事件。正常叙事节奏。"
    custom_rules_text = _custom_rules_text(world_pack)
    main_goal = _main_goal_text(world_pack) + config.adult_main_goal_suffix()

    target_len = config.STORY_LENGTH
    min_len = config.min_story_length_for_target(target_len)
    max_len = config.max_story_length_for_target(target_len)
    vocab_domain = config.vocabulary_domain_text(world_pack)
    norm_block = config.normalized_intimacy_block(world_pack)
    char_a = config.sample_char_a_name(world_pack, session_state)

    behavior_rules = config.adult_extreme_behavior_rules_text(
        vocabulary_domain=vocab_domain,
        normalized_block=norm_block,
    )
    system_raw = template.get("system", "")
    system_prompt = (
        system_raw
        .replace("{{ADULT_SYSTEM_OVERRIDE}}", config.adult_system_override_text())
        .replace("{{FORCE_EVENT_NOTICE}}", force_notice)
        .replace("{{STORY_LENGTH}}", str(target_len))
        .replace("{{STORY_LENGTH_MIN}}", str(min_len))
        .replace("{{STORY_LENGTH_MAX}}", str(max_len))
        .replace("{{ADULT_EXTREME_BEHAVIOR_RULES}}", behavior_rules)
        .replace("{{ADULT_EXTREME_CONTENT_RULES}}", config.adult_extreme_content_rules_text())
        .replace("{{CHAR_A}}", char_a)
        .replace("{{OPTION_COUNT}}", str(config.OPTION_COUNT))
        .replace("{{ADULT_OPTIONS_HINT}}", config.adult_options_hint_text())
        .replace("{{CUSTOM_RULES}}", custom_rules_text)
        .replace("{{MAIN_GOAL}}", main_goal)
    )

    memory = load_memory()
    ensure_personalities(memory, world_pack)
    brain_names = resolve_brain_character_names(session_state, memory, world_pack)
    character_brain = ""
    if config.CHARACTER_BRAIN_ENABLED:
        character_brain = build_character_brain_context(
            brain_names, memory, world_pack, session_state,
        )

    long_term = build_long_term_memory(memory, session_state)
    recent_summaries = build_recent_summaries(count=2)
    hot_context = build_hot_context(session_state, memory)
    last_choice_text = _player_choice_prompt(current_choice, session_state)

    world_text = load_world_summary_text(session_state=session_state)
    if not world_text:
        world_text = compact_world_for_prompt(world_pack)

    director_advice = ""
    if config.PLOT_DIRECTOR_ENABLED:
        plot_state = ensure_plot_state(world_pack)
        director_advice = build_director_advice(plot_state, session_state)

    rel_memory_context = _relationship_memory_context(session_state, world_pack, brain_names)
    rel_dynamics_context = _relationship_dynamics_context(session_state, world_pack, brain_names)
    rel_event_candidates = _relationship_event_candidates(session_state, world_pack)
    if rel_event_candidates:
        force_prompt = (
            f"{force_prompt}\n{rel_event_candidates}".strip()
            if force_prompt
            else rel_event_candidates
        )

    user_raw = template.get("user", "")
    user_prompt = (
        user_raw
        .replace("{{WORLD}}", world_text)
        .replace("{{LONG_TERM_MEMORY}}", long_term)
        .replace("{{RECENT_SUMMARIES}}", recent_summaries)
        .replace("{{HOT_CONTEXT}}", hot_context)
        .replace("{{DIRECTOR_ADVICE}}", director_advice)
        .replace("{{INTIMACY_ESCALATION_HINT}}", config.intimacy_escalation_hint(session_state))
        .replace("{{ENGINE_RULES}}", compact_engine_rules(engine_config))
        .replace("{{FORCE_EVENT_PROMPT}}", force_prompt)
        .replace("{{RELATIONSHIP_MEMORY_CONTEXT}}", rel_memory_context)
        .replace("{{RELATIONSHIP_DYNAMICS_CONTEXT}}", rel_dynamics_context)
        .replace("{{LAST_CHOICE}}", last_choice_text)
        .replace("{{CHARACTERS_CONTEXT}}", _characters_context(world_pack, session_state, force_triggered))
        .replace("{{CHARACTER_BRAIN}}", character_brain)
        .replace("{{RELATIONSHIP_SYSTEM}}", _relationship_context(world_pack))
        .replace("{{STORY_LENGTH}}", str(target_len))
        .replace("{{STORY_LENGTH_MIN}}", str(min_len))
        .replace("{{STORY_LENGTH_MAX}}", str(max_len))
        .replace("{{OPTION_COUNT}}", str(config.OPTION_COUNT))
        .replace("{{ADULT_TASK_HINT}}", config.adult_task_hint_text())
    )

    user_prompt = _apply_prompt_budget(user_prompt)
    _warn_if_approaching_limit(system_prompt, user_prompt)

    logger.info(
        "Prompt built — template=legacy_extreme force_event=%s current_choice=%s",
        force_notice != "当前无强制事件。正常叙事节奏。",
        current_choice or "none",
    )
    return system_prompt, user_prompt


def _force_event_blocks(session_state: dict) -> tuple[str, str]:
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
    return force_notice, force_prompt


def _custom_rules_text(world_pack: dict) -> str:
    custom = world_pack.get("custom", {})
    custom_rules_text = ""
    if not custom:
        return custom_rules_text
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
    story_prompt = str(custom.get("story_prompt", "")).strip()
    if story_prompt:
        custom_rules_text += f"【故事补充设定 — 仅本故事生效】\n{story_prompt}\n"
    return custom_rules_text


def _main_goal_text(world_pack: dict) -> str:
    world_data = world_pack.get("world", {})
    main_goal = world_data.get("main_goal", "")
    if not main_goal:
        main_goal = "推进剧情发展，探索角色关系"
    return main_goal


def _characters_context(world_pack: dict, session_state: dict, force_triggered: bool) -> str:
    world_data = world_pack.get("world", {})
    characters_list = world_data.get("characters", [])
    session_chars = session_state.get("characters", {})
    active_names: set[str] = set()
    for _key, ch in session_chars.items():
        if isinstance(ch, dict) and ch.get("name"):
            active_names.add(str(ch["name"]))
    if not characters_list:
        return ""
    lines = ["【角色信息 — 当前相关】"]
    for ch in characters_list:
        name = ch.get("name", "?")
        is_main = ch.get("is_main", False)
        if not is_main and active_names and name not in active_names:
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
        return "\n".join(lines)
    return ""


def _relationship_memory_context(
    session_state: dict,
    world_pack: dict,
    brain_names: set[str],
) -> str:
    if not config.RELATIONSHIP_ENGINE_ENABLED:
        return ""
    from engine.relationship_core import ensure_graph
    from engine.relationship_recall import build_prompt_context, ensure_memory_store

    store = ensure_memory_store(None)
    graph = ensure_graph(world_pack, session=session_state)
    return build_prompt_context(
        store, graph, session_state, world_pack, names=brain_names,
    )


def _relationship_dynamics_context(
    session_state: dict,
    world_pack: dict,
    brain_names: set[str],
) -> str:
    if not config.RELATIONSHIP_ENGINE_ENABLED:
        return ""
    from engine.relationship_core import ensure_graph
    from engine.relationship_recall import build_dynamics_prompt_context, ensure_dynamics_store

    dyn = ensure_dynamics_store(None)
    graph = ensure_graph(world_pack, session=session_state)
    return build_dynamics_prompt_context(
        dyn, graph, session_state, world_pack, names=brain_names,
    )


def _relationship_event_candidates(session_state: dict, world_pack: dict) -> str:
    if not config.RELATIONSHIP_ENGINE_ENABLED:
        return ""
    from engine.relationship_core import ensure_graph
    from engine.relationship_event_builder import format_event_candidates_for_director
    from engine.relationship_recall import ensure_dynamics_store, ensure_memory_store

    store = ensure_memory_store(None)
    dyn = ensure_dynamics_store(None)
    graph = ensure_graph(world_pack, session=session_state)
    return format_event_candidates_for_director(
        store, graph, session_state, world_pack, dynamics_store=dyn,
    )


def _relationship_context(world_pack: dict) -> str:
    world_data = world_pack.get("world", {})
    rel_system = world_data.get("relationship_system", {})
    if rel_system:
        stages = rel_system.get("stages", [])
        affection = rel_system.get("affection", 0)
        if stages:
            stage_chain = " → ".join(stages)
            return f"【关系系统】阶段递进：{stage_chain}。初始好感度：{affection}/100。角色关系应随剧情自然推进。"
        return "【关系系统】使用默认7阶段好感度系统（陌生→认识→熟悉→朋友→暧昧→恋人→灵魂伴侣）。"
    return "【关系系统】使用默认好感度系统。"


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

    same_scene_count = 1
    for entry in reversed(history):
        if entry.get("scene") == current_scene:
            same_scene_count += 1
        else:
            break

    thresholds = config.force_event_thresholds()

    if same_scene_count >= thresholds["same_scene"]:
        reasons.append(f"同场景已达 {same_scene_count} 轮（阈值 {thresholds['same_scene']}）")

    same_status_count = 1
    for entry in reversed(history):
        if entry.get("status") == current_status:
            same_status_count += 1
        else:
            break

    if same_status_count >= thresholds["same_status"]:
        reasons.append(f"状态 {current_status} 已持续 {same_status_count} 轮（阈值 {thresholds['same_status']}）")

    chars: dict = state.get("characters", {})
    levels = [c.get("level", "L0") for c in chars.values()]
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
