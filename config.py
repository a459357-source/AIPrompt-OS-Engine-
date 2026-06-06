"""
Prompt OS Engine Lite v1 — Configuration
=========================================
Central config: paths, API settings, engine constants.
Set DEEPSEEK_API_KEY in your environment before running.
"""

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent

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

# ── Save system ────────────────────────────────────────────────────
MAX_SAVE_SLOTS = 3
AUTOSAVE_SLOT = "autosave"

# ── API Key storage ─────────────────────────────────────────────────
APIKEY_PATH = DATA_DIR / "apikey.json"


def _load_api_key() -> str:
    """Load API key: file first, then env var, then empty."""
    # 1. Try the stored key file
    if APIKEY_PATH.exists():
        try:
            data = __import__("json").loads(APIKEY_PATH.read_text(encoding="utf-8"))
            key = data.get("api_key", "").strip()
            if key:
                return key
        except Exception:
            pass
    # 2. Fall back to environment variable
    env_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if env_key:
        return env_key
    return ""


def save_api_key(key: str) -> None:
    """Persist API key to disk."""
    APIKEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    APIKEY_PATH.write_text(
        __import__("json").dumps({"api_key": key.strip()}, indent=2),
        encoding="utf-8",
    )


def clear_api_key() -> None:
    """Remove the stored API key file."""
    if APIKEY_PATH.exists():
        APIKEY_PATH.unlink()


def reload_api_key() -> str:
    """Re-read the API key and update the module-level constant.
    Call this after save_api_key() or clear_api_key() at runtime.
    Returns the new key (empty string if not set).
    """
    import config
    config.DEEPSEEK_API_KEY = _load_api_key()
    return config.DEEPSEEK_API_KEY


# ── Available models ────────────────────────────────────────────────
AVAILABLE_MODELS = {
    "deepseek-chat":       "V4-Flash（快速，适合剧情生成）",
    "deepseek-reasoner":   "V4-Pro（深度推理，适合复杂剧情）",
}


def _load_model() -> str:
    """Load model preference from apikey.json, default deepseek-chat."""
    default = "deepseek-chat"
    if APIKEY_PATH.exists():
        try:
            data = __import__("json").loads(APIKEY_PATH.read_text(encoding="utf-8"))
            model = data.get("model", default)
            if model in AVAILABLE_MODELS:
                return model
        except Exception:
            pass
    return default


def save_model(model: str) -> None:
    """Persist model preference (merges with existing key data)."""
    data = {}
    if APIKEY_PATH.exists():
        try:
            data = __import__("json").loads(APIKEY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    data["model"] = model
    APIKEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    APIKEY_PATH.write_text(
        __import__("json").dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def reload_model() -> str:
    """Re-read model preference and update the module-level constant."""
    import config
    config.DEEPSEEK_MODEL = _load_model()
    return config.DEEPSEEK_MODEL


# ── Story length ────────────────────────────────────────────────────
DEFAULT_STORY_LENGTH = 1000


def _load_story_length() -> int:
    """Load story length preference from apikey.json, default 1500."""
    if APIKEY_PATH.exists():
        try:
            data = __import__("json").loads(APIKEY_PATH.read_text(encoding="utf-8"))
            val = data.get("story_length", DEFAULT_STORY_LENGTH)
            return max(300, min(3000, int(val)))
        except Exception:
            pass
    return DEFAULT_STORY_LENGTH


def save_story_length(length: int) -> None:
    """Persist story length preference."""
    data = {}
    if APIKEY_PATH.exists():
        try:
            data = __import__("json").loads(APIKEY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    data["story_length"] = length
    APIKEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    APIKEY_PATH.write_text(
        __import__("json").dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def reload_story_length() -> int:
    """Re-read and update story length."""
    import config
    config.STORY_LENGTH = _load_story_length()
    return config.STORY_LENGTH


# ── DeepSeek API ────────────────────────────────────────────────────
DEEPSEEK_API_KEY = _load_api_key()
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = _load_model()
STORY_LENGTH = _load_story_length()

# ── Obsidian live export ────────────────────────────────────────────
# Path to an Obsidian vault folder.  When set, the engine writes
# per-chapter .md files directly into this vault after every turn.
# Obsidian auto-refreshes — open the vault to read the story in real-time.
# Set via CLI: /obsidian, or edit obsidian_path.json manually.
OBSIDIAN_PATH_FILE = DATA_DIR / "obsidian_path.json"

def _load_obsidian_path() -> str:
    if OBSIDIAN_PATH_FILE.exists():
        try:
            data = __import__("json").loads(OBSIDIAN_PATH_FILE.read_text(encoding="utf-8"))
            return data.get("vault_path", "")
        except Exception:
            pass
    return ""

def save_obsidian_path(path: str) -> None:
    OBSIDIAN_PATH_FILE.parent.mkdir(parents=True, exist_ok=True)
    OBSIDIAN_PATH_FILE.write_text(
        __import__("json").dumps({"vault_path": path.strip()}, indent=2),
        encoding="utf-8",
    )

OBSIDIAN_VAULT_PATH = _load_obsidian_path()

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
