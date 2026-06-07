"""Engine settings persistence and Obsidian export."""
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
    save_temperature,
    reload_temperature,
    save_top_p,
    reload_top_p,
    save_stream,
    reload_stream,
    save_context_settings,
    reload_context_settings,
)

router = APIRouter(tags=["settings"])


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
    limits = config.story_length_limits()
    return {
        **limits,
        "story_length": config.STORY_LENGTH,
        "max_tokens": config.MAX_TOKENS,
        "matched_max_tokens": config.tokens_for_story_length(config.STORY_LENGTH),
        "temperature": config.TEMPERATURE,
        "top_p": config.TOP_P,
        "compress_threshold": config.COMPRESS_THRESHOLD,
        "api_limits": config.api_limits(),
    }


def apply_game_gen_settings(
    *,
    story_length: int | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    compress_threshold: int | None = None,
) -> dict:
    """Update generation quick settings (Game page)."""
    if story_length is not None:
        save_story_length(clamp_story_length(story_length))
        reload_story_length()
        reload_max_tokens()
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
    return game_settings_payload()


def apply_engine_settings(
    api_key: str = "",
    model: str = "deepseek-chat",
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
    if model in AVAILABLE_MODELS:
        save_model(model)
        reload_model()
    if story_length is not None:
        save_story_length(clamp_story_length(story_length))
        reload_story_length()
        reload_max_tokens()
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
