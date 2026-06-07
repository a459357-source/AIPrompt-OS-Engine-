"""NPC management: list, add, delete, AI-generate."""
from fastapi import APIRouter, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse

from engine import io_utils
from engine.deepseek_client import call_deepseek, DeepSeekError
from ui.templates import _NPC_PAGE
import config
import json

router = APIRouter(prefix="/npcs", tags=["npcs"])

# ── NPC Management ────────────────────────────────────────────────

_NPC_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>角色管理 — Prompt OS Galgame</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Segoe UI","Noto Sans SC",system-ui,sans-serif;background:#0d1117;color:#c9d1d9;min-height:100vh}
.topbar{display:flex;align-items:center;justify-content:space-between;padding:10px 24px;border-bottom:1px solid #21262d;background:#0d1117}
.topbar h1{font-size:1.15em;color:#58a6ff}
.back-btn{display:inline-block;padding:5px 14px;background:#1c2333;border:1px solid #58a6ff;border-radius:6px;color:#58a6ff;text-decoration:none;font-size:0.82em}
.back-btn:hover{background:#1a3a5c;color:#79c0ff}
.content{max-width:1100px;margin:0 auto;padding:16px 24px}
.add-bar{display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap;margin-bottom:16px;padding:14px;background:#161b22;border:1px solid #21262d;border-radius:8px}
.add-bar label{font-size:0.78em;color:#8b949e;margin-bottom:2px;display:block}
.add-bar input{padding:7px 10px;background:#0d1117;border:1px solid #30363d;border-radius:5px;color:#c9d1d9;font-size:0.85em;min-width:100px}
.add-bar input:focus{outline:none;border-color:#58a6ff}
.add-bar button{padding:7px 14px;border-radius:5px;font-size:0.82em;cursor:pointer;border:none;font-weight:bold;white-space:nowrap}
.btn-add{background:#238636;color:#fff}
.btn-add:hover{background:#2ea043}
.btn-ai{background:#1a3a5c;color:#58a6ff;border:1px solid #58a6ff!important}
.btn-ai:hover{background:#1f4a73}
.btn-ai:disabled{opacity:0.5;cursor:not-allowed}
.npc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px}
.npc-card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px 16px;position:relative}
.npc-card .tag{display:inline-block;padding:1px 6px;border-radius:3px;font-size:0.68em;margin-left:6px;vertical-align:middle}
.npc-card .tag.main{background:#1a3a5c;color:#58a6ff}
.npc-card .tag.npc{background:#3d2a1a;color:#ffa657}
.npc-card .name{font-weight:bold;color:#d2a8ff;font-size:1.05em}
.npc-card .role{color:#8b949e;font-size:0.82em;margin:4px 0}
.npc-card .note{color:#c9d1d9;font-size:0.8em;line-height:1.5;margin-top:6px}
.npc-card .level{color:#ffa657;font-size:0.78em}
.npc-card .trust{color:#7ee787;font-size:0.78em}
.npc-card .del-btn{position:absolute;top:8px;right:10px;background:none;border:none;color:#484f58;font-size:1em;cursor:pointer}
.npc-card .del-btn:hover{color:#f85149}
</style>
</head>
<body>
<div class="topbar">
    <h1>👥 角色管理</h1>
    <a href="/" class="back-btn">← 返回游戏</a>
</div>
<div class="content">
    <div class="add-bar">
        <div>
            <label>🤖 AI 生成</label>
            <div style="display:flex;gap:6px">
                <input id="ai_kw" placeholder="关键词：神秘商人 情报贩子" style="width:220px">
                <button class="btn-ai" id="ai_btn" onclick="generateNPC()">生成</button>
            </div>
            <div id="ai_status" style="font-size:0.72em;color:#8b949e;margin-top:2px;min-height:16px"></div>
        </div>
        <div style="border-left:1px solid #21262d;padding-left:12px">
            <form method="post" action="/npcs/add" style="display:flex;gap:6px;align-items:flex-end">
                <div><label>姓名</label><input name="name" placeholder="姓名" required style="width:100px"></div>
                <div><label>身份</label><input name="role" placeholder="身份" style="width:110px"></div>
                <div><label>描述</label><input name="note" placeholder="性格/背景" style="width:160px"></div>
                <button class="btn-add" type="submit">+ 添加</button>
            </form>
        </div>
    </div>
    <div class="npc-grid">
        {{NPC_CARDS}}
    </div>
</div>
    <script>
        async function generateNPC() {
            const kw = document.getElementById('ai_kw').value.trim();
            const status = document.getElementById('ai_status');
            const btn = document.getElementById('ai_btn');
            if (!kw) { status.textContent = '请输入描述'; status.style.color = '#f85149'; return; }
            status.textContent = '⏳ AI 正在生成角色…'; status.style.color = '#ffa657';
            btn.disabled = true;
            try {
                const res = await fetch('/npcs/generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: 'keywords=' + encodeURIComponent(kw)
                });
                const data = await res.json();
                if (data.error) {
                    status.textContent = '❌ ' + data.error; status.style.color = '#f85149';
                } else {
                    status.textContent = '✅ 已创建: ' + data.name;
                    status.style.color = '#7ee787';
                    setTimeout(() => location.reload(), 800);
                }
            } catch(e) {
                status.textContent = '❌ ' + e.message; status.style.color = '#f85149';
            }
            btn.disabled = false;
        }
    </script>
</body>
</html>"""


@router.get("", response_class=HTMLResponse)
async def npc_page():
    """Show all characters with management options."""
    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    except Exception:
        state = {}

    chars = state.get("characters", {})
    if not chars:
        cards = '<p style="color:#8b949e;text-align:center;padding:40px;">尚无角色，请添加</p>'
    else:
        cards_list = []
        for key, c in chars.items():
            is_main = key in ("A", "B")
            tag = '<span class="tag main">主角</span>' if is_main else '<span class="tag npc">NPC</span>'
            del_btn = '' if is_main else '<a class="del-btn" href="/npcs/delete?key=' + key + '" onclick="return confirm(&quot;delete ' + c.get('name', key) + '?&quot;)" title="delete">X</a>'
            safe_name = c.get("name", key).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            safe_role = c.get("role", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            safe_level = c.get("level", "L0").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            safe_rel = c.get("relation", "初识").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            safe_note = c.get("note", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            cards_list.append(
                f'<div class="npc-card">'
                f'{del_btn}'
                f'<div class="name">{safe_name}{tag}</div>'
                f'<div class="role">{safe_role}</div>'
                f'<div class="level">⭐ {safe_level}</div>'
                f'<div class="trust">🤝 {safe_rel}</div>'
                f'<div class="note">{safe_note}</div>'
                f'</div>'
            )
        cards = "\n".join(cards_list)

    page = _NPC_PAGE.replace("{{NPC_CARDS}}", cards)
    return HTMLResponse(page)


@router.post("/add", response_class=HTMLResponse)
async def add_npc_manual(
    name: str = Form(...),
    role: str = Form(""),
    note: str = Form(""),
):
    """Manually add a new NPC."""
    from fastapi.responses import RedirectResponse

    state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    chars = state.get("characters", {})

    # Find next available key
    existing = set(chars.keys())
    next_key = "C"
    while next_key in existing:
        next_key = chr(ord(next_key) + 1)

    chars[next_key] = {
        "name": name.strip(),
        "role": role.strip(),
        "level": "L0",
        "relation": "初识",
        "note": note.strip(),
        "is_npc": True,
    }
    state["characters"] = chars
    io_utils.write_yaml(config.SESSION_STATE_PATH, state)

    # Also add to memory
    mem = load_memory()
    mem.setdefault("characters", {})[name.strip()] = {
        "trust": 0.5, "flags": [], "relationship": f"{role.strip()}，初识"
    }
    from engine.memory import save_memory
    save_memory(mem)

    return RedirectResponse(url="/npcs", status_code=303)


@router.get("/delete", response_class=HTMLResponse)
async def delete_npc(key: str = Query(...)):
    """Delete an NPC (not main characters A/B)."""
    from fastapi.responses import RedirectResponse

    if key in ("A", "B"):
        return RedirectResponse(url="/npcs", status_code=303)

    state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    chars = state.get("characters", {})
    if key in chars:
        chars.pop(key)
        state["characters"] = chars
        io_utils.write_yaml(config.SESSION_STATE_PATH, state)
    return RedirectResponse(url="/npcs", status_code=303)


@router.post("/generate")
async def generate_npc(keywords: str = Form("")):
    """Generate a new NPC from keywords using DeepSeek."""
    from fastapi.responses import JSONResponse
    from engine.deepseek_client import call_deepseek, DeepSeekError

    kw = keywords.strip()
    if not kw:
        return JSONResponse({"error": "请输入描述"}, status_code=400)

    # Get world context
    try:
        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
        world_title = world_pack.get("world", {}).get("title", "")
        world_setting = world_pack.get("world", {}).get("setting", "")
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
        existing_chars = state.get("characters", {})
        existing_names = ", ".join(c.get("name", k) for k, c in existing_chars.items())
    except Exception:
        world_title = ""
        world_setting = ""
        existing_names = ""

    system = "你是一个 Galgame 角色生成器。根据世界观和关键词，生成一个合适的NPC角色。只输出合法JSON。"
    user = f"""当前世界观：{world_title}
背景：{world_setting}
已有角色：{existing_names}
关键词描述：{kw}

请生成一个新NPC角色，输出JSON：
{{
  "name": "角色名（2-4字中文名）",
  "role": "身份/职业",
  "note": "性格和外貌描述（20-40字）"
}}

要求：角色要符合世界观设定，与已有角色不重复，有独特的性格特点。只输出JSON。"""

    try:
        result = call_deepseek(system, user, temperature=0.9, max_tokens=config.MAX_TOKENS)

        # Auto-add to state + memory
        state = io_utils.read_yaml(config.SESSION_STATE_PATH)
        chars = state.get("characters", {})
        existing = set(chars.keys())
        next_key = "C"
        while next_key in existing:
            next_key = chr(ord(next_key) + 1)

        name = result.get("name", "未命名")
        role = result.get("role", "")
        note = result.get("note", "")

        chars[next_key] = {
            "name": name,
            "role": role,
            "level": "L0",
            "relation": "初识",
            "note": note,
            "is_npc": True,
        }
        state["characters"] = chars
        io_utils.write_yaml(config.SESSION_STATE_PATH, state)

        mem = load_memory()
        mem.setdefault("characters", {})[name] = {
            "trust": 0.5, "flags": [], "relationship": f"{role}，初识"
        }
        from engine.memory import save_memory
        save_memory(mem)

        return JSONResponse({"name": name, "role": role, "note": note, "key": next_key})
    except DeepSeekError as exc:
        return JSONResponse({"error": f"AI 生成失败: {exc}"}, status_code=500)


