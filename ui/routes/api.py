"""JSON API endpoints for the React frontend."""
from fastapi import APIRouter, Form, Query
from fastapi.responses import JSONResponse
import os

from engine.run import step
from engine import io_utils
from engine import save_manager
from engine.memory import load_memory, get_char_stats_for_ui, get_faction_stats_for_ui
from engine.deepseek_client import call_deepseek, DeepSeekError
import config

router = APIRouter(prefix="/api", tags=["api"])

_REL_METRICS = ("trust", "affection", "respect", "dependence", "hostility", "attraction")


def _merge_characters_with_memory(raw_chars: dict, mem_chars: dict, faction_map: dict) -> dict[str, dict]:
    """Merge session characters with memory metrics for API responses."""
    result: dict[str, dict] = {}
    for key, sc in raw_chars.items():
        name = sc.get("name", key)
        mem = mem_chars.get(name, {})
        trust = mem.get("trust", 0.5)
        trust_pct = round(trust * 100)
        merged = {
            **sc,
            "trust": trust,
            "trust_pct": trust_pct,
            "flags": mem.get("flags", []),
            "tier": mem.get("tier", ""),
            "faction": faction_map.get(name, mem.get("faction", "")),
        }
        for metric in _REL_METRICS:
            if metric in mem and isinstance(mem[metric], (int, float)):
                merged[metric] = round(float(mem[metric]) * 100)
        merged["affection"] = merged.get("affection", trust_pct)
        result[key] = merged
    return result


@router.get("/game-state")
async def api_game_state():
    """Return current game state as JSON (read-only, no side effects).

    If the game has not started yet (no history), returns a 'not_started'
    flag so the frontend can prompt the user to call POST /api/start.
    """
    from fastapi.responses import JSONResponse

    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    except Exception:
        return JSONResponse({"error": "没有活动中的游戏，请先创建故事"}, status_code=404)

    history = state.get("history", [])
    if not history:
        # Game not started — return minimal state, no AI call
        chars_with_trust: dict[str, dict] = {}
        raw_chars = state.get("characters", {})
        for key, sc in raw_chars.items():
            chars_with_trust[key] = {**sc, "trust": 0.5, "trust_pct": 50, "flags": [], "tier": ""}
        return JSONResponse({
            "not_started": True,
            "story": "",
            "options": [],
            "state": {
                "turn": 0,
                "status": state.get("status", "SETUP"),
                "scene": state.get("scene", ""),
                "characters": chars_with_trust,
                "factions": [],
                "force_event_pending": False,
                "chapter": state.get("chapter", 1),
            },
        })

    last = history[-1]
    story = last.get("story", last.get("summary", ""))
    options = last.get("options", [])
    raw_chars = state.get("characters", {})

    # Merge trust data from memory.json into characters
    try:
        memory = load_memory()
        mem_chars = memory.get("characters", {})
        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
        world_chars = world_pack.get("world", {}).get("characters", [])
        faction_map = {wc["name"]: wc.get("faction", "") for wc in world_chars if "name" in wc}
    except Exception:
        mem_chars = {}
        faction_map = {}

    chars_with_trust = _merge_characters_with_memory(raw_chars, mem_chars, faction_map)

    # Faction data
    factions_data: list[dict] = []
    try:
        factions_data = get_faction_stats_for_ui(memory)
    except Exception:
        pass

    return JSONResponse({
        "story": story,
        "options": options,
        "state": {
            "turn": state.get("turn", 0),
            "status": state.get("status", "SETUP"),
            "scene": state.get("scene", ""),
            "characters": chars_with_trust,
            "factions": factions_data,
            "force_event_pending": state.get("force_event_pending", False),
            "chapter": state.get("chapter", 1),
        },
    })


@router.post("/start")
async def api_start_game():
    """Generate the opening scene (POST — has side effects)."""
    from fastapi.responses import JSONResponse
    from engine.run import step, get_last_step_error

    if not config.DEEPSEEK_API_KEY:
        return JSONResponse(
            {"error": "未配置 DeepSeek API Key，请先在设置页填写"},
            status_code=400,
        )

    result = step(None)
    if result is None:
        err = get_last_step_error() or "AI 生成失败，请重试"
        return JSONResponse({"error": err}, status_code=500)

    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    except Exception:
        state = {}

    memory = load_memory()
    mem_chars = memory.get("characters", {})
    try:
        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
        world_chars = world_pack.get("world", {}).get("characters", [])
        faction_map = {wc["name"]: wc.get("faction", "") for wc in world_chars if "name" in wc}
    except Exception:
        faction_map = {}

    chars_with_trust = _merge_characters_with_memory(state.get("characters", {}), mem_chars, faction_map)

    # Faction data (consistent with /api/game-state)
    factions_data: list[dict] = []
    try:
        factions_data = get_faction_stats_for_ui(memory)
    except Exception:
        pass

    return JSONResponse({
        "story": result["story"],
        "options": result["options"],
        "state": {
            "turn": state.get("turn", result.get("turn", 1)),
            "status": state.get("status", result.get("status", "SETUP")),
            "scene": state.get("scene", result.get("scene", "")),
            "characters": chars_with_trust,
            "factions": factions_data,
            "force_event_pending": False,
            "chapter": state.get("chapter", 1),
        },
    })


@router.get("/npcs")
async def api_npcs():
    """Return all characters with full data as JSON."""
    from fastapi.responses import JSONResponse
    try:
        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
        memory = load_memory()
    except Exception:
        return JSONResponse({"characters": [], "stats": {}}, status_code=200)

    chars = world_pack.get("world", {}).get("characters", [])
    mem_chars = memory.get("characters", {})

    result = []
    for ch in chars:
        name = ch.get("name", "")
        mem = mem_chars.get(name, {})
        trust_val = mem.get("trust", 0.5)
        result.append({
            "name": name,
            "isMain": ch.get("is_main", False),
            "role_tags": ch.get("role_tags", []),
            "personality_tags": ch.get("personality_tags", []),
            "appearance": ch.get("appearance", ""),
            "relationship": ch.get("relationship", []),
            "goal": ch.get("goal", ""),
            "secret": ch.get("secret", ""),
            "background": ch.get("background", ""),
            "special_ability": ch.get("special_ability", ""),
            "faction": ch.get("faction", ""),
            "trust": trust_val,
            "trust_pct": round(trust_val * 100),
            "flags": mem.get("flags", []),
        })

    stats = {
        "total": len(result),
        "main": sum(1 for c in result if c["isMain"]),
        "npc": sum(1 for c in result if not c["isMain"]),
        "avg_trust": int(sum(c["trust_pct"] for c in result) / max(1, len(result))),
    }

    return JSONResponse({"characters": result, "stats": stats})


@router.post("/npcs/generate")
async def api_generate_npc(role_hint: str = Form("")):
    """AI-generate a new NPC and auto-add to world/state/memory."""
    from fastapi.responses import JSONResponse
    from engine.deepseek_client import call_deepseek, DeepSeekError

    system = "你是一个 Galgame 角色生成器。根据已有故事设定，生成一个与现有角色不重复的新NPC。只输出JSON。"
    user = f"为当前故事生成一个新角色。角色定位参考：{role_hint or '重要配角'}。\n\n输出JSON格式：{{\"name\":\"角色名\",\"role_tags\":[\"身份\"],\"personality_tags\":[\"性格1\",\"性格2\",\"性格3\"],\"appearance\":\"外貌特征（10~30字）\",\"relationship\":[\"与主角关系\"],\"goal\":\"角色目标\",\"secret\":\"隐藏秘密\"}}"

    try:
        result = call_deepseek(system, user, temperature=0.9, max_tokens=config.MAX_TOKENS, skip_validation=True)
    except DeepSeekError as exc:
        return JSONResponse({"error": f"AI 生成失败: {exc}"}, status_code=500)

    # Normalize result
    name = result.get("name", "新角色")
    ch = {
        "name": name,
        "is_main": False,
        "role_tags": result.get("role_tags", []) if isinstance(result.get("role_tags"), list) else [result.get("role_tags", "")] if result.get("role_tags") else [],
        "personality_tags": result.get("personality_tags", []) if isinstance(result.get("personality_tags"), list) else [],
        "appearance": result.get("appearance", ""),
        "relationship": result.get("relationship", []) if isinstance(result.get("relationship"), list) else [result.get("relationship", "")] if result.get("relationship") else [],
        "goal": result.get("goal", ""),
        "secret": result.get("secret", ""),
        "background": result.get("background", ""),
        "special_ability": result.get("special_ability", ""),
    }

    # Add to world_pack
    try:
        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
        world_pack.setdefault("world", {}).setdefault("characters", []).append(ch)
        io_utils.write_yaml(config.WORLD_PACK_PATH, world_pack)
    except Exception:
        pass

    # Add to session state
    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
        chars = state.get("characters", {})
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        key = letters[len(chars)] if len(chars) < 26 else f"X{len(chars)}"
        chars[key] = {
            "name": name,
            "role": " / ".join(ch["role_tags"]) if ch["role_tags"] else "",
            "level": "L0",
            "relation": ch["relationship"][0] if ch["relationship"] else "陌生人",
            "note": f"外貌：{ch['appearance']}" if ch.get("appearance") else "",
        }
        io_utils.write_yaml(config.SESSION_STATE_PATH, state)
    except Exception:
        pass

    # Add to memory
    try:
        memory = load_memory()
        memory.setdefault("characters", {})[name] = {
            "trust": 0.5,
            "flags": [],
            "relationship": ch["relationship"][0] if ch["relationship"] else "",
        }
        if ch.get("secret"):
            memory["characters"][name].setdefault("flags", []).append(f"隐藏秘密：{ch['secret']}")
        save_memory(memory)
    except Exception:
        pass

    return JSONResponse(ch)


@router.get("/history")
async def api_history():
    """Return the full story history as JSON."""
    from fastapi.responses import JSONResponse
    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    except Exception:
        return JSONResponse({"turns": []})

    history = state.get("history", [])
    turns = []
    for h in history:
        turns.append({
            "turn": h.get("turn", 0),
            "story": h.get("story", ""),
            "options": h.get("options", []),
            "choice": h.get("choice", ""),
            "status": h.get("status", ""),
            "scene": h.get("scene", ""),
        })
    return JSONResponse({"turns": turns, "total": len(turns)})


@router.get("/dashboard")
async def api_dashboard():
    """Return dashboard stats + analytics as JSON."""
    from fastapi.responses import JSONResponse
    from engine.analytics import compute_all

    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
        memory = load_memory()
        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
        graph = io_utils.read_json(config.STORY_GRAPH_PATH)
    except Exception:
        return JSONResponse({"error": "暂无数据"}, status_code=200)

    # Basic stats
    turn = state.get("turn", 0)
    status = state.get("status", "SETUP")
    scene = state.get("scene", "")
    chapter = state.get("chapter", 1)

    # Characters
    chars = world_pack.get("world", {}).get("characters", [])
    mem_chars = memory.get("characters", {})

    # Word count estimate from chapter.md
    word_count = 0
    try:
        text = config.CHAPTER_PATH.read_text(encoding="utf-8")
        word_count = len(text)
    except Exception:
        pass

    # Graph stats
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])
    branch_count = len(edges)

    # Character trust
    char_trust = []
    for ch in chars:
        name = ch.get("name", "")
        mem = mem_chars.get(name, {})
        char_trust.append({
            "name": name,
            "trust_pct": int(mem.get("trust", 0.5) * 100),
            "relation": ch.get("relationship", [""])[0] if ch.get("relationship") else "",
            "flags": mem.get("flags", []),
        })

    # API usage
    api_calls = 0
    total_tokens = 0
    try:
        if config.API_USAGE_PATH.exists():
            import json as _json
            with open(config.API_USAGE_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = _json.loads(line)
                    api_calls += 1
                    total_tokens += entry.get("total_tokens", 0)
    except Exception:
        pass

    # Full analytics from analytics engine
    analytics = compute_all()

    return JSONResponse({
        "turn": turn,
        "status": status,
        "scene": scene,
        "chapter": chapter,
        "word_count": word_count,
        "character_count": len(chars),
        "branch_count": branch_count,
        "node_count": len(nodes),
        "api_calls": api_calls,
        "total_tokens": total_tokens,
        "characters": char_trust,
        "history": state.get("history", [])[-5:],
        "analytics": analytics,
    })


@router.post("/next")
async def api_next_turn(choice: str = Form("A")):
    """Advance the game with a choice and return new state as JSON."""
    from fastapi.responses import JSONResponse
    from engine.run import step

    try:
        result = step(choice)
    except Exception:
        import logging
        logging.getLogger("api").error("next_turn failed", exc_info=True)
        return JSONResponse({"error": "AI 生成失败，请重试"}, status_code=500)

    if result is None:
        return JSONResponse({"error": "AI 生成失败，请重试"}, status_code=500)

    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    except Exception:
        state = {}

    # Merge trust data into characters (consistent with /api/game-state)
    memory = load_memory()
    mem_chars = memory.get("characters", {})
    try:
        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
        world_chars = world_pack.get("world", {}).get("characters", [])
        faction_map = {wc["name"]: wc.get("faction", "") for wc in world_chars if "name" in wc}
    except Exception:
        faction_map = {}
    chars_with_trust = _merge_characters_with_memory(state.get("characters", {}), mem_chars, faction_map)

    # Faction data (consistent with /api/game-state)
    factions_data: list[dict] = []
    try:
        factions_data = get_faction_stats_for_ui(memory)
    except Exception:
        pass

    return JSONResponse({
        "story": result["story"],
        "options": result["options"],
        "state": {
            "turn": state.get("turn", result.get("turn", 0)),
            "status": state.get("status", result.get("status", "SETUP")),
            "scene": state.get("scene", result.get("scene", "")),
            "characters": chars_with_trust,
            "factions": factions_data,
            "force_event_pending": state.get("force_event_pending", False),
            "chapter": state.get("chapter", 1),
        },
    })



@router.get("/settings-status")
async def api_settings_status():
    """Whether a DeepSeek API key is saved locally (not env var)."""
    return JSONResponse({"configured": bool(config._read_stored_api_key())})


@router.post("/settings-key")
async def api_save_settings_key(api_key: str = Form(...)):
    """Save API key from first-run prompt or settings."""
    key = api_key.strip()
    if not key:
        return JSONResponse({"error": "API Key 不能为空"}, status_code=400)
    config.save_api_key(key)
    config.reload_api_key()
    return JSONResponse({"ok": True, "configured": True})


@router.get("/settings")
async def api_get_settings():
    """Engine/API settings for the React settings page."""
    from ui.routes.settings import settings_payload
    return JSONResponse(settings_payload())


@router.post("/settings")
async def api_save_settings(
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
    """Save engine settings from the React settings page."""
    from ui.routes.settings import apply_engine_settings
    return JSONResponse(apply_engine_settings(
        api_key=api_key,
        model=model,
        story_length=story_length,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        stream=stream,
        max_context_messages=max_context_messages,
        auto_compress=auto_compress,
        compress_threshold=compress_threshold,
    ))


@router.post("/settings/clear")
async def api_clear_settings_key():
    """Clear stored API key."""
    from config import clear_api_key, reload_api_key
    clear_api_key()
    reload_api_key()
    from ui.routes.settings import settings_payload
    return JSONResponse(settings_payload())

