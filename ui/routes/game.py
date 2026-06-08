"""Main game routes: SPA root, save/load utilities."""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse

from engine import save_manager
import config

router = APIRouter(tags=["game"])


@router.get("/")
async def index():
    """Serve React SPA at root."""
    if config.has_bundled_frontend():
        return FileResponse(config.FRONTEND_DIST / "index.html")
    return RedirectResponse(url=config.frontend_url(), status_code=302)


# ── Save / Load routes ────────────────────────────────────────────

@router.get("/save")
async def save_game(slot: str = Query("autosave", min_length=1)):
    """
    Save the current game state to a slot (autosave, slot1, slot2, slot3).
    Returns JSON summary.
    """
    valid_slots = set(config.all_save_slots())
    if slot not in valid_slots:
        return JSONResponse(
            {"error": f"无效存档槽: {slot}，可选: {', '.join(sorted(valid_slots))}"},
            status_code=400,
        )

    result = save_manager.save(slot)
    if result is None:
        return JSONResponse({"error": "保存失败"}, status_code=500)

    return JSONResponse(result)


@router.get("/load")
async def load_game(slot: str = Query("autosave", min_length=1)):
    """
    Load a saved game state from a slot.
    Redirects to the main page after loading.
    """
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

    return RedirectResponse(url=config.frontend_url("/game"), status_code=303)


@router.get("/saves")
async def list_saves():
    """Return the list of all save slots as JSON."""
    return JSONResponse(save_manager.list_saves())


@router.get("/reset")
async def reset():
    """Reset the session state to the world's factory defaults."""
    from engine import io_utils

    if config.WORLD_INIT_PATH.exists():
        try:
            from engine.state_store import commit_bundle
            from engine.objective_system import ensure_objectives, sync_main_objective_progress
            from engine.plot_director import init_plot_state, save_plot_state

            init = io_utils.read_json(config.WORLD_INIT_PATH)
            state = init["state"]
            memory = init["memory"]
            graph = init["graph"]
            from engine.relationship_core import init_graph_from_world
            from engine.relationship_dynamics import empty_dynamics_store
            from engine.relationship_memory import empty_store

            rel_graph = init.get("relationship_graph")
            rel_mem = init.get("relationship_memory")
            rel_dyn = init.get("relationship_dynamics")
            if not (isinstance(rel_graph, dict) and rel_graph.get("edges") is not None):
                world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
                rel_graph = init_graph_from_world(world_pack, memory, state, persist=False)
            if not (isinstance(rel_mem, dict) and rel_mem.get("edges") is not None):
                rel_mem = empty_store()
            if not (isinstance(rel_dyn, dict) and rel_dyn.get("edges") is not None):
                rel_dyn = empty_dynamics_store()

            commit_bundle(
                state, memory, graph, chapter="",
                relationship=rel_graph,
                relationship_memory=rel_mem,
                relationship_dynamics=rel_dyn,
            )

            plot_state = init.get("plot_state")
            if isinstance(plot_state, dict) and plot_state.get("main_plot"):
                save_plot_state(plot_state, persist=True)
            else:
                world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
                plot_state = init_plot_state(world_pack)

            world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
            ensure_objectives(state, world_pack, plot_state)
            sync_main_objective_progress(state, plot_state)
            io_utils.write_yaml(config.SESSION_STATE_PATH, state)

            return RedirectResponse(url=config.frontend_url("/game"), status_code=303)
        except Exception:
            pass

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
    from engine.state_store import commit_bundle
    initial_graph = {
        "nodes": {"0": {"turn": 0, "text": "初始场景：回声号舰桥", "scene": "回声号 — 舰桥", "status": "SETUP", "choices": {}, "parent": None, "choice_taken": None}},
        "current_node": "0", "edges": [],
    }
    initial_memory = {
        "characters": {
            "林夜": {"trust": 0.5, "flags": [], "relationship": "船长，初识"},
            "艾琳": {"trust": 0.5, "flags": [], "relationship": "考古语言学家，初识"},
        },
        "world_flags": [], "global_trust": 0.5,
    }
    commit_bundle(initial_state, initial_memory, initial_graph, chapter="")
    return RedirectResponse(url=config.frontend_url("/game"), status_code=303)
