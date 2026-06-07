"""Main game pages: index, next_turn, save/load, graph, history, reset."""
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from engine.run import step
from engine import io_utils, save_manager
from engine.memory import load_memory, get_char_stats_for_ui
from engine.router import load_graph
from ui.obsidian_export import _generate_mermaid
from ui.templates import HTML_TEMPLATE
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

@router.get("/", response_class=HTMLResponse)
async def index():
    """Show the current story state with option buttons."""
    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    except Exception:
        state = {}

    turn = state.get("turn", 0)
    status = state.get("status", "SETUP")
    scene = state.get("scene", "初始")

    # Get last turn's options from session history (clean, no parsing needed)
    history = state.get("history", [])
    if history:
        last = history[-1]
        story = last.get("story", last.get("summary", ""))
        options = last.get("options", [])
    else:
        # No history — auto-generate the opening scene
        result = step(None)
        if result is not None:
            # Re-read state after step() modified it
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
            # AI generation failed — show static fallback
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


@router.get("/next", response_class=HTMLResponse)
async def next_turn(choice: str = Query(..., min_length=1, max_length=1)):
    """
    Advance the story with the player's choice (A/B/C/D).
    Returns the new story page.
    """
    # Accept A/B/C/D or free-text (URL-encoded)
    if choice not in ("A", "B", "C", "D"):
        # Free-text choice — pass through as-is
        pass

    result = step(choice)

    if result is None:
        return _render_template(
            error="❌ 生成失败，请确认 API key 已设置且网络正常。",
            turn=0, status="?", scene="?",
        )

    # Read updated state for character & force_event info
    try:
        updated_state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    except Exception:
        updated_state = {}

    memory = load_memory()
    try:
        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
    except Exception:
        world_pack = {}
    char_stats = get_char_stats_for_ui(updated_state, memory, world_pack)
    title, subtitle = _get_world_title()

    return _render_template(
        story=result["story"],
        options=result["options"],
        turn=result["turn"],
        status=result["status"],
        scene=result["scene"],
        characters=updated_state.get("characters", result.get("state", {}).get("characters")),
        force_event=updated_state.get("force_event_pending", False),
        char_stats=char_stats,
        title=title,
        subtitle=subtitle,
        chapter=updated_state.get("chapter", 1),
    )


# ── Save / Load routes ────────────────────────────────────────────

@router.get("/save")
async def save_game(slot: str = Query("autosave", min_length=1)):
    """
    Save the current game state to a slot (autosave, slot1, slot2, slot3).
    Returns JSON summary.
    """
    from fastapi.responses import JSONResponse

    valid_slots = {"autosave", "slot1", "slot2", "slot3"}
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

    valid_slots = {"autosave", "slot1", "slot2", "slot3"}
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
    return RedirectResponse(url="/", status_code=303)


@router.get("/saves")
async def list_saves():
    """Return the list of all save slots as JSON."""
    from fastapi.responses import JSONResponse
    return JSONResponse(save_manager.list_saves())


@router.get("/graph", response_class=HTMLResponse)
async def story_graph_page():
    """
    Render an interactive Mermaid.js story graph page.
    """
    from engine.router import load_graph
    from ui.obsidian_export import _generate_mermaid

    mermaid_lines = _generate_mermaid()
    mermaid_code = "\n".join(mermaid_lines)

    graph_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>剧情分支图 — Prompt OS Galgame</title>
<script src="/static/mermaid.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:"Segoe UI","Noto Sans SC",system-ui,sans-serif;background:#0d1117;color:#c9d1d9;min-height:100vh}}
.topbar{{display:flex;align-items:center;justify-content:space-between;padding:10px 24px;border-bottom:1px solid #21262d;background:#0d1117}}
.topbar h1{{font-size:1.15em;color:#58a6ff}}
.back-btn{{display:inline-block;padding:5px 14px;background:#1c2333;border:1px solid #58a6ff;border-radius:6px;color:#58a6ff;text-decoration:none;font-size:0.82em}}
.back-btn:hover{{background:#1a3a5c;color:#79c0ff}}
.content{{max-width:1100px;margin:0 auto;padding:16px 24px}}
.info{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px;margin-bottom:16px;font-size:0.82em;color:#8b949e;line-height:1.6}}
.mermaid{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:24px;overflow-x:auto}}
</style>
</head>
<body>
<div class="topbar">
    <h1>🌳 剧情分支图</h1>
    <a href="/" class="back-btn">← 返回游戏</a>
</div>
<div class="content">
    <div class="info">
        📖 每个节点代表一个剧情回合。边上的字母代表玩家在该节点的选择（A/B/C/D）。
    </div>
    <div class="mermaid">
{mermaid_code}
    </div>
</div>
<script>
    mermaid.initialize({{ startOnLoad: true, theme: 'dark' }});
</script>
</body>
</html>"""

    return graph_html


@router.get("/history", response_class=HTMLResponse)
async def history_page():
    """
    Show all past turns as a scrollable history log.
    """
    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    except Exception:
        state = {}

    history = state.get("history", [])
    turn = state.get("turn", 0)
    scene = state.get("scene", "")

    if not history:
        return HTMLResponse(
            HTML_TEMPLATE.replace("{{STORY}}", "尚无历史记录。")
            .replace("{{OPTIONS}}", "")
            .replace("{{STATE_ROW}}", "")
            .replace("{{SIDEBAR}}", "")
            .replace("{{ERROR}}", "")
        )

    blocks: list[str] = []
    for h in history:
        t = h.get("turn", "?")
        s = h.get("status", "?")
        sc = h.get("scene", "?")
        story = h.get("story", h.get("summary", ""))
        choice = h.get("choice", "")

        status_cn = {"SETUP": "序章", "BUILD": "展开", "TENSION": "张力", "CLIMAX": "高潮", "COOLDOWN": "余韵"}.get(s, s)

        blocks.append(
            f'<div style="margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid #30363d;">'
            f'<div style="color:#8b949e;font-size:0.8em;margin-bottom:6px;">'
            f'📖 第{t}轮 · {status_cn} · {sc}'
            f'{(" · 选择: " + choice) if choice else ""}'
            f'</div>'
            f'<div style="line-height:1.8;white-space:pre-wrap;">{story}</div>'
            f'</div>'
        )

    history_html = "\n".join(blocks)

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta charset="UTF-8">
    <title>历史回顾 — Prompt OS Galgame</title>
    <style>
        *{{box-sizing:border-box;margin:0;padding:0}}
        body{{font-family:"Segoe UI","Noto Sans SC",system-ui,sans-serif;background:#0d1117;color:#c9d1d9;min-height:100vh}}
        .topbar{{display:flex;align-items:center;justify-content:space-between;padding:10px 24px;border-bottom:1px solid #21262d;background:#0d1117}}
        .topbar h1{{font-size:1.15em;color:#58a6ff}}
        .back-btn{{display:inline-block;padding:5px 14px;background:#1c2333;border:1px solid #58a6ff;border-radius:6px;color:#58a6ff;text-decoration:none;font-size:0.82em}}
        .back-btn:hover{{background:#1a3a5c;color:#79c0ff}}
        .content{{max-width:900px;margin:0 auto;padding:16px 24px}}
        .hist-body{{background:#161b22;border:1px solid #30363d;border-radius:6px;padding:20px 24px;line-height:1.8}}
    </style>
</head>
<body>
    <div class="topbar">
        <h1>📜 历史回顾 · 共 {turn} 轮 · {scene}</h1>
        <a href="/" class="back-btn">← 返回游戏</a>
    </div>
    <div class="content">
        <div class="hist-body">
            {history_html}
        </div>
    </div>
</body>
</html>"""

    return HTMLResponse(page)


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
            return RedirectResponse(url="/", status_code=303)
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
    return RedirectResponse(url="/", status_code=303)


