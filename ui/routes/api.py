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
_APP_DISPLAY_NAME = "World Builder"


def _read_world_title() -> str:
    """Story title from world_pack (browser tab / meta)."""
    try:
        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
        return str((world_pack.get("world") or {}).get("title") or "").strip()
    except Exception:
        return ""


def _merge_characters_with_memory(raw_chars: dict, mem_chars: dict, faction_map: dict) -> dict[str, dict]:
    """Merge session characters with memory metrics for API responses."""
    from engine.character_registry import dedupe_characters_by_name

    raw_chars = dedupe_characters_by_name(raw_chars)
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


def _objectives_for_game(state: dict, *, persist_migrate: bool = False) -> dict:
    from engine.objective_system import ensure_objectives, visible_for_game

    try:
        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
    except Exception:
        world_pack = {}
    needs_migrate = not state.get("objectives") or not isinstance(state.get("objectives"), dict)
    ensure_objectives(state, world_pack)
    if persist_migrate and needs_migrate:
        io_utils.write_yaml(config.SESSION_STATE_PATH, state)
    return visible_for_game(state)


def _game_state_payload(state: dict, *, not_started: bool = False) -> dict:
    """Build JSON payload for GET /api/game-state and idempotent POST /api/start."""
    if not_started or not state.get("history"):
        from engine.character_registry import dedupe_characters_by_name

        chars_with_trust: dict[str, dict] = {}
        raw_chars = dedupe_characters_by_name(state.get("characters", {}))
        for key, sc in raw_chars.items():
            chars_with_trust[key] = {**sc, "trust": 0.5, "trust_pct": 50, "flags": [], "tier": ""}
        payload = {
            "story": "",
            "options": [],
            "state": {
                "turn": state.get("turn", 0),
                "status": state.get("status", "SETUP"),
                "scene": state.get("scene", ""),
                "characters": chars_with_trust,
                "factions": [],
                "force_event_pending": state.get("force_event_pending", False),
                "chapter": state.get("chapter", 1),
                "objectives": _objectives_for_game(state, persist_migrate=True),
            },
        }
        if not_started:
            payload["not_started"] = True
        payload["world_title"] = _read_world_title()
        return payload

    history = state.get("history", [])
    last = history[-1]
    story = last.get("story", last.get("summary", ""))
    options = last.get("options", [])
    raw_chars = state.get("characters", {})

    try:
        memory = load_memory()
        mem_chars = memory.get("characters", {})
        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
        world_chars = world_pack.get("world", {}).get("characters", [])
        faction_map = {wc["name"]: wc.get("faction", "") for wc in world_chars if "name" in wc}
    except Exception:
        memory = {}
        mem_chars = {}
        faction_map = {}

    chars_with_trust = _merge_characters_with_memory(raw_chars, mem_chars, faction_map)

    factions_data: list[dict] = []
    try:
        factions_data = get_faction_stats_for_ui(memory)
    except Exception:
        pass

    payload = {
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
            "objectives": _objectives_for_game(state, persist_migrate=True),
        },
    }
    if not config.ADULT_MODE:
        payload["suggest_adult_mode"] = config.suggest_adult_mode_for_options(options)
    payload["world_title"] = _read_world_title()
    return payload


@router.get("/world-meta")
async def api_world_meta():
    """Lightweight story title for document.title and UI chrome."""
    title = _read_world_title()
    return JSONResponse({"world_title": title, "app_name": _APP_DISPLAY_NAME})


@router.get("/game-state")
async def api_game_state():
    """Return current game state as JSON (read-only, no side effects).

    If the game has not started yet (no history), returns a 'not_started'
    flag so the frontend can prompt the user to call POST /api/start.
    """
    from fastapi.responses import JSONResponse

    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH, use_cache=False)
    except Exception:
        return JSONResponse({"error": "没有活动中的游戏，请先创建故事"}, status_code=404)

    if not state.get("history"):
        return JSONResponse(_game_state_payload(state, not_started=True))

    return JSONResponse(_game_state_payload(state))


@router.post("/start")
async def api_start_game():
    """Generate the opening scene (POST — has side effects).

    Idempotent: if history already exists, returns current state without a new AI call.
    If opening generation is already in flight, returns partial story + generating flag.
    """
    from ui.turn_stream import turn_response, get_generation_status

    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH, use_cache=False)
    except Exception:
        return JSONResponse({"error": "没有活动中的游戏，请先创建故事"}, status_code=404)

    if state.get("history"):
        return JSONResponse(_game_state_payload(state))

    gen = get_generation_status()
    if gen.get("active"):
        payload = _game_state_payload(state, not_started=True)
        payload["generating"] = True
        if gen.get("story"):
            payload["story"] = gen["story"]
        return JSONResponse(payload)

    return turn_response(None, opening=True)


@router.post("/next")
async def api_next_turn(choice: str = Form("A")):
    """Advance the game with a choice and return new state as JSON or SSE."""
    from ui.turn_stream import turn_response

    return turn_response(choice)


@router.post("/cancel-generation")
async def api_cancel_generation():
    """Request cancellation of in-flight turn generation."""
    from ui.turn_stream import cancel_active_generation

    return JSONResponse(cancel_active_generation())


@router.get("/generation-status")
async def api_generation_status():
    """Partial story for disconnect recovery."""
    from ui.turn_stream import get_generation_status

    return JSONResponse(get_generation_status())


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

    # Add to session state + memory (single commit; world_pack stays separate)
    try:
        from engine.state_store import load_runtime, commit_runtime
        runtime = load_runtime(clear_cache=True)
        state = runtime.session
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
        runtime.session = state
        memory = runtime.memory
        memory.setdefault("characters", {})[name] = {
            "trust": 0.5,
            "flags": [],
            "relationship": ch["relationship"][0] if ch["relationship"] else "",
        }
        if ch.get("secret"):
            memory["characters"][name].setdefault("flags", []).append(f"隐藏秘密：{ch['secret']}")
        runtime.memory = memory
        commit_runtime(runtime)
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

    from engine.dashboard import _build_mermaid
    from engine.plot_director import dashboard_payload as plot_dashboard_payload, ensure_plot_state
    from engine.objective_system import dashboard_payload as objectives_dashboard_payload, ensure_objectives

    mermaid_src = _build_mermaid(nodes, edges, mem_chars)
    plot_state = ensure_plot_state(world_pack)
    plot_director = plot_dashboard_payload(plot_state, state, world_pack)
    ensure_objectives(state, world_pack, plot_state)
    objectives = objectives_dashboard_payload(state)

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
        "story_graph": {
            "nodes": nodes,
            "edges": edges,
            "mermaid": mermaid_src,
            "current_node": graph.get("current_node"),
        },
        "plot_director": plot_director,
        "objectives": objectives,
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
    try:
        config.save_api_key(key)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
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
    model: str | None = Form(default=None),
    story_length: int | None = Form(default=None),
    max_tokens: int | None = Form(default=None),
    temperature: float | None = Form(default=None),
    top_p: float | None = Form(default=None),
    stream: int | None = Form(default=None),
    max_context_messages: int | None = Form(default=None),
    auto_compress: int | None = Form(default=None),
    compress_threshold: int | None = Form(default=None),
):
    """Save engine settings from the React settings page."""
    from ui.routes.settings import apply_engine_settings, apply_game_gen_settings

    gen_only = (
        not api_key.strip()
        and model is None
        and max_tokens is None
        and stream is None
        and max_context_messages is None
        and auto_compress is None
        and any(x is not None for x in (story_length, temperature, top_p, compress_threshold))
    )
    if gen_only:
        payload = apply_game_gen_settings(
            story_length=story_length,
            temperature=temperature,
            top_p=top_p,
            compress_threshold=compress_threshold,
        )
        return JSONResponse({"ok": True, **payload})

    try:
        payload = apply_engine_settings(
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
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse(payload)


@router.post("/settings/clear")
async def api_clear_settings_key():
    """Clear stored API key."""
    from config import clear_api_key, reload_api_key
    clear_api_key()
    reload_api_key()
    from ui.routes.settings import settings_payload
    return JSONResponse(settings_payload())


@router.get("/game-settings")
@router.get("/game-settings/")
async def api_get_game_settings():
    """Generation quick settings for the Game page."""
    from ui.routes.settings import game_settings_payload
    return JSONResponse(game_settings_payload())


@router.post("/game-settings")
@router.post("/game-settings/")
async def api_set_game_settings(
    story_length: int | None = Form(default=None),
    temperature: float | None = Form(default=None),
    top_p: float | None = Form(default=None),
    compress_threshold: int | None = Form(default=None),
    option_count: int | None = Form(default=None),
    narrative_pov: str | None = Form(default=None),
    style_preference: str | None = Form(default=None),
    repetition_check: str | None = Form(default=None),
    adult_mode: str | None = Form(default=None),
    adult_unlock_key: str | None = Form(default=None),
    adult_profile: str | None = Form(default=None),
    adult_theme: str | None = Form(default=None),
    visual_theme: str | None = Form(default=None),
    expression_style: str | None = Form(default=None),
    content_weights: str | None = Form(default=None),
):
    """Update generation quick settings from the Game page."""
    from ui.routes.settings import apply_game_gen_settings
    import json as _json

    # Parse adult_mode from form string
    _adult_mode = None
    if adult_mode is not None:
        _adult_mode = adult_mode.lower() in ("true", "1", "on")

    # Parse content_weights from JSON string
    _content_weights = None
    if content_weights is not None:
        try:
            _content_weights = _json.loads(content_weights)
        except Exception:
            pass

    try:
        payload = apply_game_gen_settings(
            story_length=story_length,
            temperature=temperature,
            top_p=top_p,
            compress_threshold=compress_threshold,
            option_count=option_count,
            narrative_pov=narrative_pov,
            style_preference=style_preference,
            repetition_check=repetition_check,
            adult_mode=_adult_mode,
            adult_unlock_key=adult_unlock_key,
            adult_profile=adult_profile,
            adult_theme=adult_theme,
            visual_theme=visual_theme,
            expression_style=expression_style,
            content_weights=_content_weights,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    return JSONResponse({"ok": True, **payload})


@router.get("/app-settings")
@router.get("/app-settings/")
async def api_get_app_settings():
    from ui.routes.settings import app_settings_payload
    return JSONResponse(app_settings_payload())


@router.post("/app-settings")
@router.post("/app-settings/")
async def api_set_app_settings(
    auto_save_interval: int | None = Form(default=None),
    max_save_slots: int | None = Form(default=None),
    export_format: str | None = Form(default=None),
    auto_export: str | None = Form(default=None),
):
    from ui.routes.settings import apply_app_settings
    payload = apply_app_settings(
        auto_save_interval=auto_save_interval,
        max_save_slots=max_save_slots,
        export_format=export_format,
        auto_export=auto_export,
    )
    return JSONResponse({"ok": True, **payload})


@router.post("/supplement-lore")
async def api_supplement_lore(text: str = Form("")):
    """Analyze player supplement text and merge into world/state/memory."""
    from fastapi.responses import JSONResponse
    from engine.supplement_lore import supplement_lore
    from engine.deepseek_client import DeepSeekError

    try:
        result = supplement_lore(text)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except DeepSeekError as exc:
        return JSONResponse({"error": f"AI 分析失败: {exc}"}, status_code=500)
    except Exception as exc:
        return JSONResponse({"error": f"更新失败: {exc}"}, status_code=500)

    if not config.ADULT_MODE and config.is_clearly_adult_content(text):
        result["suggest_adult_mode"] = True

    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
        payload = _game_state_payload(state)
    except Exception:
        payload = {}

    return JSONResponse({**result, **payload})

