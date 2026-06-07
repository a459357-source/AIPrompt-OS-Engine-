"""Main game routes: SPA root, legacy debug page, save/load utilities."""
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse

from engine.run import step
from engine import io_utils, save_manager
from engine.memory import load_memory, get_char_stats_for_ui
from ui.templates import _render_template
import config

router = APIRouter(tags=["game"])


def _get_world_title() -> tuple[str, str]:
    """Read world_pack.yaml and return (title, subtitle)."""
    try:
        wp = io_utils.read_yaml(config.WORLD_PACK_PATH)
        w = wp.get("world", {})
        title = w.get("title", "")
        genre = w.get("genre", "")
        return title, genre
    except Exception:
        return "", ""

@router.get("/")
async def index():
    """Serve React SPA at root."""
    if config.has_bundled_frontend():
        return FileResponse(config.FRONTEND_DIST / "index.html")
    return RedirectResponse(url=config.frontend_url(), status_code=302)


@router.get("/legacy", response_class=HTMLResponse)
async def legacy_index():
    """Legacy HTML game page (kept for debugging / bookmark compat)."""
    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    except Exception:
        state = {}

    turn = state.get("turn", 0)
    status = state.get("status", "SETUP")
    scene = state.get("scene", "初始")

    history = state.get("history", [])
    if history:
        last = history[-1]
        story = last.get("story", last.get("summary", ""))
        options = last.get("options", [])
    else:
        result = step(None)
        if result is not None:
            try:
                state = io_utils.read_yaml(config.SESSION_STATE_PATH)
            except Exception:
                pass
            turn = state.get("turn", 1)
            status = state.get("status", "SETUP")
            scene = state.get("scene", "初始")
            story = result["story"]
            options = result["options"]
        else:
            world_title = _get_world_title()[0] or "Galgame"
            world_scene = scene or "初始场景"
            story = f"欢迎来到 **{world_title}**。\n\n当前场景：{world_scene}\n\n❌ AI 生成失败，请检查 API Key 后刷新页面。"
            state_chars = state.get("characters", {})
            char_names = [c.get("name", "") for c in state_chars.values() if c.get("name")]
            options = [
                "调查周围环境，寻找线索",
                "与同伴交流当前情况",
                "检查装备和可用资源",
                "深入探索前方的未知区域",
            ]
            if len(char_names) >= 1:
                options[1] = f"与{char_names[0]}商议接下来的行动"
            if len(char_names) >= 2:
                options[2] = f"向{char_names[1]}询问她的看法"

    memory = load_memory()
    try:
        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
    except Exception:
        world_pack = {}
    char_stats = get_char_stats_for_ui(state, memory, world_pack)
    title, subtitle = _get_world_title()

    return _render_template(
        story=story,
        options=options,
        turn=turn,
        status=status,
        scene=scene,
        characters=state.get("characters"),
        force_event=state.get("force_event_pending", False),
        char_stats=char_stats,
        title=title,
        subtitle=subtitle,
        chapter=state.get("chapter", 1),
    )


# ── Save / Load routes ────────────────────────────────────────────

@router.get("/save")
async def save_game(slot: str = Query("autosave", min_length=1)):
    """
    Save the current game state to a slot (autosave, slot1, slot2, slot3).
    Returns JSON summary.
    """
    from fastapi.responses import JSONResponse

    valid_slots = set(config.all_save_slots())
    if slot not in valid_slots:
        return JSONResponse(
            {"error": f"无效存档槽: {slot}，可选: {', '.join(sorted(valid_slots))}"},
            status_code=400,
        )

    result = save_manager.save(slot)
    if result is None:
        return JSONResponse({"error": "保存失败"}, status_code=500)

    # Don't overwrite autosave with a manual save to autosave slot
    return JSONResponse(result)


@router.get("/load")
async def load_game(slot: str = Query("autosave", min_length=1)):
    """
    Load a saved game state from a slot.
    Redirects to the main page after loading.
    """
    from fastapi.responses import JSONResponse, RedirectResponse

    valid_slots = set(config.all_save_slots())
    if slot not in valid_slots:
        return JSONResponse(
            {"error": f"无效存档槽: {slot}，可选: {', '.join(sorted(valid_slots))}"},
            status_code=400,
        )

    if not save_manager.save_exists(slot):
        return JSONResponse(
            {"error": f"存档槽 '{slot}' 为空，没有存档数据。"},
            status_code=404,
        )

    result = save_manager.load(slot)
    if result is None:
        return JSONResponse({"error": "读取存档失败"}, status_code=500)

    # Redirect to main page to show loaded state
    return RedirectResponse(url=config.frontend_url("/game"), status_code=303)


@router.get("/saves")
async def list_saves():
    """Return the list of all save slots as JSON."""
    from fastapi.responses import JSONResponse
    return JSONResponse(save_manager.list_saves())


@router.get("/reset", response_class=HTMLResponse)
async def reset():
    """Reset the session state to the world's factory defaults."""
    from engine import io_utils
    from fastapi.responses import RedirectResponse

    # Try to restore from factory snapshot (saved at world creation)
    if config.WORLD_INIT_PATH.exists():
        try:
            init = io_utils.read_json(config.WORLD_INIT_PATH)
            io_utils.write_yaml(config.SESSION_STATE_PATH, init["state"])
            io_utils.write_json(config.STORY_GRAPH_PATH, init["graph"])
            io_utils.write_json(config.MEMORY_PATH, init["memory"])
            config.CHAPTER_PATH.write_text("", encoding="utf-8")
            return RedirectResponse(url=config.frontend_url("/game"), status_code=303)
        except Exception:
            pass

    # Fallback: hardcoded defaults (only used if no world_init.json exists)
    initial_state = {
        "scene": "回声号 — 舰桥",
        "status": "SETUP",
        "turn": 0,
        "characters": {
            "A": {"name": "林夜", "role": "调查船船长", "level": "L0", "relation": "初识", "note": "冷静、理性，背负过去的秘密"},
            "B": {"name": "艾琳", "role": "考古语言学家", "level": "L0", "relation": "初识", "note": "热情、好奇，对星痕有特殊的感知力"},
        },
        "history": [],
        "force_event_pending": False,
        "chapter": 1,
    }
    io_utils.write_yaml(config.SESSION_STATE_PATH, initial_state)
    initial_graph = {
        "nodes": {"0": {"turn": 0, "text": "初始场景：回声号舰桥", "scene": "回声号 — 舰桥", "status": "SETUP", "choices": {}, "parent": None, "choice_taken": None}},
        "current_node": "0", "edges": [],
    }
    io_utils.write_json(config.STORY_GRAPH_PATH, initial_graph)
    initial_memory = {
        "characters": {
            "林夜": {"trust": 0.5, "flags": [], "relationship": "船长，初识"},
            "艾琳": {"trust": 0.5, "flags": [], "relationship": "考古语言学家，初识"},
        },
        "world_flags": [], "global_trust": 0.5,
    }
    io_utils.write_json(config.MEMORY_PATH, initial_memory)
    config.CHAPTER_PATH.write_text("", encoding="utf-8")
    return RedirectResponse(url=config.frontend_url("/game"), status_code=303)


