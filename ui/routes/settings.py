"""Engine settings persistence and Obsidian export."""
import logging

from fastapi import APIRouter
from fastapi.responses import FileResponse

import config
from config import (
    save_api_key,
    clear_api_key,
    reload_api_key,
    save_model,
    reload_model,
    AVAILABLE_MODELS,
    save_story_length,
    reload_story_length,
    clamp_story_length,
    save_max_tokens,
    reload_max_tokens,
    tokens_for_story_length,
    compress_threshold_for_story_length,
    ensure_story_length_token_sync,
    ensure_story_length_context_sync,
    save_option_count,
    reload_option_count,
    save_narrative_pov,
    reload_narrative_pov,
    save_style_preference,
    reload_style_preference,
    save_repetition_check,
    reload_repetition_check,
    save_adult_mode,
    reload_adult_mode,
    is_adult_unlocked,
    reload_adult_unlock_key,
    save_adult_unlock_key,
    save_adult_profile,
    reload_adult_profile,
    save_adult_theme,
    reload_adult_theme,
    save_visual_theme,
    reload_visual_theme,
    save_expression_style,
    reload_expression_style,
    save_content_weights,
    reload_content_weights,
    EXPRESSION_STYLE_OPTIONS,
    EXPRESSION_STYLE_LABELS,
    PRESET_WEIGHTS,
    ADULT_PROFILE_OPTIONS,
    ADULT_PROFILE_LABELS,
    ADULT_PROFILE_DESCRIPTIONS,
    ADULT_THEME_OPTIONS,
    ADULT_THEME_LABELS,
    VISUAL_THEME_OPTIONS,
    VISUAL_THEME_LABELS,
    save_auto_save_interval,
    reload_auto_save_interval,
    save_max_save_slots,
    reload_max_save_slots,
    save_export_format,
    reload_export_format,
    save_auto_export,
    reload_auto_export,
    reload_app_behavior,
    save_temperature,
    reload_temperature,
    save_top_p,
    reload_top_p,
    save_stream,
    reload_stream,
    save_context_settings,
    reload_context_settings,
)
from engine.adult_unlock import mask_unlock_key

router = APIRouter(tags=["settings"])
gen_settings_logger = logging.getLogger("gen_settings")

# Set by apply_game_gen_settings; consumed on next step() for correlated logging.
_pending_gen_settings_note: str | None = None


def pop_pending_gen_settings_note() -> str | None:
    global _pending_gen_settings_note
    note = _pending_gen_settings_note
    _pending_gen_settings_note = None
    return note


def _gen_settings_snapshot() -> dict:
    return {
        "story_length": config.STORY_LENGTH,
        "max_tokens": config.MAX_TOKENS,
        "matched_max_tokens": config.tokens_for_story_length(config.STORY_LENGTH),
        "compress_threshold": config.COMPRESS_THRESHOLD,
        "matched_compress_threshold": config.compress_threshold_for_story_length(config.STORY_LENGTH),
        "temperature": config.TEMPERATURE,
        "top_p": config.TOP_P,
        "max_context_messages": config.MAX_CONTEXT_MESSAGES,
        "auto_compress": config.AUTO_COMPRESS,
    }


def _format_gen_settings_diff(before: dict, after: dict) -> str:
    parts: list[str] = []
    labels = {
        "story_length": "目标字数",
        "max_tokens": "最大Token",
        "compress_threshold": "压缩阈值",
        "temperature": "温度",
        "top_p": "TopP",
        "max_context_messages": "上下文消息上限",
        "auto_compress": "自动压缩",
    }
    for key, label in labels.items():
        if before.get(key) != after.get(key):
            parts.append(f"{label} {before.get(key)}→{after.get(key)}")
    return " | ".join(parts) if parts else "（无变更）"


def log_gen_settings_change(before: dict, after: dict, *, source: str) -> None:
    diff = _format_gen_settings_diff(before, after)
    if diff == "（无变更）":
        return
    global _pending_gen_settings_note
    _pending_gen_settings_note = diff
    gen_settings_logger.info(
        "⚙️ 快捷设置已修改 [%s] %s | 生效于下一轮生成",
        source,
        diff,
    )
    gen_settings_logger.info(
        "   当前快照: 目标字数=%d 最大Token=%d 压缩阈值=%d 温度=%.2f TopP=%.2f",
        after["story_length"],
        after["max_tokens"],
        after["compress_threshold"],
        after["temperature"],
        after["top_p"],
    )


def mask_api_key(key: str) -> str:
    if not key:
        return ""
    return key[:8] + "…" + key[-4:] if len(key) > 12 else "***"


def settings_payload() -> dict:
    """Current engine/API settings for the React settings page."""
    key = config._read_stored_api_key()
    return {
        "configured": bool(key),
        "api_key_masked": mask_api_key(key),
        "model": config.DEEPSEEK_MODEL,
        "models": dict(AVAILABLE_MODELS),
        "story_length": config.STORY_LENGTH,
        "max_tokens": config.MAX_TOKENS,
        "matched_max_tokens": config.tokens_for_story_length(config.STORY_LENGTH),
        "api_limits": config.api_limits(),
        "temperature": config.TEMPERATURE,
        "top_p": config.TOP_P,
        "stream": config.STREAM,
        "max_context_messages": config.MAX_CONTEXT_MESSAGES,
        "auto_compress": config.AUTO_COMPRESS,
        "compress_threshold": config.COMPRESS_THRESHOLD,
    }


def game_settings_payload() -> dict:
    """Generation quick settings for the Game page."""
    reload_story_length()
    reload_max_tokens()
    reload_context_settings()
    reload_app_behavior()
    ensure_story_length_context_sync()
    limits = config.story_length_limits()
    return {
        **limits,
        "story_length": config.STORY_LENGTH,
        "max_tokens": config.MAX_TOKENS,
        "matched_max_tokens": config.tokens_for_story_length(config.STORY_LENGTH),
        "compress_threshold": config.COMPRESS_THRESHOLD,
        "matched_compress_threshold": config.compress_threshold_for_story_length(config.STORY_LENGTH),
        "auto_compress": config.AUTO_COMPRESS,
        "max_context_messages": config.MAX_CONTEXT_MESSAGES,
        "temperature": config.TEMPERATURE,
        "top_p": config.TOP_P,
        "option_count": config.OPTION_COUNT,
        "narrative_pov": config.NARRATIVE_POV,
        "style_preference": config.STYLE_PREFERENCE,
        "repetition_check": config.REPETITION_CHECK,
        "adult_mode": config.ADULT_MODE,
        "adult_unlocked": is_adult_unlocked(),
        "adult_unlock_key_masked": (
            mask_unlock_key(reload_adult_unlock_key()) if is_adult_unlocked() else ""
        ),
        "adult_profile": config.ADULT_PROFILE,
        "adult_profile_options": ADULT_PROFILE_OPTIONS,
        "adult_profile_labels": ADULT_PROFILE_LABELS,
        "adult_profile_descriptions": ADULT_PROFILE_DESCRIPTIONS,
        "adult_theme": config.ADULT_THEME,
        "adult_theme_options": ADULT_THEME_OPTIONS,
        "adult_theme_labels": ADULT_THEME_LABELS,
        "visual_theme": config.VISUAL_THEME,
        "visual_theme_options": VISUAL_THEME_OPTIONS,
        "visual_theme_labels": VISUAL_THEME_LABELS,
        "expression_style": config.EXPRESSION_STYLE,
        "expression_style_options": EXPRESSION_STYLE_OPTIONS,
        "expression_style_labels": EXPRESSION_STYLE_LABELS,
        "content_weights": config.CONTENT_WEIGHTS,
        "preset_weights": PRESET_WEIGHTS,
        "api_limits": config.api_limits(),
    }


def apply_game_gen_settings(
    *,
    story_length: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    compress_threshold: int | None = None,
    option_count: int | None = None,
    narrative_pov: str | None = None,
    style_preference: str | None = None,
    repetition_check: str | None = None,
    adult_mode: bool | None = None,
    adult_unlock_key: str | None = None,
    adult_profile: str | None = None,
    adult_theme: str | None = None,
    visual_theme: str | None = None,
    expression_style: str | None = None,
    content_weights: dict | None = None,
) -> dict:
    """Update generation quick settings (Game page)."""
    before = _gen_settings_snapshot()
    if story_length is not None:
        save_story_length(clamp_story_length(story_length))
        reload_story_length()
        reload_max_tokens()
        reload_context_settings()
        ensure_story_length_token_sync()
    if temperature is not None:
        save_temperature(max(0.1, min(config.DEEPSEEK_MAX_TEMPERATURE, temperature)))
        reload_temperature()
    if top_p is not None:
        save_top_p(max(0.0, min(config.DEEPSEEK_MAX_TOP_P, top_p)))
        reload_top_p()
    if compress_threshold is not None:
        save_context_settings(
            config.MAX_CONTEXT_MESSAGES,
            config.AUTO_COMPRESS,
            max(500, min(config.DEEPSEEK_CONTEXT_TOKENS, compress_threshold)),
        )
        reload_context_settings()
    if option_count is not None:
        save_option_count(option_count)
    if narrative_pov is not None:
        save_narrative_pov(narrative_pov)
    if style_preference is not None:
        save_style_preference(style_preference)
    if repetition_check is not None:
        save_repetition_check(repetition_check)
    if adult_unlock_key is not None:
        save_adult_unlock_key(adult_unlock_key)
    adult_mode_changed = False
    if adult_mode is not None:
        prev_adult = config.ADULT_MODE
        save_adult_mode(adult_mode)
        adult_mode_changed = prev_adult != bool(adult_mode)
    if adult_profile is not None:
        save_adult_profile(adult_profile)
    if adult_theme is not None:
        save_adult_theme(adult_theme)
    if visual_theme is not None:
        save_visual_theme(visual_theme)
    if expression_style is not None:
        save_expression_style(expression_style)
    if content_weights is not None:
        save_content_weights(content_weights)
    if any(x is not None for x in (option_count, narrative_pov, style_preference, repetition_check,
                                    adult_unlock_key, adult_mode, adult_profile, adult_theme, visual_theme,
                                    expression_style, content_weights)):
        reload_app_behavior()
    ensure_story_length_context_sync(force_compress=story_length is not None)
    after = _gen_settings_snapshot()
    log_gen_settings_change(before, after, source="game-settings")
    payload = game_settings_payload()
    if adult_mode_changed:
        from engine.regenerate_options import regenerate_current_turn_options

        regen = regenerate_current_turn_options()
        payload["options_regenerated"] = bool(regen.get("ok"))
        if regen.get("ok") and regen.get("options"):
            payload["options"] = regen["options"]
        elif regen.get("error"):
            payload["options_regen_error"] = regen["error"]
    return payload


def app_settings_payload() -> dict:
    """Save/export settings (Settings page — not duplicated in Game quick panel)."""
    reload_app_behavior()
    return {
        "auto_save_interval": config.AUTO_SAVE_INTERVAL,
        "max_save_slots": config.MAX_SAVE_SLOTS,
        "export_format": config.EXPORT_FORMAT,
        "auto_export": config.AUTO_EXPORT,
        "save_slots": config.all_save_slots(),
    }


def apply_app_settings(
    *,
    auto_save_interval: int | None = None,
    max_save_slots: int | None = None,
    export_format: str | None = None,
    auto_export: str | None = None,
) -> dict:
    """Persist data/save settings from the Settings page."""
    if auto_save_interval is not None:
        save_auto_save_interval(auto_save_interval)
    if max_save_slots is not None:
        save_max_save_slots(max_save_slots)
    if export_format is not None:
        save_export_format(export_format)
    if auto_export is not None:
        save_auto_export(auto_export)
    reload_app_behavior()
    return app_settings_payload()


def apply_engine_settings(
    api_key: str = "",
    model: str | None = None,
    story_length: int | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    stream: int | None = None,
    max_context_messages: int | None = None,
    auto_compress: int | None = None,
    compress_threshold: int | None = None,
) -> dict:
    """Persist engine settings and return updated payload."""
    key = api_key.strip()
    if key:
        try:
            save_api_key(key)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        reload_api_key()
    if model is not None and model in AVAILABLE_MODELS:
        save_model(model)
        reload_model()
    if story_length is not None:
        save_story_length(clamp_story_length(story_length))
        reload_story_length()
        reload_max_tokens()
        reload_context_settings()
        ensure_story_length_token_sync()
    elif max_tokens is not None:
        save_max_tokens(config.cap_output_tokens(max_tokens))
        reload_max_tokens()
    if temperature is not None:
        save_temperature(max(0.1, min(config.DEEPSEEK_MAX_TEMPERATURE, temperature)))
        reload_temperature()
    if top_p is not None:
        save_top_p(max(0.0, min(config.DEEPSEEK_MAX_TOP_P, top_p)))
        reload_top_p()
    if stream is not None:
        save_stream(bool(stream))
        reload_stream()
    if any(x is not None for x in (max_context_messages, auto_compress, compress_threshold)):
        msgs = max_context_messages if max_context_messages is not None else config.MAX_CONTEXT_MESSAGES
        ac = auto_compress if auto_compress is not None else config.AUTO_COMPRESS
        ct = compress_threshold if compress_threshold is not None else config.COMPRESS_THRESHOLD
        save_context_settings(
            max(4, min(100, msgs)),
            bool(ac),
            max(500, min(config.DEEPSEEK_CONTEXT_TOKENS, ct)),
        )
        reload_context_settings()
    return settings_payload()


@router.get("/export")
async def export_obsidian():
    """Export the full story as Obsidian Markdown and return it for download."""
    from ui.obsidian_export import export_full_story

    path = export_full_story()
    return FileResponse(
        path=path,
        media_type="text/markdown",
        filename="星痕纪元_完整叙事.md",
    )
