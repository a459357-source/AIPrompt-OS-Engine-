"""World creation: new story form POST and AI world/field/rules generators."""
from fastapi import APIRouter, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse

from engine import io_utils, save_manager
from engine.memory import load_memory
from engine.deepseek_client import call_deepseek, DeepSeekError
import config
import json

router = APIRouter(tags=["world"])

_REL_TYPES = frozenset({"friend", "lover", "family", "teacher", "rival", "ally", "enemy"})
_REL_METRICS = ("affection", "trust", "respect", "dependence", "hostility", "attraction")

_PERSONALITY_BRAIN_KEYS = frozenset({"desire", "fear", "taboo", "secret", "values"})


def _is_brain_personality(raw) -> bool:
    return isinstance(raw, dict) and any(k in raw for k in _PERSONALITY_BRAIN_KEYS)


def _normalize_character_personality(ch: dict) -> dict:
    """Ensure character has normalized personality brain (from AI or form)."""
    from engine.character_brain import normalize_personality, seed_personality_from_world

    ch = ch if isinstance(ch, dict) else {}
    if _is_brain_personality(ch.get("personality")):
        ch["personality"] = normalize_personality(ch["personality"])
    else:
        ch["personality"] = seed_personality_from_world(ch)
    return ch


def _apply_character_personality_from_ai(result: dict) -> None:
    """Normalize AI character JSON: brain personality vs legacy personality tags."""
    from engine.character_brain import normalize_personality, seed_personality_from_world

    raw_p = result.get("personality")
    if _is_brain_personality(raw_p):
        result["personality"] = normalize_personality(raw_p)
    elif "personality_tags" not in result and "personality" in result:
        p = result.pop("personality")
        result["personality_tags"] = [p] if isinstance(p, str) else (p if isinstance(p, list) else [])
        result["personality"] = seed_personality_from_world(result)
    else:
        result["personality"] = seed_personality_from_world(result)


def _finalize_character_field_result(result: dict, *, context: str = "") -> dict:
    """Normalize single-character AI field output (main path + regex fallback)."""
    if "role_tags" not in result and "role" in result:
        role = result.pop("role")
        result["role_tags"] = [role] if isinstance(role, str) else role
    _apply_character_personality_from_ai(result)
    if "relationship" in result and isinstance(result["relationship"], str):
        result["relationship"] = [result["relationship"]]
    for f in ("role_tags", "personality_tags", "relationship"):
        if f in result and not isinstance(result[f], list):
            result[f] = [result[f]] if result[f] else []
    result.setdefault("role_tags", [])
    result.setdefault("personality_tags", [])
    result.setdefault("appearance", "")
    result.setdefault("relationship", [])
    result.setdefault("goal", "")
    result.setdefault("secret", "")
    result.setdefault("faction", "")
    result.setdefault("factionMemberships", [])
    if context.strip():
        try:
            fac_list = json.loads(context)
            if isinstance(fac_list, list):
                linked = _link_character_factions([result], fac_list)
                if linked:
                    result["factionMemberships"] = linked[0].get("factionMemberships", [])
                    result["faction"] = linked[0].get("faction", result.get("faction", ""))
        except json.JSONDecodeError:
            pass
    return result


def _clamp_rel_metric(value, default: int = 50) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(100, n))


def _normalize_character_relations(raw, npc_names: list[str]) -> dict:
    """Normalize AI output for NewStory multidimensional relations."""
    raw = _remap_relation_keys(raw, npc_names)
    out = {}
    for name in npc_names:
        if not name:
            continue
        rel = raw.get(name) if isinstance(raw.get(name), dict) else {}
        rel_type = rel.get("relationshipType", "friend")
        if rel_type not in _REL_TYPES:
            rel_type = "friend"
        tags = rel.get("tags") or []
        if not isinstance(tags, list):
            tags = [tags] if tags else []
        tags = [str(t).strip() for t in tags if t and str(t).strip()]
        out[name] = {
            "relationshipType": rel_type,
            **{m: _clamp_rel_metric(rel.get(m), 50) for m in _REL_METRICS},
            "tags": tags[:6],
        }
    return out


def _parse_json_object_from_story(story: str) -> dict | None:
    import re as _re
    m = _re.search(r"\{[^{}]*\{[^{}]*\}[^{}]*\}", story)
    if not m:
        m = _re.search(r"\{[^}]+\}", story)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def _resolve_faction_name(raw: str, name_map: dict) -> str:
    """Match a faction name against known factions (exact or fuzzy)."""
    raw = str(raw or "").strip()
    if not raw:
        return ""
    if raw in name_map:
        return raw
    for fname in name_map:
        if raw in fname or fname in raw:
            return fname
    return ""


def _primary_public_faction(memberships: list) -> str:
    for item in memberships:
        if not isinstance(item, dict):
            continue
        if item.get("visibility", "public") == "public":
            return str(item.get("faction", "")).strip()
    if memberships and isinstance(memberships[0], dict):
        return str(memberships[0].get("faction", "")).strip()
    return ""


def _normalize_faction_memberships(entry: dict, factions: list, name_map: dict, leader_map: dict) -> list:
    """Normalize factionMemberships / legacy faction into [{faction, visibility}]."""
    cname = str(entry.get("name", "")).strip()
    raw_list = entry.get("factionMemberships") or entry.get("faction_memberships")
    out: list[dict] = []
    if isinstance(raw_list, list) and raw_list:
        seen: set[str] = set()
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            fname = _resolve_faction_name(item.get("faction", ""), name_map)
            if not fname or fname in seen:
                continue
            vis = item.get("visibility", "public")
            if vis not in ("public", "hidden"):
                vis = "public"
            out.append({"faction": fname, "visibility": vis})
            seen.add(fname)
    if not out:
        raw = str(entry.get("faction", "")).strip()
        resolved = _resolve_faction_name(raw, name_map)
        if not resolved and cname in leader_map:
            resolved = leader_map[cname]
        if resolved:
            out.append({"faction": resolved, "visibility": "public"})
    return out


def _link_character_factions(characters, factions) -> list:
    """Ensure each character has factionMemberships and primary faction."""
    if not isinstance(characters, list) or not characters:
        return characters or []
    if not isinstance(factions, list) or not factions:
        return characters

    name_map = {
        str(f.get("name", "")).strip(): f
        for f in factions
        if isinstance(f, dict) and str(f.get("name", "")).strip()
    }
    if not name_map:
        return characters

    leader_map = {}
    for fname, fac in name_map.items():
        leader = str(fac.get("leader", "")).strip()
        if leader:
            leader_map[leader] = fname

    linked = []
    for ch in characters:
        if not isinstance(ch, dict):
            linked.append(ch)
            continue
        entry = dict(ch)
        memberships = _normalize_faction_memberships(entry, factions, name_map, leader_map)
        entry["factionMemberships"] = memberships
        entry["faction"] = _primary_public_faction(memberships)
        linked.append(entry)
    return linked


def _remap_relation_keys(raw, npc_names: list[str]) -> dict:
    """Match characterRelations keys to actual NPC names (fuzzy)."""
    if not isinstance(raw, dict):
        return {}
    remapped = {}
    used_keys: set[str] = set()
    for npc in npc_names:
        if not npc:
            continue
        if npc in raw and isinstance(raw.get(npc), dict):
            remapped[npc] = raw[npc]
            used_keys.add(npc)
            continue
        for key, val in raw.items():
            if key in used_keys or not isinstance(val, dict):
                continue
            key_str = str(key)
            if key_str == npc or key_str in npc or npc in key_str:
                remapped[npc] = val
                used_keys.add(key_str)
                break
    return remapped


def _link_artifact_owners(artifacts, characters, factions) -> list:
    """Resolve artifact ownerId to known character or faction names."""
    if not isinstance(artifacts, list):
        return []
    char_names = [
        str(c.get("name", "")).strip()
        for c in (characters or [])
        if isinstance(c, dict) and str(c.get("name", "")).strip()
    ]
    fac_names = [
        str(f.get("name", "")).strip()
        for f in (factions or [])
        if isinstance(f, dict) and str(f.get("name", "")).strip()
    ]

    def _resolve(name, owner_type: str) -> str:
        raw = str(name or "").strip()
        if not raw:
            return ""
        if owner_type == "character":
            pool = char_names
        elif owner_type == "faction":
            pool = fac_names
        else:
            pool = char_names + fac_names
        if raw in pool:
            return raw
        for candidate in pool:
            if raw in candidate or candidate in raw:
                return candidate
        return raw

    linked = []
    for art in artifacts:
        if not isinstance(art, dict):
            continue
        entry = dict(art)
        owner_type = str(entry.get("ownerType", "none") or "none")
        entry["ownerId"] = _resolve(entry.get("ownerId", ""), owner_type)
        linked.append(entry)
    return linked


@router.post("/new")
async def create_new_story(
    title: str = Form(...),
    world: str = Form(""),
    genre: str = Form(""),
    scene: str = Form(...),
    chars_json: str = Form(""),
    custom_rules: str = Form(""),
    main_goal: str = Form(""),
    rel_system: str = Form(""),
    artifacts_json: str = Form(""),
    factions_json: str = Form(""),
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

    # Parse factions (needed before linking character memberships)
    factions = []
    if factions_json.strip():
        try:
            raw_factions = json.loads(factions_json.strip())
            for f in raw_factions:
                f.setdefault("type", "organization")
                f.setdefault("goals", [])
                f.setdefault("resources", [])
                f.setdefault("controlledTerritories", [])
                f.setdefault("subordinateOrganizations", [])
                f.setdefault("keyAssets", [])
                f.setdefault("power", {"military": 0, "economic": 0, "political": 0, "technology": 0})
                f.setdefault("influence", 50)
                f.setdefault("relation_to_player", "neutral")
                f.setdefault("leader", "")
                f.setdefault("description", "")
                factions.append(f)
        except Exception:
            pass

    if factions:
        chars = _link_character_factions(chars, factions)

    # Parse custom rules if provided
    custom = {}
    if custom_rules.strip():
        try:
            custom = json.loads(custom_rules.strip())
        except Exception:
            pass

    # Normalize stats from AI / form (label may be missing)
    raw_stats = custom.get("stats") if isinstance(custom, dict) else None
    if isinstance(raw_stats, list):
        normalized_stats = []
        for s in raw_stats:
            if not isinstance(s, dict):
                continue
            normalized_stats.append({
                "key": s.get("key") or "stat",
                "label": s.get("label") or s.get("key") or "维度",
                "max": s.get("max", 100),
            })
        custom["stats"] = normalized_stats

    # Parse main goal
    main_goal_text = main_goal.strip() if main_goal else ""

    # Parse relationship system
    rel_config = {"stages": ["崩坏", "敌视", "对立", "冷漠", "疏远", "陌生", "认识", "信赖", "盟友", "羁绊"], "affection": 0}
    if rel_system.strip():
        try:
            rel_config = json.loads(rel_system.strip())
        except Exception:
            pass

    # Parse artifacts
    artifacts = []
    if artifacts_json.strip():
        try:
            artifacts = json.loads(artifacts_json.strip())
            # Normalize each artifact
            for art in artifacts:
                art.setdefault("type", "personal")
                art.setdefault("ownerType", "none")
                art.setdefault("ownerId", "")
                art.setdefault("importance", 50)
                art.setdefault("status", "active")
                art.setdefault("abilities", [])
                art.setdefault("tags", [])
                art.setdefault("relatedCharacters", [])
                art.setdefault("relatedFactions", [])
        except Exception:
            pass

    # Parse factions — already parsed above for character linking; skip duplicate block if empty retry
    if not factions and factions_json.strip():
        try:
            raw_factions = json.loads(factions_json.strip())
            for f in raw_factions:
                f.setdefault("type", "organization")
                f.setdefault("goals", [])
                f.setdefault("resources", [])
                f.setdefault("controlledTerritories", [])
                f.setdefault("subordinateOrganizations", [])
                f.setdefault("keyAssets", [])
                f.setdefault("power", {"military": 0, "economic": 0, "political": 0, "technology": 0})
                f.setdefault("influence", 50)
                f.setdefault("relation_to_player", "neutral")
                f.setdefault("leader", "")
                f.setdefault("description", "")
                factions.append(f)
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
            "factions": factions,
            "locations": [
                {"name": scene, "desc": "初始场景"},
            ],
            "tone": "聚焦人物情感与选择",
            "themes": [],
            "characters": [],
            "relationship_system": rel_config,
            "artifacts": artifacts,
        }
    }
    if custom:
        world_pack["custom"] = custom

    # Build rich character data for world_pack
    for ch in chars:
        memberships = ch.get("factionMemberships") or ch.get("faction_memberships") or []
        if not isinstance(memberships, list):
            memberships = []
        memberships = [
            {
                "faction": str(m.get("faction", "")).strip(),
                "visibility": m.get("visibility", "public")
                if m.get("visibility") in ("public", "hidden")
                else "public",
            }
            for m in memberships
            if isinstance(m, dict) and str(m.get("faction", "")).strip()
        ]
        primary_faction = _primary_public_faction(memberships) or str(ch.get("faction", "")).strip()
        char_data = {
            "name": ch.get("name", ""),
            "is_main": ch.get("isMain", False),
            "faction": primary_faction,
            "faction_memberships": memberships,
            "role_tags": ch.get("role_tags", []),
            "personality_tags": ch.get("personality_tags", []),
            "appearance": ch.get("appearance", ""),
            "relationship": ch.get("relationship", []),
            "goal": ch.get("goal", ""),
            "secret": ch.get("secret", ""),
            "background": ch.get("background", ""),
            "special_ability": ch.get("special_ability", ""),
        }
        _normalize_character_personality(char_data)
        if isinstance(char_data["role_tags"], str): char_data["role_tags"] = [char_data["role_tags"]]
        if isinstance(char_data["personality_tags"], str): char_data["personality_tags"] = [char_data["personality_tags"]]
        if isinstance(char_data["relationship"], str): char_data["relationship"] = [char_data["relationship"]]
        world_pack["world"]["characters"].append(char_data)
    io_utils.write_yaml(config.WORLD_PACK_PATH, world_pack)
    from engine.memory_layers import build_world_summary_from_pack
    io_utils.write_json(config.WORLD_SUMMARY_PATH, build_world_summary_from_pack(world_pack))

    # Build initial state with dynamic characters
    state_chars = {}
    mem_chars = {}
    init_affection = rel_config.get("affection", 0)
    char_relations = custom.get("characterRelations", {}) if custom else {}
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    from engine.character_registry import initial_relation_label

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

        relation_label = initial_relation_label(
            name,
            is_main=is_main,
            relationship=relationship,
            char_relations=char_relations,
        )

        state_chars[key] = {
            "name": name,
            "role": role_str,
            "level": "L0",
            "relation": relation_label,
            "note": note,
        }
        initial_trust = init_affection / 100.0 if init_affection > 0 else 0.5
        mem_rel = relation_label
        if is_main and role_str:
            mem_rel = f"{role_str}，主角"
        mem_chars[name] = {
            "trust": initial_trust,
            "flags": [],
            "relationship": mem_rel,
            "personality": char_data["personality"],
        }
        if secret:
            mem_chars[name].setdefault("flags", []).append(f"隐藏秘密：{secret}")

    # Seed multidimensional relations from NewStory「专属规则 & 多维关系」
    rel_metrics = ("trust", "affection", "respect", "dependence", "hostility", "attraction")
    for npc_name, rel in char_relations.items():
        if not isinstance(rel, dict) or npc_name not in mem_chars:
            continue
        entry = mem_chars[npc_name]
        for metric in rel_metrics:
            raw = rel.get(metric)
            if isinstance(raw, (int, float)):
                val = round(max(0.0, min(1.0, float(raw) / 100.0)), 2)
                entry[metric] = val
                entry.setdefault("metric_history", {}).setdefault(metric, []).append([0, val])
        rel_type = rel.get("relationshipType", "")
        if rel_type:
            entry["relationship_type"] = rel_type
        for tag in rel.get("tags") or []:
            flag = f"关系：{tag}"
            if flag not in entry.get("flags", []):
                entry.setdefault("flags", []).append(flag)
        for state_key, state_ch in state_chars.items():
            if state_ch.get("name") == npc_name:
                state_ch["relation"] = initial_relation_label(
                    npc_name,
                    is_main=False,
                    relationship=[],
                    char_relations=char_relations,
                )
                break

    initial_state = {
        "scene": scene,
        "status": "SETUP",
        "turn": 0,
        "characters": state_chars,
        "history": [],
        "force_event_pending": False,
        "chapter": 1,
    }
    from engine.objective_system import default_objectives

    initial_state["objectives"] = default_objectives(main_goal_text)
    from engine.state_store import commit_bundle

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
    initial_memory = {
        "characters": mem_chars,
        "world_flags": [],
        "global_trust": 0.5,
        "relationship_system": rel_config,
    }
    from engine.relationship_core import init_graph_from_world
    from engine.relationship_dynamics import empty_dynamics_store
    from engine.relationship_memory import empty_store

    relationship_graph = init_graph_from_world(
        world_pack, initial_memory, initial_state, persist=False,
    )
    relationship_memory = empty_store()
    relationship_dynamics = empty_dynamics_store()
    commit_bundle(
        initial_state,
        initial_memory,
        initial_graph,
        chapter="",
        relationship=relationship_graph,
        relationship_memory=relationship_memory,
        relationship_dynamics=relationship_dynamics,
    )

    from engine.plot_director import init_plot_state
    plot_state = init_plot_state(world_pack)

    from engine.candidate_npcs import reset_pool
    reset_pool(persist=True)

    # Save factory-reset snapshot so reset() can restore the user's world
    io_utils.write_json(config.WORLD_INIT_PATH, {
        "state": initial_state,
        "graph": initial_graph,
        "memory": initial_memory,
        "plot_state": plot_state,
        "relationship_graph": relationship_graph,
        "relationship_memory": relationship_memory,
        "relationship_dynamics": relationship_dynamics,
    })

    # Redirect to main page
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=config.frontend_url("/game"), status_code=303)


# ── AI World Generator ─────────────────────────────────────────────

def _parse_form_bool(val: str | None) -> bool | None:
    if val is None:
        return None
    s = str(val).strip().lower()
    if not s:
        return None
    if s in ("true", "1", "on", "yes"):
        return True
    if s in ("false", "0", "off", "no"):
        return False
    return None


def _world_gen_effective_mode(form_adult: str = "") -> bool:
    config.reload_app_behavior()
    parsed = _parse_form_bool(form_adult)
    if parsed is not None:
        return parsed
    return bool(config.ADULT_MODE)


@router.post("/generate-world")
async def generate_world(keywords: str = Form(""), adult_mode: str = Form("")):
    """Generate a world setting from keywords using DeepSeek."""
    from fastapi.responses import JSONResponse
    from engine.deepseek_client import call_deepseek, DeepSeekError

    kw = keywords.strip()
    if not kw:
        return JSONResponse({"error": "请输入关键词"}, status_code=400)

    adult = _world_gen_effective_mode(adult_mode)
    system = config.world_gen_system_prompt(adult_mode=adult)
    user = f"""输入内容：{kw}

{config.world_gen_task_intro(adult_mode=adult)}

{{
  "title": "故事标题（8~20字）",
  "world": "世界观/背景描述（50-300字）",
  "genre": ["标签1", "标签2"],
  "scene": "初始场景/地点名称",
  "main_goal": "故事主线目标（一句话）",
  "factions": [
    {{
      "name": "势力名",
      "type": "government|corporation|family|organization|guild|school|religion|kingdom|other",
      "description": "势力描述（20-80字）",
      "goals": ["目标1", "目标2"],
      "resources": ["资源1"],
      "controlledTerritories": ["控制区域"],
      "subordinateOrganizations": ["下属机构"],
      "keyAssets": ["关键资产"],
      "power": {{"military": 0, "economic": 0, "political": 0, "technology": 0}},
      "influence": 50,
      "relation_to_player": "neutral",
      "leader": "首领角色姓名（须与 characters 中某角色 name 一致）"
    }}
  ],
  "characters": [
    {{
      "name": "角色姓名",
      "isMain": true,
      "faction": "势力名（必须与 factions 中某一项 name 完全一致，兼容旧字段）",
      "factionMemberships": [
        {{"faction": "明面所属势力名", "visibility": "public"}},
        {{"faction": "暗中隶属势力名（可选）", "visibility": "hidden"}}
      ],
      "role_tags": ["身份标签"],
      "personality_tags": ["性格标签1", "性格标签2", "性格标签3"],
      "appearance": "外貌特征（10~30字）",
      "relationship": ["与主角关系"],
      "goal": "角色目标",
      "secret": "隐藏秘密",
      "personality": {{
        "desire": "核心欲望（可与 goal 呼应）",
        "fear": "最深恐惧",
        "taboo": "行为禁忌（触犯时即使高好感也会拒绝）",
        "secret": "隐藏秘密（可与 secret 字段一致）",
        "values": ["价值观1", "价值观2"]
      }},
      "background": "背景经历（主角）",
      "special_ability": "特殊能力（主角）"
    }}
  ],
  "rel_stages": ["崩坏", "敌视", "对立", "冷漠", "疏远", "陌生", "认识", "信赖", "盟友", "羁绊"],
  "rel_affection": 0,
  "stats": [
    {{"key": "trust", "label": "好感度", "max": 100}}
  ],
  "artifacts": [
    {{
      "name": "物品名",
      "type": "personal|faction|world",
      "description": "物品描述（20-60字）",
      "ownerType": "character|faction|none",
      "ownerId": "持有者名",
      "importance": 50,
      "abilities": ["能力"],
      "tags": ["标签"]
    }}
  ],
  "characterRelations": {{
    "NPC姓名（与 characters 中非主角一致）": {{
      "relationshipType": "friend|lover|family|teacher|rival|ally|enemy",
      "affection": 0,
      "trust": 0,
      "respect": 0,
      "dependence": 0,
      "hostility": 0,
      "attraction": 0,
      "tags": ["关系标签1", "关系标签2", "关系标签3"]
    }}
  }}
}}

要求：
1. 先设计 factions（至少2个互相对立的势力），再为 characters 分配隶属；优先用 factionMemberships（可多个，visibility 为 public 或 hidden）；至少有一个 public 隶属；faction 字段可填主要明面势力名
2. factions[].leader 应填写该势力首领的角色姓名；首领通常 public 隶属本势力，也可有 hidden 双重身份
3. characters 必须包含 1 名主角（isMain:true）和至少 1 名 NPC（isMain:false）
4. 角色要有个性，包含外貌、性格标签、目标、隐藏秘密，以及 personality 人格核心（desire/fear/taboo/secret/values）；每个 NPC 的 taboo 须明确非空
5. 主角和至少1个NPC之间要有潜在的戏剧冲突或情感张力
6. 初始场景要具体、有画面感；world 不超过 300 字
7. stats 根据故事类型设计2-3个专属追踪维度
8. rel_stages 必须是双向的（负面←陌生→正面），共6-10个阶段
9. artifacts 生成2-3个有故事推动力的关键物品；ownerId 必须与已有角色名或势力名一致
10. characterRelations 的 key 必须与 NPC 的 name 完全一致；tags 选 2-4 个；六维数值要体现角色设定与戏剧张力
11. 所有文字用中文
12. 只输出JSON，不要输出markdown代码块或其他文字"""
    adult_body = config.world_gen_adult_requirements_body(adult_mode=adult)
    if adult_body:
        user += f"\n{adult_body}"
    user += config.world_gen_adult_requirements_suffix(adult_mode=adult)

    try:
        result = call_deepseek(system, user, temperature=0.9, max_tokens=config.world_gen_output_tokens(), skip_validation=True)
        if isinstance(result.get("world"), str):
            result["world"] = result["world"].strip()[:300]
        if result.get("characters") and result.get("factions"):
            result["characters"] = _link_character_factions(
                result.get("characters"), result.get("factions")
            )
        if result.get("characters"):
            result["characters"] = [
                _normalize_character_personality(dict(c))
                for c in (result.get("characters") or [])
                if isinstance(c, dict)
            ]
        if result.get("artifacts"):
            result["artifacts"] = _link_artifact_owners(
                result.get("artifacts"),
                result.get("characters"),
                result.get("factions"),
            )
        npc_names = [
            c.get("name", "")
            for c in (result.get("characters") or [])
            if not c.get("isMain") and c.get("name")
        ]
        if npc_names:
            result["characterRelations"] = _normalize_character_relations(
                result.get("characterRelations"), npc_names
            )
        result["adult_mode_applied"] = adult
        return JSONResponse(result)
    except DeepSeekError as exc:
        import logging
        logging.getLogger("world").error("generate-world failed: %s", exc)
        return JSONResponse({"error": f"AI 生成失败: {exc}"}, status_code=500)
    except Exception as exc:
        import logging
        logging.getLogger("world").error("generate-world failed: %s", exc, exc_info=True)
        return JSONResponse({"error": f"未知错误: {exc}"}, status_code=500)


# ── Field-level AI generation ─────────────────────────────────────

@router.post("/generate-field")
async def generate_field(field: str = Form(""), title: str = Form(""), world: str = Form(""),
                         genre: str = Form(""), char_name: str = Form(""), char_role: str = Form(""),
                         context: str = Form(""), adult_mode: str = Form("")):
    """Generate a single story field via AI (title, world, or character)."""
    from engine.deepseek_client import call_deepseek, DeepSeekError
    from fastapi.responses import JSONResponse as JR

    adult = _world_gen_effective_mode(adult_mode)
    system = config.world_gen_field_system_prompt(adult_mode=adult)
    adult_suffix = config.world_gen_adult_requirements_suffix(adult_mode=adult)

    if field == "title":
        user = f"根据以下世界观，生成一个吸引人的故事标题（8~20字）：\n{world or context}\n\n标题："
    elif field == "world":
        ctx = f"标题：{title}，风格：{genre}" if title else context
        kind = "成人向 Galgame" if adult else "Galgame"
        user = f"为以下 {kind} 生成世界观背景描述（50-300字，沉浸式叙事风格）：\n{ctx}\n\n世界观："
    elif field == "main_goal":
        ctx = f"标题：{title}，世界观：{world[:200] if world else context[:200]}"
        hint = "（须与情感/亲密关系推进相关）" if adult else ""
        user = f"为以下 Galgame 生成一个清晰的故事主线目标（一句话）{hint}：\n{ctx}\n\n主线目标："
    elif field == "scene":
        ctx = f"标题：{title}，世界观：{world[:200] if world else context[:200]}"
        user = f"为以下 Galgame 生成一个具体的开局场景名称：\n{ctx}\n\n场景："
    elif field == "genre":
        ctx = f"标题：{title}，世界观：{world[:200] if world else context[:200]}"
        extra = "；成人模式下须含「恋爱/后宫/成人向」至少一项" if adult else ""
        user = f"为以下 Galgame 推荐3-5个风格标签（校园、恋爱、后宫、日常、轻小说、科幻、奇幻、修仙、末日、悬疑、推理、克苏鲁、冒险、战争、搞笑、黑暗、治愈、百合、女性向、成人向{extra}）：\n{ctx}\n\n输出JSON数组：[\"标签1\", \"标签2\"]"
    elif field == "character":
        faction_ctx = context[:500] if context else "（暂无势力，faction 留空字符串）"
        adult_char_hint = (
            "女角色须有具体外貌吸引力；goal/secret 含情感或暧昧张力；禁止男男设定。"
            if adult else ""
        )
        user = f"""为以下故事生成一个完整的角色，用 JSON 格式输出：
故事标题：{title}
世界观：{world[:300] if world else context[:300]}
已有势力：{faction_ctx}
角色定位：{char_role or '重要NPC'}
{adult_char_hint}

输出格式：{{"name":"角色名","isMain":false,"faction":"主要明面势力（可选，与 factionMemberships 一致）","factionMemberships":[{{"faction":"势力名","visibility":"public|hidden"}}],"role_tags":["身份"],"personality_tags":["性格1","性格2","性格3"],"appearance":"外貌特征（10~30字）","relationship":["与主角关系"],"goal":"角色目标","secret":"隐藏秘密","personality":{{"desire":"核心欲望","fear":"最深恐惧","taboo":"行为禁忌","secret":"隐藏秘密","values":["价值观1","价值观2"]}}}}

要求：角色要有个性、有目标、有秘密；personality 须完整且 taboo 要明确（行为红线）；若已有势力列表，用 factionMemberships 指定隶属（可多个，hidden 表示暗中）；只输出JSON。"""
    elif field == "rel_system":
        ctx = f"标题：{title}，世界观：{world[:200] if world else context[:200]}"
        user = f"为以下 Galgame 推荐关系阶段系统（必须是双向的！包含正面和负面阶段，共6-10个）：\n{ctx}\n\n关系应有正反两面，例如：崩坏←敌视←对立←冷漠←疏远←陌生→认识→信赖→盟友→羁绊\n\n输出JSON：{{\"rel_stages\":[\"负面阶段\",...,\"陌生\",...,\"正面阶段\"],\"rel_affection\":0}}"
    elif field == "artifact":
        user = f"为以下故事生成一个关键物品（Artifact），用 JSON 格式输出：\n故事标题：{title}\n世界观：{world[:300] if world else context[:300]}\n\n输出格式：{{\"name\":\"物品名称（8字内）\",\"type\":\"personal|faction|world\",\"description\":\"物品描述（20-60字）\",\"ownerType\":\"character|faction|location|none\",\"ownerId\":\"持有者名（与已有角色或势力匹配，或留空）\",\"importance\":50-95,\"abilities\":[\"能力1\",\"能力2\"],\"tags\":[\"标签1\",\"标签2\"]}}\n\n要求：物品要有故事推动力，可以是传家宝、机密文件、武器、货币、信物等。只输出JSON。"
    elif field == "faction":
        user = f"为以下故事生成一个势力（Faction），用 JSON 格式输出：\n故事标题：{title}\n世界观：{world[:300] if world else context[:300]}\n\n输出格式：{{\"name\":\"势力名（6字内）\",\"type\":\"government|corporation|family|organization|guild|school|religion|kingdom|other\",\"description\":\"势力描述（20-80字）\",\"goals\":[\"目标1\",\"目标2\"],\"resources\":[\"资源1\",\"资源2\"],\"controlledTerritories\":[\"控制区域\"],\"subordinateOrganizations\":[\"下属机构\"],\"keyAssets\":[\"关键资产\"],\"power\":{{\"military\":0-100,\"economic\":0-100,\"political\":0-100,\"technology\":0-100}},\"influence\":10-100,\"relation_to_player\":\"ally|friendly|neutral|hostile|enemy\",\"leader\":\"首领名\"}}\n\n要求：势力要有明确目标和资源，能独立推动剧情。只输出JSON。"
    elif field == "character_relation":
        if not char_name.strip():
            return JR({"error": "请指定 NPC 姓名"}, status_code=400)
        user = f"""为以下 Galgame 生成主角与 NPC「{char_name}」的多维关系设定，JSON 格式：
故事标题：{title}
世界观：{world[:300] if world else context[:300]}
角色背景：{context[:400] if context else '（未提供）'}

输出格式：
{{"relationshipType":"friend|lover|family|teacher|rival|ally|enemy","affection":0-100,"trust":0-100,"respect":0-100,"dependence":0-100,"hostility":0-100,"attraction":0-100,"tags":["标签1","标签2","标签3"]}}

要求：tags 选 2-4 个有戏剧张力的关系标签（青梅竹马、救命恩人、秘密共享、竞争意识、单向暗恋、互相试探、过去纠葛、命运绑定、生死之交、不共戴天 等）。六维数值要与角色性格和剧情张力一致。只输出 JSON。"""
    else:
        return JR({"error": f"未知字段类型: {field}"}, status_code=400)

    if adult_suffix:
        user = user.rstrip() + adult_suffix

    try:
        result = call_deepseek(system, user, temperature=0.9, max_tokens=config.MAX_TOKENS, skip_validation=True)
        # For character field, try to parse JSON from response
        if field == "character":
            # The result might already be the character object (skip_validation mode)
            # or wrapped in a {"story": "..."} envelope
            if "name" in result:
                return JR(_finalize_character_field_result(result, context=context))
            story = result.get("story", "") or result.get("name", "") or ""
            parsed = _parse_json_object_from_story(story)
            if parsed and parsed.get("name"):
                return JR(_finalize_character_field_result(parsed, context=context))
            fallback = {
                "name": story.strip()[:20],
                "role_tags": [char_role] if char_role else [],
                "isMain": False,
                "personality_tags": [],
                "appearance": "",
                "relationship": [],
                "goal": "",
                "secret": "",
            }
            return JR(_finalize_character_field_result(fallback, context=context))
        if field == "artifact":
            # Normalize artifact result
            if "name" in result:
                result.setdefault("type", "personal")
                result.setdefault("description", "")
                result.setdefault("ownerType", "none")
                result.setdefault("ownerId", "")
                result.setdefault("importance", 50)
                result.setdefault("abilities", [])
                result.setdefault("tags", [])
                for f in ["abilities", "tags"]:
                    if f in result and not isinstance(result[f], list):
                        result[f] = [result[f]] if result[f] else []
                return JR(result)
            story = result.get("story", "")
            import re as _re4
            m = _re4.search(r'\{[^}]+\}', story)
            if m:
                import json as _json4
                try:
                    art = _json4.loads(m.group())
                    art.setdefault("type", "personal")
                    art.setdefault("ownerType", "none")
                    art.setdefault("ownerId", "")
                    art.setdefault("importance", 50)
                    return JR(art)
                except Exception:
                    pass
            return JR({"name": story.strip()[:20], "type": "personal", "description": story.strip()[:60], "ownerType": "none", "ownerId": "", "importance": 50, "abilities": [], "tags": []})
        if field == "faction":
            if "name" in result:
                result.setdefault("type", "organization")
                result.setdefault("influence", 50)
                result.setdefault("relation_to_player", "neutral")
                result.setdefault("goals", [])
                result.setdefault("resources", [])
                result.setdefault("power", {"military": 0, "economic": 0, "political": 0, "technology": 0})
                return JR(result)
            story = result.get("story", "")
            import re as _re5
            m = _re5.search(r'\{[^}]+\}', story)
            if m:
                import json as _json5
                try:
                    fac = _json5.loads(m.group())
                    fac.setdefault("type", "organization")
                    fac.setdefault("influence", 50)
                    return JR(fac)
                except Exception:
                    pass
            return JR({"name": story.strip()[:20], "type": "organization", "influence": 50, "relation_to_player": "neutral", "goals": [], "resources": []})
        if field == "character_relation":
            rel = None
            if isinstance(result, dict) and (
                "relationshipType" in result or "tags" in result or "affection" in result
            ):
                rel = result
            if rel is None:
                story = result.get("story", "") if isinstance(result, dict) else ""
                rel = _parse_json_object_from_story(story) or {}
            normalized = _normalize_character_relations({char_name: rel}, [char_name])
            return JR(normalized.get(char_name, _normalize_character_relations({}, [char_name])[char_name]))
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
        if isinstance(result, dict):
            result["adult_mode_applied"] = adult
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
    adult_mode: str = Form(""),
):
    """Generate story-specific custom tracking rules."""
    from fastapi.responses import JSONResponse
    from engine.deepseek_client import call_deepseek, DeepSeekError

    adult = _world_gen_effective_mode(adult_mode)
    system = config.world_gen_system_prompt("Galgame 规则设计师", adult_mode=adult)
    stat_hint = (
        "成人向故事优先：吸引力、信任、亲密、欲望张力 等维度，勿用纯战斗/政务维度。"
        if adult else
        "根据故事的世界观、势力结构、关键物品来定制。"
    )
    user = f"""故事标题：{title}
类型：{genre}
世界观：{world}
角色1：{char1_name}（{char1_role}）
角色2：{char2_name}（{char2_role}）

请为这个故事设计 2-3 个专属的角色追踪维度（替代通用的"好感度"）。
{stat_hint}
例如：
- 宫廷故事 → 忠诚度、权势、民心
- 修仙故事 → 修为、道心、羁绊
- 商战故事 → 信任度、影响力、筹码
- 成人向恋爱 → 吸引力、信任、亲密

同时设计 5-7 个**双向**关系阶段标签（必须有正反两面）：
崩坏←敌视←对立←冷漠←疏远←陌生→认识→信赖→盟友→羁绊

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
    user += config.world_gen_adult_requirements_suffix(adult_mode=adult)

    try:
        result = call_deepseek(system, user, temperature=0.9, max_tokens=config.MAX_TOKENS, skip_validation=True)
        if isinstance(result, dict):
            result["adult_mode_applied"] = adult
        return JSONResponse(result)
    except DeepSeekError as exc:
        return JSONResponse({"error": f"AI 生成失败: {exc}"}, status_code=500)


