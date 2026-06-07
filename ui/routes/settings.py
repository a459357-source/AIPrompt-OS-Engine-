"""Settings page, dashboard, and export routes."""
from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from pathlib import Path

from engine import io_utils
from config import (
    save_api_key, clear_api_key, reload_api_key, APIKEY_PATH,
    save_model, reload_model, AVAILABLE_MODELS,
    save_story_length, reload_story_length,
    save_max_tokens, reload_max_tokens,
    save_temperature, reload_temperature,
    save_top_p, reload_top_p,
    save_stream, reload_stream,
    save_context_settings, reload_context_settings,
)
from ui.templates import _SETTINGS_PAGE
from engine.dashboard import build_html
import config

router = APIRouter(tags=["settings"])

@router.get("/settings", response_class=HTMLResponse)
async def settings_page():
    """Show API key settings page."""
    key = config._read_stored_api_key()
    masked = ""
    if key:
        masked = key[:8] + "…" + key[-4:] if len(key) > 12 else "***"

    status_class = "ok" if key else "empty"
    status_text = f"✅ 已配置 ({masked})" if key else "❌ 未设置 — 请在下方输入 API Key"

    # NEVER echo full key to HTML — use masked or empty placeholder
    display_key = masked if key else ""

    # Model options
    current_model = config.DEEPSEEK_MODEL
    model_opts = []
    model_hint = ""
    for mid, mlabel in AVAILABLE_MODELS.items():
        sel = ' selected' if mid == current_model else ''
        model_opts.append(f'<option value="{mid}"{sel}>{mlabel}</option>')
        if mid == current_model:
            model_hint = f"当前: {mlabel}"
    if not model_hint:
        model_hint = "当前: V4-Flash（默认）"

    # Max tokens options
    current_max_tokens = config.MAX_TOKENS
    max_tokens_opts = []
    max_tokens_hint = ""
    for val in [512, 1024, 2048, 4096, 8192, 16384]:
        sel = ' selected' if val == current_max_tokens else ''
        label = f"{val} tokens（{'快速/可能截断' if val <= 1024 else '标准' if val <= 2048 else '完整/较慢' if val <= 4096 else '最大/最慢'}）"
        max_tokens_opts.append(f'<option value="{val}"{sel}>{label}</option>')
        if val == current_max_tokens:
            max_tokens_hint = f"当前: {val} tokens"

    # Stream options
    stream_opts = []
    for val, label in [(0, "关闭"), (1, "开启（实验性）")]:
        sel = ' selected' if bool(val) == config.STREAM else ''
        stream_opts.append(f'<option value="{val}"{sel}>{label}</option>')

    # Auto-compress options
    ac_opts = []
    for val, label in [(1, "开启"), (0, "关闭")]:
        sel = ' selected' if bool(val) == config.AUTO_COMPRESS else ''
        ac_opts.append(f'<option value="{val}"{sel}>{label}</option>')

    page = (
        _SETTINGS_PAGE
        .replace("{{MASKED_KEY}}", display_key)
        .replace("{{STATUS_CLASS}}", status_class)
        .replace("{{STATUS_TEXT}}", status_text)
        .replace("{{MODEL_OPTIONS}}", "\n".join(model_opts))
        .replace("{{MODEL_HINT}}", model_hint)
        .replace("{{STORY_LENGTH}}", str(config.STORY_LENGTH))
        .replace("{{MAX_TOKENS_OPTIONS}}", "\n".join(max_tokens_opts))
        .replace("{{TEMPERATURE}}", str(config.TEMPERATURE))
        .replace("{{TOP_P}}", str(config.TOP_P))
        .replace("{{STREAM_OPTIONS}}", "\n".join(stream_opts))
        .replace("{{MAX_CONTEXT_MESSAGES}}", str(config.MAX_CONTEXT_MESSAGES))
        .replace("{{AUTO_COMPRESS_OPTIONS}}", "\n".join(ac_opts))
        .replace("{{COMPRESS_THRESHOLD}}", str(config.COMPRESS_THRESHOLD))
    )
    return HTMLResponse(page)


@router.post("/settings", response_class=HTMLResponse)
async def save_settings(
    api_key: str = Form(""),
    model: str = Form("deepseek-chat"),
    story_length: int = Form(1500),
    max_tokens: int = Form(2048),
    temperature: float = Form(0.8),
    top_p: float = Form(0.9),
    stream: int = Form(0),
    max_context_messages: int = Form(20),
    auto_compress: int = Form(1),
    compress_threshold: int = Form(4000),
):
    """Save all settings."""
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
    return await settings_page()


@router.post("/settings/clear", response_class=HTMLResponse)
async def clear_settings():
    """Clear the stored API key."""
    clear_api_key()
    reload_api_key()
    return await settings_page()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Analytics dashboard with toggleable panels — uses unified engine."""
    from engine.dashboard import build_html, ensure_local_js
    ensure_local_js()
    html = build_html()
    # Rewrite local paths for web serving
    html = html.replace('./mermaid.min.js', '/static/mermaid.min.js')
    html = html.replace('./chart.umd.min.js', '/static/chart.umd.min.js')
    return HTMLResponse(html)


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


# ── Helpers ────────────────────────────────────────────────────────
