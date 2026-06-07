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
        "temperature": config.TEMPERATURE,
        "top_p": config.TOP_P,
        "stream": config.STREAM,
        "max_context_messages": config.MAX_CONTEXT_MESSAGES,
        "auto_compress": config.AUTO_COMPRESS,
        "compress_threshold": config.COMPRESS_THRESHOLD,
    }


def apply_engine_settings(
    api_key: str = "",
    model: str = "deepseek-chat",
    story_length: int = 1500,
    max_tokens: int = 2048,
    temperature: float = 0.8,
    top_p: float = 0.9,
    stream: int = 0,
    max_context_messages: int = 20,
    auto_compress: int = 1,
    compress_threshold: int = 4000,
) -> dict:
    """Persist engine settings and return updated payload."""
    key = api_key.strip()
    if key:
        save_api_key(key)
        reload_api_key()
    if model in AVAILABLE_MODELS:
        save_model(model)
        reload_model()
    save_story_length(max(300, min(3000, story_length)))
    reload_story_length()
    save_max_tokens(max(512, min(16384, max_tokens)))
    reload_max_tokens()
    save_temperature(max(0.1, min(2.0, temperature)))
    reload_temperature()
    save_top_p(max(0.0, min(1.0, top_p)))
    reload_top_p()
    save_stream(bool(stream))
    reload_stream()
    save_context_settings(
        max(4, min(100, max_context_messages)),
        bool(auto_compress),
        max(500, min(32000, compress_threshold)),
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
