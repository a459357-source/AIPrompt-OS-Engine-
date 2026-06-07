"""
Prompt OS Engine Lite v1 — Configuration
=========================================
Central config: paths, API settings, engine constants.
Set DEEPSEEK_API_KEY in your environment before running.
"""

import json
import os
import sys
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
    BUNDLE_ROOT = Path(sys._MEIPASS)
else:
    ROOT = Path(__file__).resolve().parent
    BUNDLE_ROOT = ROOT

WORLD_PACK_PATH      = ROOT / "world_pack.yaml"
SESSION_STATE_PATH   = ROOT / "session_state.yaml"
ENGINE_CONFIG_PATH   = ROOT / "engine.yaml"
PROMPT_TEMPLATE_PATH = ROOT / "prompt_template.yaml"

OUTPUT_DIR           = ROOT / "output"
CHAPTER_PATH         = OUTPUT_DIR / "chapter.md"
TURN_LOG_PATH        = OUTPUT_DIR / "turn_log.json"
DASHBOARD_HTML_PATH  = OUTPUT_DIR / "dashboard.html"

DATA_DIR             = ROOT / "data"
STORY_GRAPH_PATH     = DATA_DIR / "story_graph.json"
MEMORY_PATH          = DATA_DIR / "memory.json"
SAVES_DIR            = DATA_DIR / "saves"
WORLD_INIT_PATH      = DATA_DIR / "world_init.json"
API_USAGE_PATH       = DATA_DIR / "api_usage.jsonl"
LOG_PATH             = DATA_DIR / "app.log"
ERROR_LOG_PATH       = DATA_DIR / "error.log"

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
# :8000 = API + 遗留路由；日常 UI 请打开 FRONTEND_DEV_URL（默认 :5173）
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
MAX_SAVE_SLOTS = 3
AUTOSAVE_SLOT = "autosave"

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


def _read_stored_api_key() -> str:
    """API key saved in data/apikey.json only (not env var)."""
    return _read_settings().get("api_key", "").strip()


def _load_api_key() -> str:
    """Load API key: file first, then env var (dev only), then empty."""
    data = _read_settings()
    key = data.get("api_key", "").strip()
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
    _update_settings(api_key=key.strip())


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


# ── Story length ────────────────────────────────────────────────────
DEFAULT_STORY_LENGTH = 1000


def _load_story_length() -> int:
    """Load story length preference from settings."""
    val = _read_settings().get("story_length", DEFAULT_STORY_LENGTH)
    return max(300, min(3000, int(val)))


def save_story_length(length: int) -> None:
    """Persist story length preference."""
    _update_settings(story_length=length)


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
    return max(512, min(16384, int(val)))


def save_max_tokens(tokens: int) -> None:
    """Persist max_tokens preference."""
    _update_settings(max_tokens=tokens)


def reload_max_tokens() -> int:
    """Re-read and update max_tokens."""
    global MAX_TOKENS
    MAX_TOKENS = _load_max_tokens()
    return MAX_TOKENS


# ── Temperature ─────────────────────────────────────────────────────
DEFAULT_TEMPERATURE = 0.8


def _load_temperature() -> float:
    val = _read_settings().get("temperature", DEFAULT_TEMPERATURE)
    return max(0.1, min(2.0, float(val)))


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
    return max(0.0, min(1.0, float(val)))


def save_top_p(val: float) -> None:
    _update_settings(top_p=val)


def reload_top_p() -> float:
    global TOP_P
    TOP_P = _load_top_p()
    return TOP_P


# ── Streaming ───────────────────────────────────────────────────────
DEFAULT_STREAM = False


def _load_stream() -> bool:
    return bool(_read_settings().get("stream", DEFAULT_STREAM))


def save_stream(val: bool) -> None:
    _update_settings(stream=val)


def reload_stream() -> bool:
    global STREAM
    STREAM = _load_stream()
    return STREAM


# ── Context management ──────────────────────────────────────────────
DEFAULT_MAX_CONTEXT_MESSAGES = 20
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
        "compress_threshold": max(500, min(32000, int(data.get("compress_threshold", defaults["compress_threshold"])))),
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

def setup_logging():
    """Configure Python logging: console + rotating file handlers."""
    import logging
    from logging.handlers import RotatingFileHandler

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    from engine.constants import LOG_MAX_BYTES, LOG_BACKUP_COUNT

    # File handler — all logs (rotating)
    fh = RotatingFileHandler(
        str(LOG_PATH), maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    root_logger.addHandler(fh)

    from engine.constants import ERROR_LOG_MAX_BYTES, ERROR_LOG_BACKUP_COUNT

    # Error file handler — errors only
    efh = RotatingFileHandler(
        str(ERROR_LOG_PATH), maxBytes=ERROR_LOG_MAX_BYTES, backupCount=ERROR_LOG_BACKUP_COUNT, encoding="utf-8"
    )
    efh.setLevel(logging.ERROR)
    efh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s\n"
        "  File: %(pathname)s:%(lineno)d\n"
        "  Function: %(funcName)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root_logger.addHandler(efh)

    logging.getLogger("engine.deepseek_client").info("Logging initialized — app.log + error.log")


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
