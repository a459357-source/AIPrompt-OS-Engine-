"""
Prompt OS Engine Lite v1 — Configuration
=========================================
Central config: paths, API settings, engine constants.
Set DEEPSEEK_API_KEY in your environment before running.
"""

import json
import os
import re
import sys
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
    BUNDLE_ROOT = Path(sys._MEIPASS)
else:
    ROOT = Path(__file__).resolve().parent
    BUNDLE_ROOT = ROOT


def bundled_asset(name: str) -> Path:
    """Read-only shipped assets (engine.yaml, prompt_template.yaml).

    PyInstaller --onedir places --add-data files under _MEIPASS/_internal,
    not next to the exe. Runtime YAML (world_pack, session) stays under ROOT.
    """
    if getattr(sys, "frozen", False):
        candidate = BUNDLE_ROOT / name
        if candidate.exists():
            return candidate
    return ROOT / name


WORLD_PACK_PATH      = ROOT / "world_pack.yaml"
SESSION_STATE_PATH   = ROOT / "session_state.yaml"
ENGINE_CONFIG_PATH   = bundled_asset("engine.yaml")
PROMPT_TEMPLATE_PATH = bundled_asset("prompt_template.yaml")

OUTPUT_DIR           = ROOT / "output"
CHAPTER_PATH         = OUTPUT_DIR / "chapter.md"
TURN_LOG_PATH        = OUTPUT_DIR / "turn_log.json"
DASHBOARD_HTML_PATH  = OUTPUT_DIR / "dashboard.html"

DATA_DIR             = ROOT / "data"
STORY_GRAPH_PATH     = DATA_DIR / "story_graph.json"
MEMORY_PATH          = DATA_DIR / "memory.json"
CANDIDATE_NPCS_PATH  = DATA_DIR / "candidate_npcs.json"
SAVES_DIR            = DATA_DIR / "saves"
WORLD_INIT_PATH      = DATA_DIR / "world_init.json"
API_USAGE_PATH       = DATA_DIR / "api_usage.jsonl"
WORLD_SUMMARY_PATH   = DATA_DIR / "world_summary.json"
CHAPTER_SUMMARIES_PATH = DATA_DIR / "chapter_summaries.json"
TURN_PROFILE_PATH    = DATA_DIR / "turn_profile.jsonl"
RUNTIME_MEMORY_PATH  = DATA_DIR / "runtime_memory.json"
LOG_PATH             = DATA_DIR / "app.log"
ERROR_LOG_PATH       = DATA_DIR / "error.log"

# ── V2 performance / memory constants ─────────────────────────────
HOT_CONTEXT_MAX_TOKENS = 4000
HOT_CONTEXT_TURNS = 5
CHAPTER_SUMMARY_INTERVAL = 5
TURN_MAX_GENERATIONS = 2
API_MAX_PARSE_ATTEMPTS = 2
DASHBOARD_UPDATE_INTERVAL = 10
SNAPSHOT_TURN_INTERVAL = 5
LONG_TERM_MEMORY_MAX_CHARS = 2000
PROMPT_TOKEN_BUDGET = 7000

STORY_LENGTH_MIN_RATIO_SHORT = 0.80   # target 0–1000
STORY_LENGTH_MIN_RATIO_MEDIUM = 0.85  # 1000–3000
STORY_LENGTH_MIN_RATIO_LONG = 0.90    # 3000+

FRONTEND_DIST        = BUNDLE_ROOT / "frontend" / "dist"
if not (FRONTEND_DIST / "index.html").exists():
    FRONTEND_DIST    = ROOT / "frontend" / "dist"


def has_bundled_frontend() -> bool:
    """True when production React build is available (exe or local dist)."""
    return (FRONTEND_DIST / "index.html").exists()


def ensure_runtime_files() -> None:
    """Copy factory defaults next to exe on first run."""
    defaults = BUNDLE_ROOT / "packaging" / "defaults"
    if not defaults.is_dir():
        defaults = ROOT / "packaging" / "defaults"
    if not defaults.is_dir():
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SAVES_DIR.mkdir(parents=True, exist_ok=True)
    mapping = {
        "apikey.json": APIKEY_PATH,
        "memory.json": MEMORY_PATH,
        "story_graph.json": STORY_GRAPH_PATH,
        "session_state.yaml": SESSION_STATE_PATH,
        "world_pack.yaml": WORLD_PACK_PATH,
    }
    for name, dest in mapping.items():
        src = defaults / name
        if src.exists() and not dest.exists():
            dest.write_bytes(src.read_bytes())

# ── Frontend (React Vite dev server) ───────────────────────────────
# :8000 = API + 工具端点；日常 UI 请打开 FRONTEND_DEV_URL（默认 :5173）
FRONTEND_DEV_URL = os.environ.get("PROMPTOS_FRONTEND_URL", "http://127.0.0.1:5173").rstrip("/")


def frontend_url(path: str = "/") -> str:
    """Build absolute URL to the React SPA."""
    if has_bundled_frontend():
        base = os.environ.get("PROMPTOS_FRONTEND_URL", "http://127.0.0.1:8000").rstrip("/")
    else:
        base = FRONTEND_DEV_URL
    if not path or path == "/":
        return base
    return f"{base}/{path.lstrip('/')}"


# ── Save system ────────────────────────────────────────────────────
AUTOSAVE_SLOT = "autosave"
DEFAULT_MAX_SAVE_SLOTS = 3

# ── API Key storage ─────────────────────────────────────────────────
APIKEY_PATH = DATA_DIR / "apikey.json"


# ── Shared settings persistence ────────────────────────────────────
# All user-configurable settings (API key, model, token limits, etc.)
# are stored in a single JSON file (APIKEY_PATH).  Reading and writing
# the full dict avoids the previous pattern of 15 near-identical
# save_X() functions each calling __import__("json") separately.


def _read_settings() -> dict:
    """Load the full settings dict from apikey.json.  Returns {} on any error."""
    if not APIKEY_PATH.exists():
        return {}
    try:
        return json.loads(APIKEY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_settings(data: dict) -> None:
    """Persist the full settings dict to apikey.json atomically."""
    APIKEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    APIKEY_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _update_settings(**kwargs) -> dict:
    """Merge kwargs into the settings file and return the new full dict."""
    data = _read_settings()
    data.update(kwargs)
    _write_settings(data)
    return data


_API_KEY_RE = re.compile(r"sk-[a-fA-F0-9]{20,}")


def _sanitize_api_key(raw: str) -> str:
    """Extract a valid DeepSeek key from pasted text."""
    text = raw.strip()
    if not text:
        return ""
    if _API_KEY_RE.fullmatch(text):
        return text
    matches = _API_KEY_RE.findall(text)
    return matches[-1] if matches else ""


def _read_stored_api_key() -> str:
    """API key saved in data/apikey.json only (not env var)."""
    return _sanitize_api_key(_read_settings().get("api_key", ""))


def _load_api_key() -> str:
    """Load API key: file first, then env var (dev only), then empty."""
    key = _sanitize_api_key(_read_settings().get("api_key", ""))
    if key:
        return key
    # Packaged exe must NOT inherit the builder's machine env var.
    if getattr(sys, "frozen", False):
        return ""
    env_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if env_key:
        return env_key
    return ""


def save_api_key(key: str) -> None:
    """Persist API key to disk."""
    cleaned = _sanitize_api_key(key)
    if key.strip() and not cleaned:
        raise ValueError("API Key 格式无效，请只粘贴以 sk- 开头的密钥")
    _update_settings(api_key=cleaned)


def clear_api_key() -> None:
    """Remove the stored API key file."""
    if APIKEY_PATH.exists():
        APIKEY_PATH.unlink()


def reload_api_key() -> str:
    """Re-read the API key and update the module-level constant."""
    global DEEPSEEK_API_KEY
    DEEPSEEK_API_KEY = _load_api_key()
    return DEEPSEEK_API_KEY


# ── Available models ────────────────────────────────────────────────
AVAILABLE_MODELS = {
    "deepseek-chat":       "V4-Flash（快速，适合剧情生成）",
    "deepseek-reasoner":   "V4-Pro（深度推理，适合复杂剧情）",
}


def _load_model() -> str:
    """Load model preference from settings, default deepseek-chat."""
    default = "deepseek-chat"
    data = _read_settings()
    model = data.get("model", default)
    if model in AVAILABLE_MODELS:
        return model
    return default


def save_model(model: str) -> None:
    """Persist model preference."""
    _update_settings(model=model)


def reload_model() -> str:
    """Re-read model preference and update the module-level constant."""
    global DEEPSEEK_MODEL
    DEEPSEEK_MODEL = _load_model()
    return DEEPSEEK_MODEL


# ── DeepSeek API limits (official) ──────────────────────────────────
# Source: https://api-docs.deepseek.com/quick_start/pricing
DEEPSEEK_CONTEXT_TOKENS = 1_000_000      # 1M context window
DEEPSEEK_MAX_OUTPUT_TOKENS = 384_000     # 384K max output per request
DEEPSEEK_MIN_OUTPUT_TOKENS = 1
DEEPSEEK_MAX_TEMPERATURE = 2.0
DEEPSEEK_MAX_TOP_P = 1.0


def cap_output_tokens(tokens: int) -> int:
    """Clamp max_tokens to DeepSeek official output range."""
    return max(DEEPSEEK_MIN_OUTPUT_TOKENS, min(DEEPSEEK_MAX_OUTPUT_TOKENS, int(tokens)))


def api_limits() -> dict[str, int | float]:
    """Official API limits exposed to the frontend."""
    return {
        "context_tokens": DEEPSEEK_CONTEXT_TOKENS,
        "max_output_tokens": DEEPSEEK_MAX_OUTPUT_TOKENS,
        "max_temperature": DEEPSEEK_MAX_TEMPERATURE,
        "max_top_p": DEEPSEEK_MAX_TOP_P,
    }


# ── Story length ────────────────────────────────────────────────────
MIN_STORY_LENGTH = 300
DEFAULT_STORY_LENGTH = 1000
RECOMMENDED_STORY_LENGTH = DEFAULT_STORY_LENGTH
# 目标字数浮动：设定 <1000 固定 ±200；≥1000 为 max(200, 15%) 且溢出上限 1000
STORY_LENGTH_SHORT_THRESHOLD = 1000
STORY_LENGTH_SHORT_FLOAT = 200
STORY_LENGTH_LONG_RATIO = 0.15
STORY_LENGTH_MAX_OVERFLOW = 1000
# JSON 回复含 story + options + state；overhead 随选项数缩放
STORY_CHAR_TO_TOKEN = 1.35
JSON_OUTPUT_BASE_OVERHEAD = 400
JSON_OUTPUT_PER_OPTION = 80
JSON_STATE_BUFFER = 200
# 默认 4 选项时的 overhead（用于 MAX_STORY_LENGTH 估算）
JSON_OUTPUT_OVERHEAD_TOKENS = JSON_OUTPUT_BASE_OVERHEAD + 4 * JSON_OUTPUT_PER_OPTION + JSON_STATE_BUFFER
MAX_STORY_LENGTH = int(
    (DEEPSEEK_MAX_OUTPUT_TOKENS - JSON_OUTPUT_OVERHEAD_TOKENS) / STORY_CHAR_TO_TOKEN
)


def clamp_story_length(length: int) -> int:
    """Clamp target story length to values the engine can honor."""
    return max(MIN_STORY_LENGTH, min(MAX_STORY_LENGTH, int(length)))


def json_output_overhead_tokens(option_count: int | None = None) -> int:
    """Token budget for options + state JSON (excludes story body)."""
    n = option_count if option_count is not None else DEFAULT_OPTION_COUNT
    return JSON_OUTPUT_BASE_OVERHEAD + n * JSON_OUTPUT_PER_OPTION + JSON_STATE_BUFFER


def tokens_for_story_length(length: int, option_count: int | None = None) -> int:
    """Map target story length to max_tokens (official output cap)."""
    chars = clamp_story_length(length)
    n = option_count if option_count is not None else _load_option_count()
    needed = int(chars * STORY_CHAR_TO_TOKEN) + json_output_overhead_tokens(n)
    return cap_output_tokens(needed)


def compress_threshold_for_story_length(length: int) -> int:
    """Scale compress threshold with per-turn story size (longer turns → higher bar)."""
    chars = clamp_story_length(length)
    per_turn_tokens = int(chars * 0.6)
    needed = DEFAULT_COMPRESS_THRESHOLD + per_turn_tokens * 5
    return max(500, min(DEEPSEEK_CONTEXT_TOKENS, needed))


def ensure_story_length_token_sync() -> None:
    """Keep max_tokens aligned with story_length (fixes legacy saves)."""
    matched = tokens_for_story_length(STORY_LENGTH)
    if MAX_TOKENS != matched:
        save_max_tokens(matched)
        reload_max_tokens()


def ensure_story_length_context_sync(*, force_compress: bool = False) -> None:
    """Keep max_tokens aligned; raise compress_threshold when below story-scaled minimum."""
    matched_tokens = tokens_for_story_length(STORY_LENGTH)
    matched_compress = compress_threshold_for_story_length(STORY_LENGTH)
    updates: dict = {}
    if MAX_TOKENS != matched_tokens:
        updates["max_tokens"] = matched_tokens
    if force_compress:
        if COMPRESS_THRESHOLD != matched_compress:
            updates["compress_threshold"] = matched_compress
    elif COMPRESS_THRESHOLD < matched_compress:
        updates["compress_threshold"] = matched_compress
    if updates:
        _update_settings(**updates)
        if "max_tokens" in updates:
            reload_max_tokens()
        if "compress_threshold" in updates:
            reload_context_settings()


def story_length_float_margin(length: int | None = None) -> int:
    """Acceptable ± chars from target (see STORY_LENGTH_* constants)."""
    target = clamp_story_length(length if length is not None else STORY_LENGTH)
    if target < STORY_LENGTH_SHORT_THRESHOLD:
        return STORY_LENGTH_SHORT_FLOAT
    pct = int(target * STORY_LENGTH_LONG_RATIO)
    return min(STORY_LENGTH_MAX_OVERFLOW, max(STORY_LENGTH_SHORT_FLOAT, pct))


def story_length_acceptable_range(length: int | None = None) -> tuple[int, int, int]:
    """Return (min, max, margin) for validation and logging."""
    target = clamp_story_length(length if length is not None else STORY_LENGTH)
    margin = story_length_float_margin(target)
    return (
        max(MIN_STORY_LENGTH, target - margin),
        target + margin,
        margin,
    )


def min_story_length_for_target(length: int | None = None) -> int:
    """Minimum acceptable story chars for the given target."""
    lo, _, _ = story_length_acceptable_range(length)
    return lo


def max_story_length_for_target(length: int | None = None) -> int:
    """Maximum acceptable story chars for the given target."""
    _, hi, _ = story_length_acceptable_range(length)
    return hi


def story_length_limits() -> dict[str, int]:
    target = STORY_LENGTH
    limits = {
        "min": MIN_STORY_LENGTH,
        "max": MAX_STORY_LENGTH,
        "recommended": RECOMMENDED_STORY_LENGTH,
        "target_min": min_story_length_for_target(target),
        "target_max": max_story_length_for_target(target),
        "max_output_tokens": DEEPSEEK_MAX_OUTPUT_TOKENS,
        "context_tokens": DEEPSEEK_CONTEXT_TOKENS,
    }
    return limits


def _load_story_length() -> int:
    """Load story length preference from settings."""
    val = _read_settings().get("story_length", DEFAULT_STORY_LENGTH)
    return clamp_story_length(val)


def save_story_length(length: int) -> None:
    """Persist story length and sync max_tokens / compress_threshold to match."""
    length = clamp_story_length(length)
    _update_settings(
        story_length=length,
        max_tokens=tokens_for_story_length(length),
        compress_threshold=compress_threshold_for_story_length(length),
    )


def reload_story_length() -> int:
    """Re-read and update story length."""
    global STORY_LENGTH
    STORY_LENGTH = _load_story_length()
    return STORY_LENGTH


# ── Max tokens (AI response length) ─────────────────────────────────
DEFAULT_MAX_TOKENS = 4096


def _load_max_tokens() -> int:
    """Load max_tokens preference from settings."""
    val = _read_settings().get("max_tokens", DEFAULT_MAX_TOKENS)
    return cap_output_tokens(val)


def save_max_tokens(tokens: int) -> None:
    """Persist max_tokens preference."""
    _update_settings(max_tokens=cap_output_tokens(tokens))


def reload_max_tokens() -> int:
    """Re-read and update max_tokens."""
    global MAX_TOKENS
    MAX_TOKENS = _load_max_tokens()
    return MAX_TOKENS


def world_gen_output_tokens(base: int | None = None) -> int:
    """World/field generation may request 2× turn budget, capped at official max."""
    base_tokens = base if base is not None else MAX_TOKENS
    return cap_output_tokens(base_tokens * 2)


# ── Temperature ─────────────────────────────────────────────────────
DEFAULT_TEMPERATURE = 0.8


def _load_temperature() -> float:
    val = _read_settings().get("temperature", DEFAULT_TEMPERATURE)
    return max(0.1, min(DEEPSEEK_MAX_TEMPERATURE, float(val)))


def save_temperature(temp: float) -> None:
    _update_settings(temperature=temp)


def reload_temperature() -> float:
    global TEMPERATURE
    TEMPERATURE = _load_temperature()
    return TEMPERATURE


# ── Top-P ───────────────────────────────────────────────────────────
DEFAULT_TOP_P = 0.9


def _load_top_p() -> float:
    val = _read_settings().get("top_p", DEFAULT_TOP_P)
    return max(0.0, min(DEEPSEEK_MAX_TOP_P, float(val)))


def save_top_p(val: float) -> None:
    _update_settings(top_p=val)


def reload_top_p() -> float:
    global TOP_P
    TOP_P = _load_top_p()
    return TOP_P


# ── Streaming ───────────────────────────────────────────────────────
DEFAULT_STREAM = True


def _load_stream() -> bool:
    return bool(_read_settings().get("stream", DEFAULT_STREAM))


def save_stream(val: bool) -> None:
    _update_settings(stream=val)


def reload_stream() -> bool:
    global STREAM
    STREAM = _load_stream()
    return STREAM


# ── Context management ──────────────────────────────────────────────
DEFAULT_MAX_CONTEXT_MESSAGES = HOT_CONTEXT_TURNS
DEFAULT_AUTO_COMPRESS = True
DEFAULT_COMPRESS_THRESHOLD = 4000


def _load_context_settings() -> dict:
    defaults = {
        "max_context_messages": DEFAULT_MAX_CONTEXT_MESSAGES,
        "auto_compress": DEFAULT_AUTO_COMPRESS,
        "compress_threshold": DEFAULT_COMPRESS_THRESHOLD,
    }
    data = _read_settings()
    return {
        "max_context_messages": max(4, min(100, int(data.get("max_context_messages", defaults["max_context_messages"])))),
        "auto_compress": bool(data.get("auto_compress", defaults["auto_compress"])),
        "compress_threshold": max(
            500,
            min(DEEPSEEK_CONTEXT_TOKENS, int(data.get("compress_threshold", defaults["compress_threshold"]))),
        ),
    }


def save_context_settings(max_msgs: int, auto_compress: bool, compress_threshold: int) -> None:
    _update_settings(max_context_messages=max_msgs, auto_compress=auto_compress,
                     compress_threshold=compress_threshold)


def reload_context_settings() -> dict:
    global MAX_CONTEXT_MESSAGES, AUTO_COMPRESS, COMPRESS_THRESHOLD
    s = _load_context_settings()
    MAX_CONTEXT_MESSAGES = s["max_context_messages"]
    AUTO_COMPRESS = s["auto_compress"]
    COMPRESS_THRESHOLD = s["compress_threshold"]
    return s


# ── App behavior (AI narrative + save + export) ─────────────────────
DEFAULT_OPTION_COUNT = 4
DEFAULT_NARRATIVE_POV = "auto"
DEFAULT_STYLE_PREFERENCE = "balanced"
DEFAULT_REPETITION_CHECK = "standard"
DEFAULT_AUTO_SAVE_INTERVAL = 60
DEFAULT_EXPORT_FORMAT = "markdown"
DEFAULT_AUTO_EXPORT = "off"

NARRATIVE_POV_INSTRUCTIONS = {
    "first": "使用第一人称「我」叙事，贴近主角内心。",
    "third": "使用第三人称叙事（全知或限知均可）。",
    "auto": "根据场景自动选择最合适的人称视角。",
}
STYLE_PREFERENCE_INSTRUCTIONS = {
    "descriptive": "文风偏细腻描写，环境、动作与感官细节丰富。",
    "fast": "文风偏快节奏，少铺垫，情节推进干脆。",
    "dialogue": "以对话推动剧情，对话占比高。",
    "psycho": "侧重心理刻画与内心独白。",
    "balanced": "描写、对话、心理均衡。",
}
REPETITION_PROMPT_INSTRUCTIONS = {
    "strict": "严禁重复已写过的情节、对话套路或场景描写；每轮必须有新信息。",
    "standard": "避免明显重复已发生的情节与套路。",
    "loose": "允许适度呼应前文，但不要整段复述。",
}


def _clamp_option_count(val: int) -> int:
    return max(3, min(5, int(val)))


def _load_option_count() -> int:
    return _clamp_option_count(_read_settings().get("option_count", DEFAULT_OPTION_COUNT))


def save_option_count(count: int) -> None:
    _update_settings(option_count=_clamp_option_count(count))


def reload_option_count() -> int:
    global OPTION_COUNT
    OPTION_COUNT = _load_option_count()
    return OPTION_COUNT


def _load_narrative_pov() -> str:
    val = _read_settings().get("narrative_pov", DEFAULT_NARRATIVE_POV)
    return val if val in NARRATIVE_POV_INSTRUCTIONS else DEFAULT_NARRATIVE_POV


def save_narrative_pov(pov: str) -> None:
    if pov not in NARRATIVE_POV_INSTRUCTIONS:
        pov = DEFAULT_NARRATIVE_POV
    _update_settings(narrative_pov=pov)


def reload_narrative_pov() -> str:
    global NARRATIVE_POV
    NARRATIVE_POV = _load_narrative_pov()
    return NARRATIVE_POV


def _load_style_preference() -> str:
    val = _read_settings().get("style_preference", DEFAULT_STYLE_PREFERENCE)
    return val if val in STYLE_PREFERENCE_INSTRUCTIONS else DEFAULT_STYLE_PREFERENCE


def save_style_preference(style: str) -> None:
    if style not in STYLE_PREFERENCE_INSTRUCTIONS:
        style = DEFAULT_STYLE_PREFERENCE
    _update_settings(style_preference=style)


def reload_style_preference() -> str:
    global STYLE_PREFERENCE
    STYLE_PREFERENCE = _load_style_preference()
    return STYLE_PREFERENCE


def _load_repetition_check() -> str:
    val = _read_settings().get("repetition_check", DEFAULT_REPETITION_CHECK)
    return val if val in REPETITION_PROMPT_INSTRUCTIONS else DEFAULT_REPETITION_CHECK


def save_repetition_check(level: str) -> None:
    if level not in REPETITION_PROMPT_INSTRUCTIONS:
        level = DEFAULT_REPETITION_CHECK
    _update_settings(repetition_check=level)


def reload_repetition_check() -> str:
    global REPETITION_CHECK
    REPETITION_CHECK = _load_repetition_check()
    return REPETITION_CHECK


def _load_auto_save_interval() -> int:
    val = int(_read_settings().get("auto_save_interval", DEFAULT_AUTO_SAVE_INTERVAL))
    if val in (0, 30, 60, 300):
        return val
    return DEFAULT_AUTO_SAVE_INTERVAL


def save_auto_save_interval(seconds: int) -> None:
    val = int(seconds)
    if val not in (0, 30, 60, 300):
        val = DEFAULT_AUTO_SAVE_INTERVAL
    _update_settings(auto_save_interval=val)


def reload_auto_save_interval() -> int:
    global AUTO_SAVE_INTERVAL
    AUTO_SAVE_INTERVAL = _load_auto_save_interval()
    return AUTO_SAVE_INTERVAL


def _load_max_save_slots() -> int:
    val = int(_read_settings().get("max_save_slots", DEFAULT_MAX_SAVE_SLOTS))
    if val in (3, 5, 10):
        return val
    return DEFAULT_MAX_SAVE_SLOTS


def save_max_save_slots(count: int) -> None:
    val = int(count)
    if val not in (3, 5, 10):
        val = DEFAULT_MAX_SAVE_SLOTS
    _update_settings(max_save_slots=val)


def reload_max_save_slots() -> int:
    global MAX_SAVE_SLOTS
    MAX_SAVE_SLOTS = _load_max_save_slots()
    return MAX_SAVE_SLOTS


def _load_export_format() -> str:
    val = _read_settings().get("export_format", DEFAULT_EXPORT_FORMAT)
    return val if val in ("markdown", "text", "html") else DEFAULT_EXPORT_FORMAT


def save_export_format(fmt: str) -> None:
    if fmt not in ("markdown", "text", "html"):
        fmt = DEFAULT_EXPORT_FORMAT
    _update_settings(export_format=fmt)


def reload_export_format() -> str:
    global EXPORT_FORMAT
    EXPORT_FORMAT = _load_export_format()
    return EXPORT_FORMAT


def _load_auto_export() -> str:
    val = _read_settings().get("auto_export", DEFAULT_AUTO_EXPORT)
    return val if val in ("off", "turn", "chapter") else DEFAULT_AUTO_EXPORT


def save_auto_export(mode: str) -> None:
    if mode not in ("off", "turn", "chapter"):
        mode = DEFAULT_AUTO_EXPORT
    _update_settings(auto_export=mode)


def reload_auto_export() -> str:
    global AUTO_EXPORT
    AUTO_EXPORT = _load_auto_export()
    return AUTO_EXPORT


def reload_app_behavior() -> None:
    reload_option_count()
    reload_narrative_pov()
    reload_style_preference()
    reload_repetition_check()
    reload_auto_save_interval()
    reload_max_save_slots()
    reload_export_format()
    reload_auto_export()


def valid_manual_save_slots() -> list[str]:
    return [f"slot{i}" for i in range(1, MAX_SAVE_SLOTS + 1)]


def all_save_slots() -> list[str]:
    return [AUTOSAVE_SLOT, *valid_manual_save_slots()]


def is_valid_save_slot(slot: str) -> bool:
    return slot in all_save_slots()


def force_event_thresholds() -> dict[str, int]:
    scale = {"strict": 0.75, "standard": 1.0, "loose": 1.5}.get(REPETITION_CHECK, 1.0)
    return {
        "same_scene": max(2, int(MAX_TURNS_SAME_SCENE * scale)),
        "same_status": max(2, int(MAX_TURNS_SAME_STATUS * scale)),
        "interaction": max(2, int(MAX_TURNS_INTERACTION_STAGNANT * scale)),
    }


def ai_behavior_rules_text() -> str:
    return (
        f"【叙事视角】{NARRATIVE_POV_INSTRUCTIONS[NARRATIVE_POV]}\n"
        f"【文风偏好】{STYLE_PREFERENCE_INSTRUCTIONS[STYLE_PREFERENCE]}\n"
        f"【选项数量】必须输出恰好 {OPTION_COUNT} 个 options。\n"
        f"【反重复】{REPETITION_PROMPT_INSTRUCTIONS[REPETITION_CHECK]}"
    )


# ── DeepSeek API ────────────────────────────────────────────────────
DEEPSEEK_API_KEY = _load_api_key()
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = _load_model()
STORY_LENGTH = _load_story_length()
MAX_TOKENS = _load_max_tokens()
TEMPERATURE = _load_temperature()
TOP_P = _load_top_p()
STREAM = _load_stream()
ctx = _load_context_settings()
MAX_CONTEXT_MESSAGES = ctx["max_context_messages"]
AUTO_COMPRESS = ctx["auto_compress"]
COMPRESS_THRESHOLD = ctx["compress_threshold"]
reload_app_behavior()

# ── Obsidian live export ────────────────────────────────────────────
# Path to an Obsidian vault folder.  When set, the engine writes
# per-chapter .md files directly into this vault after every turn.
# Obsidian auto-refreshes — open the vault to read the story in real-time.
# Set via CLI: /obsidian, or edit obsidian_path.json manually.
OBSIDIAN_PATH_FILE = DATA_DIR / "obsidian_path.json"

def _load_obsidian_path() -> str:
    if not OBSIDIAN_PATH_FILE.exists():
        return ""
    try:
        return json.loads(OBSIDIAN_PATH_FILE.read_text(encoding="utf-8")).get("vault_path", "")
    except Exception:
        return ""

def save_obsidian_path(path: str) -> None:
    OBSIDIAN_PATH_FILE.parent.mkdir(parents=True, exist_ok=True)
    OBSIDIAN_PATH_FILE.write_text(
        json.dumps({"vault_path": path.strip()}, indent=2),
        encoding="utf-8",
    )

OBSIDIAN_VAULT_PATH = _load_obsidian_path()

# ── Logging setup ───────────────────────────────────────────────────

_LOGGING_CONFIGURED = False


def log_paths_hint() -> str:
    """Human-readable paths to runtime log files."""
    return f"运行日志: {LOG_PATH}\n错误日志: {ERROR_LOG_PATH}"


def install_excepthook() -> None:
    """Write uncaught exceptions to error.log (exe / bat / CLI)."""
    if getattr(install_excepthook, "_installed", False):
        return
    install_excepthook._installed = True

    import logging
    import traceback

    def _hook(exc_type, exc, tb):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"\n{'=' * 60}\n")
                f.write("Uncaught exception\n")
                traceback.print_exception(exc_type, exc, tb, file=f)
        except Exception:
            pass
        logging.getLogger("promptos").critical(
            "Uncaught exception", exc_info=(exc_type, exc, tb)
        )
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook


def setup_logging(*, console: bool = True) -> None:
    """Configure Python logging: console + rotating app.log + error.log."""
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    import logging
    from logging.handlers import RotatingFileHandler

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    from engine.constants import LOG_MAX_BYTES, LOG_BACKUP_COUNT

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if console and not any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
        for h in root_logger.handlers
    ):
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        root_logger.addHandler(ch)

    if not any(getattr(h, "baseFilename", None) == str(LOG_PATH) for h in root_logger.handlers):
        fh = RotatingFileHandler(
            str(LOG_PATH), maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        root_logger.addHandler(fh)

    from engine.constants import ERROR_LOG_MAX_BYTES, ERROR_LOG_BACKUP_COUNT

    if not any(getattr(h, "baseFilename", None) == str(ERROR_LOG_PATH) for h in root_logger.handlers):
        efh = RotatingFileHandler(
            str(ERROR_LOG_PATH),
            maxBytes=ERROR_LOG_MAX_BYTES,
            backupCount=ERROR_LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        efh.setLevel(logging.ERROR)
        efh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s\n"
            "  File: %(pathname)s:%(lineno)d\n"
            "  Function: %(funcName)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root_logger.addHandler(efh)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        lg = logging.getLogger(name)
        lg.propagate = True

    install_excepthook()
    _LOGGING_CONFIGURED = True
    logging.getLogger("promptos").info("Logging initialized — %s | %s", LOG_PATH, ERROR_LOG_PATH)


# ── Character tier system ───────────────────────────────────────────
# Four-tier classification with hard capacity limits.
# Tiers: 主角 > 核心 > 重要 > 背景 > 退休
CHARACTER_TIER_LIMITS = {
    "主角": 1,
    "核心": 6,
    "重要": 15,
    # 背景: unlimited
}
TIER_ORDER = ["主角", "核心", "重要", "背景"]  # degradation order (skip 退休)
TIER_DEGRADATION_TURNS = 10  # turns without appearance → degrade one tier

# ── Engine constants ────────────────────────────────────────────────
STATUS_ORDER = ["SETUP", "BUILD", "TENSION", "CLIMAX", "COOLDOWN"]

# State machine: max turns before forced advancement
MAX_TURNS_SAME_STATUS = 2
# Scene: max turns in the same scene before force event
MAX_TURNS_SAME_SCENE = 3
# Interaction: max turns with no level increase before force event
MAX_TURNS_INTERACTION_STAGNANT = 2

# Interaction levels (from spec)
INTERACTION_LEVELS = ["L0", "L1", "L2", "L3", "L4"]
