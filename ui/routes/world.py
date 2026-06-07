"""World creation: new story page, AI world/field/rules generators."""
from fastapi import APIRouter, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse

from engine import io_utils, save_manager
from engine.memory import load_memory
from engine.deepseek_client import call_deepseek, DeepSeekError
from ui.templates import _NEW_PAGE, _PRESETS
import config
import json

router = APIRouter(tags=["world"])

@router.get("/new", response_class=HTMLResponse)
async def new_story_page():
    """Show the new story creation form."""
    return HTMLResponse(_NEW_PAGE)


@router.post("/new", response_class=HTMLResponse)
async def create_new_story(
    title: str = Form(...),
    world: str = Form(""),
    genre: str = Form(""),
    scene: str = Form(...),
    chars_json: str = Form(""),
    custom_rules: str = Form(""),
    main_goal: str = Form(""),
    rel_system: str = Form(""),
):
    """Process the new story form and initialize all state."""
    import yaml

    # Parse characters from JSON
    chars = []
    if chars_json.strip():
        try:
            chars = json.loads(chars_json.strip())
        except Exception:
            pass
    if not chars:
        chars = [{"name": "主角", "role_tags": [], "appearance": "", "personality_tags": [], "relationship": [], "goal": "", "secret": "", "background": "", "special_ability": "", "isMain": True}]

    # Parse custom rules if provided
    custom = {}
    if custom_rules.strip():
        try:
            custom = json.loads(custom_rules.strip())
        except Exception:
            pass

    # Parse main goal
    main_goal_text = main_goal.strip() if main_goal else ""

    # Parse relationship system
    rel_config = {"stages": ["陌生", "熟悉", "朋友", "信赖", "暧昧", "恋人"], "affection": 0}
    if rel_system.strip():
        try:
            rel_config = json.loads(rel_system.strip())
        except Exception:
            pass

    # Build world_pack.yaml
    world_pack = {
        "world": {
            "title": title,
            "genre": genre,
            "era": "故事开端",
            "setting": world,
            "main_goal": main_goal_text,
            "factions": [],
            "locations": [
                {"name": scene, "desc": "初始场景"},
            ],
            "tone": "聚焦人物情感与选择",
            "themes": [],
            "characters": [],
            "relationship_system": rel_config,
        }
    }
    if custom:
        world_pack["custom"] = custom

    # Build rich character data for world_pack
    for ch in chars:
        char_data = {
            "name": ch.get("name", ""),
            "is_main": ch.get("isMain", False),
            "role_tags": ch.get("role_tags", []),
            "personality_tags": ch.get("personality_tags", []),
            "appearance": ch.get("appearance", ""),
            "relationship": ch.get("relationship", []),
            "goal": ch.get("goal", ""),
            "secret": ch.get("secret", ""),
            "background": ch.get("background", ""),
            "special_ability": ch.get("special_ability", ""),
        }
        if isinstance(char_data["role_tags"], str): char_data["role_tags"] = [char_data["role_tags"]]
        if isinstance(char_data["personality_tags"], str): char_data["personality_tags"] = [char_data["personality_tags"]]
        if isinstance(char_data["relationship"], str): char_data["relationship"] = [char_data["relationship"]]
        world_pack["world"]["characters"].append(char_data)
    io_utils.write_yaml(config.WORLD_PACK_PATH, world_pack)

    # Build initial state with dynamic characters
    state_chars = {}
    mem_chars = {}
    init_stage = rel_config.get("stages", ["陌生"])[0] if rel_config.get("stages") else "陌生"
    init_affection = rel_config.get("affection", 0)
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i, ch in enumerate(chars):
        if i >= len(letters):
            break
        key = letters[i]
        name = ch.get("name", f"角色{i+1}")
        is_main = ch.get("isMain", False)
        role_tags = ch.get("role_tags", [])
        if isinstance(role_tags, str): role_tags = [role_tags]
        role_str = " / ".join(role_tags) if role_tags else (ch.get("role", ""))
        personality_tags = ch.get("personality_tags", [])
        if isinstance(personality_tags, str): personality_tags = [personality_tags]
        relationship = ch.get("relationship", [])
        if isinstance(relationship, str): relationship = [relationship]
        appearance = ch.get("appearance", "")
        goal = ch.get("goal", "")
        secret = ch.get("secret", "")
        background = ch.get("background", "")
        special_ability = ch.get("special_ability", "")

        note_parts = []
        if appearance: note_parts.append(f"外貌：{appearance}")
        if personality_tags: note_parts.append(f"性格：{' / '.join(personality_tags)}")
        if relationship and not is_main: note_parts.append(f"关系：{' / '.join(relationship)}")
        if goal: note_parts.append(f"目标：{goal}")
        if secret: note_parts.append(f"秘密：{secret}")
        if background and is_main: note_parts.append(f"背景：{background}")
        if special_ability and is_main: note_parts.append(f"能力：{special_ability}")
        note_parts.append(ch.get("notes", ""))
        note = "\n".join(p for p in note_parts if p)
        if not note: note = ""

        state_chars[key] = {
            "name": name,
            "role": role_str,
            "level": "L0",
            "relation": init_stage,
            "note": note,
        }
        initial_trust = init_affection / 100.0 if init_affection > 0 else 0.5
        rel_desc = (role_str + "，" if role_str else "") + init_stage
        mem_chars[name] = {
            "trust": initial_trust,
            "flags": [],
            "relationship": rel_desc,
        }
        if secret:
            mem_chars[name].setdefault("flags", []).append(f"隐藏秘密：{secret}")

    initial_state = {
        "scene": scene,
        "status": "SETUP",
        "turn": 0,
        "characters": state_chars,
        "history": [],
        "force_event_pending": False,
        "chapter": 1,
    }
    io_utils.write_yaml(config.SESSION_STATE_PATH, initial_state)

    # Reset chapter
    config.CHAPTER_PATH.write_text("", encoding="utf-8")

    # Reset story graph
    initial_graph = {
        "nodes": {
            "0": {
                "turn": 0,
                "text": f"初始场景：{scene}",
                "scene": scene,
                "status": "SETUP",
                "choices": {},
                "parent": None,
                "choice_taken": None,
            }
        },
        "current_node": "0",
        "edges": [],
    }
    io_utils.write_json(config.STORY_GRAPH_PATH, initial_graph)

    # Reset memory
    initial_memory = {
        "characters": mem_chars,
        "world_flags": [],
        "global_trust": 0.5,
        "relationship_system": rel_config,
    }
    io_utils.write_json(config.MEMORY_PATH, initial_memory)

    # Save factory-reset snapshot so reset() can restore the user's world
    io_utils.write_json(config.WORLD_INIT_PATH, {
        "state": initial_state,
        "graph": initial_graph,
        "memory": initial_memory,
    })

    # Redirect to main page
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/", status_code=303)


# ── AI World Generator ─────────────────────────────────────────────

@router.post("/generate-world")
async def generate_world(keywords: str = Form("")):
    """Generate a world setting from keywords using DeepSeek."""
    from fastapi.responses import JSONResponse
    from engine.deepseek_client import call_deepseek, DeepSeekError

    kw = keywords.strip()
    if not kw:
        return JSONResponse({"error": "请输入关键词"}, status_code=400)

    system = "你是一个 Galgame 世界观生成器。根据用户提供的描述或关键词，生成完整的中文 Galgame 世界观设定。只输出合法 JSON，不要输出其他内容。"
    user = f"""输入内容：{kw}

请根据以上内容，生成一个完整的 Galgame 世界观设定。输出必须是合法的 JSON：

{{
  "title": "故事标题（8~20字）",
  "world": "世界观/背景描述（50-300字）",
  "genre": ["标签1", "标签2"],
  "scene": "初始场景/地点名称",
  "main_goal": "故事主线目标（一句话）",
  "characters": [
    {{
      "name": "角色姓名",
      "isMain": true,
      "role_tags": ["身份标签"],
      "personality_tags": ["性格标签1", "性格标签2", "性格标签3"],
      "appearance": "外貌特征（10~30字）",
      "relationship": ["与主角关系"],
      "goal": "角色目标",
      "secret": "隐藏秘密",
      "background": "背景经历（主角）",
      "special_ability": "特殊能力（主角）"
    }}
  ],
  "rel_stages": ["陌生", "熟悉", "朋友", "信赖", "暧昧", "恋人"],
  "rel_affection": 0,
  "stats": [
    {{"key": "trust", "label": "好感度", "max": 100}}
  ]
}}

要求：
1. 角色要有个性，包含外貌、性格标签、目标、隐藏秘密
2. 主角和至少1个NPC之间要有潜在的戏剧冲突或情感张力
3. 初始场景要具体、有画面感
4. stats 根据故事类型设计2-3个专属追踪维度（如修仙→修为/道心，宫廷→忠诚/权势，悬疑→信任/线索），key用英文label用中文
5. rel_stages 设计5-7个贴合故事的递进阶段
6. 所有文字用中文
7. 只输出JSON，不要输出markdown代码块或其他文字"""

    try:
        result = call_deepseek(system, user, temperature=0.9, max_tokens=config.MAX_TOKENS * 2, skip_validation=True)
        return JSONResponse(result)
    except DeepSeekError as exc:
        return JSONResponse({"error": f"AI 生成失败: {exc}"}, status_code=500)
    except Exception as exc:
        return JSONResponse({"error": f"未知错误: {exc}"}, status_code=500)


# ── Field-level AI generation ─────────────────────────────────────

@router.post("/generate-field")
async def generate_field(field: str = Form(""), title: str = Form(""), world: str = Form(""),
                         genre: str = Form(""), char_name: str = Form(""), char_role: str = Form(""),
                         context: str = Form("")):
    """Generate a single story field via AI (title, world, or character)."""
    from engine.deepseek_client import call_deepseek, DeepSeekError
    from fastapi.responses import JSONResponse as JR

    system = "你是一个中文 Galgame 创作助手。只输出要求的内容，不要输出解释、引号或 JSON 包装。"

    if field == "title":
        user = f"根据以下世界观，生成一个吸引人的故事标题（8~20字）：\n{world or context}\n\n标题："
    elif field == "world":
        ctx = f"标题：{title}，风格：{genre}" if title else context
        user = f"为以下 Galgame 生成世界观背景描述（50-300字，沉浸式叙事风格）：\n{ctx}\n\n世界观："
    elif field == "main_goal":
        ctx = f"标题：{title}，世界观：{world[:200] if world else context[:200]}"
        user = f"为以下 Galgame 生成一个清晰的故事主线目标（一句话）：\n{ctx}\n\n主线目标："
    elif field == "scene":
        ctx = f"标题：{title}，世界观：{world[:200] if world else context[:200]}"
        user = f"为以下 Galgame 生成一个具体的开局场景名称：\n{ctx}\n\n场景："
    elif field == "genre":
        ctx = f"标题：{title}，世界观：{world[:200] if world else context[:200]}"
        user = f"为以下 Galgame 推荐3-5个风格标签（校园、恋爱、后宫、日常、轻小说、科幻、奇幻、修仙、末日、悬疑、推理、克苏鲁、冒险、战争、搞笑、黑暗、治愈、百合、女性向）：\n{ctx}\n\n输出JSON数组：[\"标签1\", \"标签2\"]"
    elif field == "character":
        user = f"为以下故事生成一个完整的角色，用 JSON 格式输出：\n故事标题：{title}\n世界观：{world[:300] if world else context[:300]}\n角色定位：{char_role or '重要NPC'}\n\n输出格式：{{\"name\":\"角色名\",\"isMain\":false,\"role_tags\":[\"身份\"],\"personality_tags\":[\"性格1\",\"性格2\",\"性格3\"],\"appearance\":\"外貌特征（10~30字）\",\"relationship\":[\"与主角关系\"],\"goal\":\"角色目标\",\"secret\":\"隐藏秘密\"}}\n\n要求：角色要有个性、有目标、有秘密，避免平淡。只输出JSON。"
    elif field == "rel_system":
        ctx = f"标题：{title}，世界观：{world[:200] if world else context[:200]}"
        user = f"为以下 Galgame 推荐关系阶段系统（5-7个递进阶段）：\n{ctx}\n\n输出JSON：{{\"rel_stages\":[\"阶段1\",\"阶段2\",...],\"rel_affection\":0}}"
    else:
        return JR({"error": f"未知字段类型: {field}"}, status_code=400)

    try:
        result = call_deepseek(system, user, temperature=0.9, max_tokens=config.MAX_TOKENS, skip_validation=True)
        # For character field, try to parse JSON from response
        if field == "character":
            # The result might already be the character object (skip_validation mode)
            # or wrapped in a {"story": "..."} envelope
            if "name" in result:
                # Normalize: AI might return singular strings instead of lists
                if "role_tags" not in result and "role" in result:
                    result["role_tags"] = [result.pop("role")] if isinstance(result.get("role"), str) else result.pop("role")
                if "personality_tags" not in result and "personality" in result:
                    p = result.pop("personality")
                    result["personality_tags"] = [p] if isinstance(p, str) else p
                if "relationship" in result and isinstance(result["relationship"], str):
                    result["relationship"] = [result["relationship"]]
                # Ensure list fields are lists
                for f in ["role_tags", "personality_tags", "relationship"]:
                    if f in result and not isinstance(result[f], list):
                        result[f] = [result[f]] if result[f] else []
                if "name" in result and ("role_tags" in result or "role" not in result):
                    result.setdefault("role_tags", [])
                    result.setdefault("personality_tags", [])
                    result.setdefault("appearance", "")
                    result.setdefault("relationship", [])
                    result.setdefault("goal", "")
                    result.setdefault("secret", "")
                    return JR(result)
            story = result.get("story", "") or result.get("name", "") or ""
            import re as _re
            m = _re.search(r'\{[^{}]*\{[^{}]*\}[^{}]*\}', story)
            if not m:
                m = _re.search(r'\{[^}]+\}', story)
            if m:
                import json as _json
                try:
                    return JR(_json.loads(m.group()))
                except Exception:
                    pass
            return JR({"name": story.strip()[:20], "role_tags": [char_role] if char_role else [], "isMain": False, "personality_tags": [], "appearance": "", "relationship": [], "goal": "", "secret": ""})
        if field == "genre":
            story = result.get("story", "")
            import re as _re2
            m = _re2.search(r'\[[^\]]+\]', story)
            if m:
                import json as _json2
                try:
                    return JR({"genre": _json2.loads(m.group())})
                except Exception:
                    pass
            return JR({"genre": [story.strip()[:10]]})
        if field == "rel_system":
            story = result.get("story", "")
            import re as _re3
            m = _re3.search(r'\{[^}]+\}', story)
            if m:
                import json as _json3
                try:
                    return JR(_json3.loads(m.group()))
                except Exception:
                    pass
            return JR({"rel_stages": ["陌生", "熟悉", "朋友", "信赖", "暧昧", "恋人"], "rel_affection": 0})
        return JR(result)
    except DeepSeekError as exc:
        return JR({"error": f"AI 生成失败: {exc}"}, status_code=500)
    except Exception as exc:
        return JR({"error": f"未知错误: {exc}"}, status_code=500)


# ── Custom Rules Generator ─────────────────────────────────────────

@router.post("/generate-rules")
async def generate_rules(
    title: str = Form(""),
    world: str = Form(""),
    genre: str = Form(""),
    char1_name: str = Form(""),
    char1_role: str = Form(""),
    char2_name: str = Form(""),
    char2_role: str = Form(""),
):
    """Generate story-specific custom tracking rules."""
    from fastapi.responses import JSONResponse
    from engine.deepseek_client import call_deepseek, DeepSeekError

    system = "你是 Galgame 规则设计师。根据故事设定生成专属的角色追踪维度。只输出合法JSON。"
    user = f"""故事标题：{title}
类型：{genre}
世界观：{world}
角色1：{char1_name}（{char1_role}）
角色2：{char2_name}（{char2_role}）

请为这个故事设计 2-3 个专属的角色追踪维度（替代通用的"好感度"）。
例如：
- 宫廷故事 → 忠诚度、权势、民心
- 修仙故事 → 修为、道心、羁绊
- 商战故事 → 信任度、影响力、筹码

同时设计 5-7 个关系阶段标签（替代通用的"陌生→朋友→恋人"）。

输出 JSON：
{{
  "stats": [
    {{"key": "loyalty", "label": "忠诚度", "max": 100}},
    {{"key": "power", "label": "权势", "max": 100}}
  ],
  "stages": ["陌路", "相识", "君臣", "心腹", "托付"]
}}

要求：
1. stat.key 用英文（loyalty/power等），label 用中文
2. 每个 stat 有 max 值（建议 100）
3. stages 5-7 个，从疏远到亲密递进
4. 维度要贴合故事背景，有创意
5. 只输出 JSON"""

    try:
        result = call_deepseek(system, user, temperature=0.9, max_tokens=config.MAX_TOKENS, skip_validation=True)
        return JSONResponse(result)
    except DeepSeekError as exc:
        return JSONResponse({"error": f"AI 生成失败: {exc}"}, status_code=500)


