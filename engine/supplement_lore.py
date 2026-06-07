"""Analyze player-supplied lore and merge into world_pack / runtime state.

Field coverage aligns with NewStory one-click generation (WorldGenResponse):
title, world, genre, scene, main_goal, characters, factions, artifacts,
stats, rel_stages, rel_affection, characterRelations — plus story_prompt
for in-game narrative rules that are not part of world-gen JSON.
"""

from __future__ import annotations

import logging
from typing import Any

import config
from engine import io_utils
from engine.character_registry import initial_relation_label
from engine.deepseek_client import call_deepseek, DeepSeekError
from engine.memory import init_artifacts, init_factions
from engine.memory_layers import build_world_summary_from_pack
from engine.state_store import commit_runtime, load_runtime

logger = logging.getLogger(__name__)

_REL_TYPES = frozenset({"friend", "lover", "family", "teacher", "rival", "ally", "enemy"})
_REL_METRICS = ("affection", "trust", "respect", "dependence", "hostility", "attraction")
_CHAR_PATCH_KEYS = (
    "role_tags", "personality_tags", "appearance", "relationship",
    "goal", "secret", "background", "special_ability", "faction",
    "factionMemberships", "faction_memberships", "is_main",
)
_FACTION_PATCH_KEYS = (
    "type", "description", "goals", "resources", "controlledTerritories",
    "subordinateOrganizations", "keyAssets", "power", "influence",
    "relation_to_player", "leader",
)
_ARTIFACT_PATCH_KEYS = (
    "type", "description", "ownerType", "ownerId", "importance",
    "abilities", "tags", "relatedCharacters", "relatedFactions", "status",
)


def _clamp_rel_metric(value: Any, default: int = 50) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(100, n))


def _find_by_name(items: list[dict], name: str) -> dict | None:
    name = str(name or "").strip()
    if not name:
        return None
    for item in items:
        if isinstance(item, dict) and str(item.get("name", "")).strip() == name:
            return item
    for item in items:
        if isinstance(item, dict):
            iname = str(item.get("name", "")).strip()
            if iname and (name in iname or iname in name):
                return item
    return None


def _merge_dict(base: dict, patch: dict, keys: tuple[str, ...]) -> dict:
    out = dict(base)
    for key in keys:
        val = patch.get(key)
        if val is None:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        if isinstance(val, list) and not val:
            continue
        out[key] = val
    return out


def _remap_relation_keys(raw: dict, npc_names: list[str]) -> dict:
    if not isinstance(raw, dict):
        return {}
    remapped: dict = {}
    used: set[str] = set()
    for npc in npc_names:
        if not npc:
            continue
        if npc in raw and isinstance(raw.get(npc), dict):
            remapped[npc] = raw[npc]
            used.add(npc)
            continue
        for key, val in raw.items():
            if key in used or not isinstance(val, dict):
                continue
            key_str = str(key)
            if key_str == npc or key_str in npc or npc in key_str:
                remapped[npc] = val
                used.add(key_str)
                break
    return remapped


def _normalize_rel_entry(rel: dict) -> dict:
    rel_type = rel.get("relationshipType", "friend")
    if rel_type not in _REL_TYPES:
        rel_type = "friend"
    tags = rel.get("tags") or []
    if not isinstance(tags, list):
        tags = [tags] if tags else []
    return {
        "relationshipType": rel_type,
        **{m: _clamp_rel_metric(rel.get(m), 50) for m in _REL_METRICS},
        "tags": [str(t).strip() for t in tags if t and str(t).strip()][:6],
    }


def _normalize_stats(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for s in raw:
        if not isinstance(s, dict):
            continue
        key = str(s.get("key") or "stat").strip()
        if not key:
            continue
        action = str(s.get("action") or "update").lower()
        if action not in ("add", "update"):
            action = "update"
        out.append({
            "action": action,
            "key": key,
            "label": str(s.get("label") or key).strip(),
            "max": s.get("max", 100) if isinstance(s.get("max"), (int, float)) else 100,
        })
    return out


def _npc_names_from_world(world: dict, extra: list[str] | None = None) -> list[str]:
    names = [
        str(c.get("name", "")).strip()
        for c in (world.get("characters") or [])
        if isinstance(c, dict) and c.get("name") and not c.get("is_main")
    ]
    for n in extra or []:
        if n and n not in names:
            names.append(n)
    return names


def _build_analysis_context(world_pack: dict, session_state: dict) -> str:
    world = world_pack.get("world", {}) or {}
    custom = world_pack.get("custom") or {}
    rel_sys = world.get("relationship_system") or {}

    char_lines = []
    for ch in (world.get("characters") or [])[:24]:
        if not isinstance(ch, dict):
            continue
        name = ch.get("name", "?")
        tag = "主角" if ch.get("is_main") else "NPC"
        role = " / ".join(ch.get("role_tags") or []) if isinstance(ch.get("role_tags"), list) else ""
        char_lines.append(f"- {name}（{tag}）{(' · ' + role) if role else ''}")

    fac_lines = []
    for fac in (world.get("factions") or [])[:16]:
        if isinstance(fac, dict):
            fac_lines.append(f"- {fac.get('name', '?')}：{str(fac.get('description', ''))[:60]}")

    art_lines = []
    for art in (world.get("artifacts") or [])[:12]:
        if isinstance(art, dict):
            art_lines.append(
                f"- {art.get('name', '?')}（{art.get('type', '?')}）持有者={art.get('ownerId', '无')}"
            )

    stat_lines = []
    for s in (custom.get("stats") or [])[:8]:
        if isinstance(s, dict):
            stat_lines.append(f"- {s.get('label', s.get('key', '?'))}")

    rel_raw = custom.get("characterRelations") or {}
    rel_lines = []
    if isinstance(rel_raw, dict):
        for npc, rel in list(rel_raw.items())[:12]:
            if isinstance(rel, dict):
                rel_lines.append(f"- {npc}：{rel.get('relationshipType', '?')}")

    genre = world.get("genre") or []
    if isinstance(genre, str):
        genre = [genre]
    stages = rel_sys.get("stages") or custom.get("stages") or []

    history = session_state.get("history") or []
    recent = ""
    if history:
        last = history[-1]
        recent = str(last.get("story") or last.get("summary") or "")[:600]

    existing_prompt = str(custom.get("story_prompt") or "").strip()
    prompt_note = existing_prompt[:400] + ("…" if len(existing_prompt) > 400 else "")

    loc_names = [
        str(loc.get("name", "")).strip()
        for loc in (world.get("locations") or [])
        if isinstance(loc, dict) and loc.get("name")
    ]

    return f"""【故事标题】{world.get('title', '')}
【类型标签】{' / '.join(str(g) for g in genre) or '（无）'}
【世界观】{str(world.get('setting', ''))[:200]}
【主线】{str(world.get('main_goal', ''))[:120]}
【初始/已知场景】{' / '.join(loc_names) or session_state.get('scene', '')}
【当前场景】{session_state.get('scene', '')}
【当前回合】T{session_state.get('turn', 0)} 状态={session_state.get('status', '')}
【关系阶段链】{' → '.join(str(s) for s in stages[:12]) or '（默认）'}
【初始好感】{rel_sys.get('affection', 0)}

【已有角色】
{chr(10).join(char_lines) or '（无）'}

【已有势力】
{chr(10).join(fac_lines) or '（无）'}

【已有关键物品】
{chr(10).join(art_lines) or '（无）'}

【已有追踪维度】
{chr(10).join(stat_lines) or '（无）'}

【已有关系种子】
{chr(10).join(rel_lines) or '（无）'}

【已有故事补充 prompt（摘要）】
{prompt_note or '（无）'}

【最近剧情摘要】
{recent or '（故事尚未开始）'}"""


def _analysis_prompt(context: str, user_text: str) -> tuple[str, str]:
    system = (
        "你是 Galgame 设定分析师。玩家会在游戏进行中补充设定。"
        "输出字段须与「一键生成完整设定」同一套数据结构（见下方 JSON）。"
        "只输出合法 JSON，不要 markdown。"
    )
    user = f"""{context}

【玩家补充设定】
{user_text.strip()}

请分析并输出 JSON（与新建故事「一键生成」字段对齐，另加 story_prompt）：
{{
  "story_prompt": "叙事规则/风格禁忌/剧情约束等，仅写入本故事 prompt，不放实体设定。无则空字符串",
  "title": "故事标题（8~20字，仅变更时填写，否则省略或空字符串）",
  "world": "世界观背景（50~300字，仅变更时填写）",
  "genre": ["类型标签"],
  "scene": "场景/地点名称（仅变更或新增地点时填写）",
  "scene_desc": "场景描述（可选，配合 scene）",
  "main_goal": "主线目标（仅变更时填写）",
  "rel_stages": ["关系阶段标签，6~10个，双向从疏远到亲密，仅变更时填写"],
  "rel_affection": 0,
  "stats": [
    {{"action": "add|update", "key": "english_key", "label": "中文维度名", "max": 100}}
  ],
  "characters": [
    {{
      "action": "add|update",
      "name": "角色名",
      "is_main": false,
      "faction": "主要明面势力",
      "factionMemberships": [{{"faction": "势力名", "visibility": "public|hidden"}}],
      "role_tags": ["身份"],
      "personality_tags": ["性格"],
      "appearance": "外貌",
      "relationship": ["与主角关系"],
      "goal": "目标",
      "secret": "秘密",
      "background": "背景",
      "special_ability": "能力"
    }}
  ],
  "factions": [
    {{
      "action": "add|update",
      "name": "势力名",
      "type": "government|corporation|family|organization|guild|school|religion|kingdom|other",
      "description": "描述",
      "goals": ["目标"],
      "resources": ["资源"],
      "controlledTerritories": ["区域"],
      "subordinateOrganizations": ["下属"],
      "keyAssets": ["资产"],
      "power": {{"military": 0, "economic": 0, "political": 0, "technology": 0}},
      "influence": 50,
      "relation_to_player": "neutral",
      "leader": "首领角色名"
    }}
  ],
  "artifacts": [
    {{
      "action": "add|update",
      "name": "物品名",
      "type": "personal|faction|world",
      "description": "描述",
      "ownerType": "character|faction|none",
      "ownerId": "持有者名",
      "importance": 50,
      "abilities": ["能力"],
      "tags": ["标签"]
    }}
  ],
  "characterRelations": {{
    "NPC姓名": {{
      "relationshipType": "friend|lover|family|teacher|rival|ally|enemy",
      "affection": 0, "trust": 0, "respect": 0,
      "dependence": 0, "hostility": 0, "attraction": 0,
      "tags": ["标签"]
    }}
  }},
  "summary": "用中文简要说明本次更新了哪些内容"
}}

规则：
1. 仅根据玩家补充提取/推断，不要编造无关内容
2. 写作规则/禁忌/叙事约束 → story_prompt；结构化设定 → 对应字段
3. update 只填变更字段；add 需填完整基础信息
4. 不修改主角 is_main；新增角色默认 NPC
5. characterRelations 的 key 须与 NPC 姓名一致（含本次 add 的角色）
6. ownerId / leader / faction 须与已有或本次新增的角色/势力名一致
7. 未涉及的字段：字符串用 ""，数组用 []，数字可省略"""
    return system, user


def _normalize_analysis(raw: dict, npc_names: list[str]) -> dict:
    genre = raw.get("genre")
    if isinstance(genre, str):
        genre = [genre.strip()] if genre.strip() else []
    elif not isinstance(genre, list):
        genre = []

    rel_stages = raw.get("rel_stages")
    if not isinstance(rel_stages, list):
        rel_stages = []
    rel_stages = [str(s).strip() for s in rel_stages if s and str(s).strip()]

    out: dict[str, Any] = {
        "story_prompt": str(raw.get("story_prompt") or "").strip(),
        "title": str(raw.get("title") or "").strip()[:20],
        "world": str(raw.get("world") or "").strip()[:300],
        "genre": [str(g).strip() for g in genre if g and str(g).strip()],
        "scene": str(raw.get("scene") or "").strip(),
        "scene_desc": str(raw.get("scene_desc") or "").strip(),
        "main_goal": str(raw.get("main_goal") or "").strip(),
        "rel_stages": rel_stages,
        "rel_affection": raw.get("rel_affection"),
        "stats": _normalize_stats(raw.get("stats")),
        "characters": [],
        "factions": [],
        "artifacts": [],
        "characterRelations": {},
        "summary": str(raw.get("summary") or "设定已更新").strip(),
    }

    for entry in raw.get("characters") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        action = str(entry.get("action") or "update").lower()
        if action not in ("add", "update"):
            action = "update"
        out["characters"].append({"action": action, "name": name, **entry})
        if action == "add" and not entry.get("is_main") and name not in npc_names:
            npc_names.append(name)

    for entry in raw.get("factions") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        action = str(entry.get("action") or "update").lower()
        if action not in ("add", "update"):
            action = "update"
        out["factions"].append({"action": action, "name": name, **entry})

    for entry in raw.get("artifacts") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        action = str(entry.get("action") or "update").lower()
        if action not in ("add", "update"):
            action = "update"
        out["artifacts"].append({"action": action, "name": name, **entry})

    rel_raw = raw.get("characterRelations")
    if isinstance(rel_raw, dict):
        remapped = _remap_relation_keys(rel_raw, npc_names)
        for npc, rel in remapped.items():
            if isinstance(rel, dict):
                out["characterRelations"][npc] = _normalize_rel_entry(rel)

    return out


def _apply_world_core(analysis: dict, world_pack: dict, session_state: dict) -> list[str]:
    changes: list[str] = []
    world = world_pack.setdefault("world", {})

    if analysis.get("title"):
        world["title"] = analysis["title"]
        changes.append("更新标题")
    if analysis.get("world"):
        world["setting"] = analysis["world"]
        changes.append("更新世界观")
    if analysis.get("genre"):
        world["genre"] = analysis["genre"]
        changes.append("更新类型标签")
    if analysis.get("main_goal"):
        world["main_goal"] = analysis["main_goal"]
        changes.append("更新主线目标")

    scene = analysis.get("scene") or ""
    if scene:
        locations: list = world.setdefault("locations", [])
        existing = _find_by_name(locations, scene)
        desc = analysis.get("scene_desc") or ""
        if existing:
            if desc:
                existing["desc"] = desc[:200]
            changes.append(f"更新场景：{scene}")
        else:
            locations.append({"name": scene, "desc": desc[:200] if desc else "补充设定地点"})
            changes.append(f"新增场景：{scene}")

    return changes


def _apply_rel_system(analysis: dict, world_pack: dict) -> list[str]:
    changes: list[str] = []
    world = world_pack.setdefault("world", {})
    custom = world_pack.setdefault("custom", {})
    rel_sys = world.setdefault("relationship_system", {"stages": [], "affection": 0})

    stages = analysis.get("rel_stages") or []
    if stages:
        rel_sys["stages"] = stages
        custom["stages"] = stages
        changes.append("更新关系阶段")

    aff = analysis.get("rel_affection")
    if isinstance(aff, (int, float)):
        rel_sys["affection"] = max(0, min(100, int(aff)))
        changes.append("更新初始好感")

    return changes


def _apply_stats(entries: list[dict], custom: dict) -> list[str]:
    if not entries:
        return []
    stats: list = list(custom.get("stats") or [])
    changes: list[str] = []
    by_key = {str(s.get("key", "")): s for s in stats if isinstance(s, dict) and s.get("key")}

    for entry in entries:
        key = entry["key"]
        label = entry.get("label") or key
        max_val = entry.get("max", 100)
        action = entry.get("action", "update")
        if action == "add" and key not in by_key:
            by_key[key] = {"key": key, "label": label, "max": max_val}
            changes.append(f"新增追踪维度：{label}")
        elif key in by_key:
            by_key[key]["label"] = label
            by_key[key]["max"] = max_val
            changes.append(f"更新追踪维度：{label}")
        else:
            by_key[key] = {"key": key, "label": label, "max": max_val}
            changes.append(f"新增追踪维度：{label}")

    custom["stats"] = list(by_key.values())
    return changes


def _char_note(ch: dict) -> str:
    parts = []
    if ch.get("appearance"):
        parts.append(f"外貌：{ch['appearance']}")
    tags = ch.get("personality_tags") or []
    if isinstance(tags, list) and tags:
        parts.append(f"性格：{' / '.join(str(t) for t in tags)}")
    rel = ch.get("relationship") or []
    if isinstance(rel, list) and rel and not ch.get("is_main"):
        parts.append(f"关系：{' / '.join(str(r) for r in rel)}")
    for key, label in (("goal", "目标"), ("secret", "秘密"), ("background", "背景"), ("special_ability", "能力")):
        if ch.get(key):
            parts.append(f"{label}：{ch[key]}")
    return "\n".join(parts)


def _apply_characters(
    entries: list[dict],
    world_pack: dict,
    session_state: dict,
    memory: dict,
    char_relations: dict,
) -> list[str]:
    changes: list[str] = []
    world = world_pack.setdefault("world", {})
    wp_chars: list = world.setdefault("characters", [])
    session_chars = session_state.setdefault("characters", {})
    mem_chars = memory.setdefault("characters", {})

    for entry in entries:
        name = entry["name"]
        action = entry["action"]
        existing = _find_by_name(wp_chars, name)

        if action == "add":
            if existing:
                action = "update"
            else:
                ch = {
                    "name": name,
                    "is_main": bool(entry.get("is_main", False)),
                    "faction": str(entry.get("faction") or "").strip(),
                    "role_tags": entry.get("role_tags") or [],
                    "personality_tags": entry.get("personality_tags") or [],
                    "appearance": entry.get("appearance") or "",
                    "relationship": entry.get("relationship") or [],
                    "goal": entry.get("goal") or "",
                    "secret": entry.get("secret") or "",
                    "background": entry.get("background") or "",
                    "special_ability": entry.get("special_ability") or "",
                }
                memberships = entry.get("factionMemberships") or entry.get("faction_memberships")
                if isinstance(memberships, list) and memberships:
                    ch["faction_memberships"] = memberships
                wp_chars.append(ch)
                existing = ch
                changes.append(f"新增角色：{name}")

        if action == "update" and existing:
            merged = _merge_dict(existing, entry, _CHAR_PATCH_KEYS)
            merged["name"] = name
            idx = wp_chars.index(existing)
            wp_chars[idx] = merged
            existing = merged
            changes.append(f"更新角色：{name}")

        if not existing:
            continue

        role_tags = existing.get("role_tags") or []
        if isinstance(role_tags, str):
            role_tags = [role_tags]
        role_str = " / ".join(str(t) for t in role_tags if t)
        is_main = bool(existing.get("is_main"))

        state_entry = next(
            (v for v in session_chars.values() if isinstance(v, dict) and v.get("name") == name),
            None,
        )
        if state_entry is None:
            letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            used = set(session_chars.keys())
            key = next((letters[i] for i in range(len(letters)) if letters[i] not in used), f"X{len(session_chars)}")
            state_entry = {"name": name, "role": role_str, "level": "L0", "relation": "", "note": ""}
            session_chars[key] = state_entry
            changes.append(f"注册到当前会话：{name}")

        state_entry["role"] = role_str or state_entry.get("role", "")
        note = _char_note(existing)
        if note:
            state_entry["note"] = note
        state_entry["relation"] = initial_relation_label(
            name, is_main=is_main, relationship=existing.get("relationship") or [], char_relations=char_relations,
        )

        mem = mem_chars.setdefault(name, {"trust": 0.5, "flags": [], "relationship": state_entry["relation"]})
        mem["relationship"] = state_entry["relation"]
        if existing.get("secret"):
            flag = f"隐藏秘密：{existing['secret']}"
            if flag not in mem.get("flags", []):
                mem.setdefault("flags", []).append(flag)
        if existing.get("faction"):
            mem["faction"] = existing["faction"]

    return changes


def _apply_factions(entries: list[dict], world_pack: dict, memory: dict) -> list[str]:
    changes: list[str] = []
    world = world_pack.setdefault("world", {})
    wp_factions: list = world.setdefault("factions", [])

    for entry in entries:
        name = entry["name"]
        action = entry["action"]
        existing = _find_by_name(wp_factions, name)

        if action == "add" and not existing:
            fac = {"name": name, "type": entry.get("type") or "organization", "description": entry.get("description") or ""}
            fac = _merge_dict(fac, entry, _FACTION_PATCH_KEYS)
            wp_factions.append(fac)
            changes.append(f"新增势力：{name}")
        elif existing:
            idx = wp_factions.index(existing)
            wp_factions[idx] = _merge_dict(existing, entry, _FACTION_PATCH_KEYS)
            wp_factions[idx]["name"] = name
            changes.append(f"更新势力：{name}")

    init_factions(memory)
    return changes


def _apply_artifacts(entries: list[dict], world_pack: dict, memory: dict) -> list[str]:
    changes: list[str] = []
    world = world_pack.setdefault("world", {})
    wp_arts: list = world.setdefault("artifacts", [])

    for entry in entries:
        name = entry["name"]
        action = entry["action"]
        existing = _find_by_name(wp_arts, name)

        if action == "add" and not existing:
            art = {
                "name": name,
                "type": entry.get("type") or "personal",
                "description": entry.get("description") or "",
                "ownerType": entry.get("ownerType") or "none",
                "ownerId": entry.get("ownerId") or "",
                "importance": entry.get("importance", 50),
                "status": entry.get("status") or "active",
                "abilities": entry.get("abilities") or [],
                "tags": entry.get("tags") or [],
            }
            art = _merge_dict(art, entry, _ARTIFACT_PATCH_KEYS)
            wp_arts.append(art)
            changes.append(f"新增关键物品：{name}")
        elif existing:
            idx = wp_arts.index(existing)
            wp_arts[idx] = _merge_dict(existing, entry, _ARTIFACT_PATCH_KEYS)
            wp_arts[idx]["name"] = name
            changes.append(f"更新关键物品：{name}")

    init_artifacts(memory)
    return changes


def _apply_relations(rel_patch: dict, custom: dict, session_state: dict, memory: dict) -> list[str]:
    if not rel_patch:
        return []
    merged = dict(custom.get("characterRelations") or {})
    merged.update(rel_patch)
    custom["characterRelations"] = merged

    changes: list[str] = []
    mem_chars = memory.setdefault("characters", {})
    session_chars = session_state.get("characters") or {}

    for npc_name, rel in rel_patch.items():
        entry = mem_chars.setdefault(npc_name, {"trust": 0.5, "flags": [], "relationship": ""})
        for metric in _REL_METRICS:
            raw = rel.get(metric)
            if isinstance(raw, (int, float)):
                val = round(max(0.0, min(1.0, float(raw) / 100.0)), 2)
                entry[metric] = val
        rel_type = rel.get("relationshipType", "")
        if rel_type:
            entry["relationship_type"] = rel_type
        for tag in rel.get("tags") or []:
            flag = f"关系：{tag}"
            if flag not in entry.get("flags", []):
                entry.setdefault("flags", []).append(flag)

        label = initial_relation_label(
            npc_name, is_main=False, relationship=[], char_relations=merged,
        )
        entry["relationship"] = label
        for state_ch in session_chars.values():
            if isinstance(state_ch, dict) and state_ch.get("name") == npc_name:
                state_ch["relation"] = label
                break
        changes.append(f"更新关系：{npc_name}")

    return changes


def analyze_supplement(user_text: str) -> dict:
    """Call AI to analyze supplement text. Raises DeepSeekError on failure."""
    text = str(user_text or "").strip()
    if not text:
        raise ValueError("请输入补充设定内容")
    if len(text) > 4000:
        raise ValueError("补充内容过长，请控制在 4000 字以内")

    world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
    session_state = io_utils.read_yaml(config.SESSION_STATE_PATH)
    context = _build_analysis_context(world_pack, session_state)

    system, user = _analysis_prompt(context, text)
    raw = call_deepseek(
        system, user,
        temperature=0.7,
        max_tokens=min(config.MAX_TOKENS, 4096),
        skip_validation=True,
    )
    if not isinstance(raw, dict):
        raise DeepSeekError("AI 返回格式无效")

    world = world_pack.get("world", {}) or {}
    add_npc = [
        str(e.get("name", "")).strip()
        for e in (raw.get("characters") or [])
        if isinstance(e, dict) and e.get("action") == "add" and not e.get("is_main")
    ]
    npc_names = _npc_names_from_world(world, add_npc)
    return _normalize_analysis(raw, npc_names)


def apply_supplement(analysis: dict) -> dict:
    """Merge analyzed supplement into world_pack and runtime. Returns change summary."""
    world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
    runtime = load_runtime(clear_cache=True)
    session_state = runtime.session
    memory = runtime.memory
    custom = world_pack.setdefault("custom", {})

    all_changes: list[str] = []

    all_changes.extend(_apply_world_core(analysis, world_pack, session_state))
    all_changes.extend(_apply_rel_system(analysis, world_pack))
    all_changes.extend(_apply_stats(analysis.get("stats") or [], custom))

    prompt_add = str(analysis.get("story_prompt") or "").strip()
    if prompt_add:
        prev = str(custom.get("story_prompt") or "").strip()
        custom["story_prompt"] = f"{prev}\n\n{prompt_add}".strip() if prev else prompt_add
        all_changes.append("已追加故事专属 prompt")

    char_relations = dict(custom.get("characterRelations") or {})
    all_changes.extend(_apply_characters(
        analysis.get("characters") or [],
        world_pack, session_state, memory, char_relations,
    ))
    all_changes.extend(_apply_factions(analysis.get("factions") or [], world_pack, memory))
    all_changes.extend(_apply_artifacts(analysis.get("artifacts") or [], world_pack, memory))
    all_changes.extend(_apply_relations(
        analysis.get("characterRelations") or {},
        custom, session_state, memory,
    ))

    io_utils.write_yaml(config.WORLD_PACK_PATH, world_pack)
    io_utils.write_json(config.WORLD_SUMMARY_PATH, build_world_summary_from_pack(world_pack))

    runtime.session = session_state
    runtime.memory = memory
    commit_runtime(runtime)

    summary = analysis.get("summary") or "设定已更新"
    return {
        "summary": summary,
        "changes": all_changes,
        "story_prompt_added": bool(prompt_add),
    }


def supplement_lore(user_text: str) -> dict:
    """Analyze and apply supplement lore in one call."""
    analysis = analyze_supplement(user_text)
    result = apply_supplement(analysis)
    result["analysis"] = {
        "world_core": bool(
            analysis.get("title") or analysis.get("world") or analysis.get("genre")
            or analysis.get("main_goal") or analysis.get("scene")
        ),
        "rel_system": bool(analysis.get("rel_stages") or analysis.get("rel_affection") is not None),
        "stats": len(analysis.get("stats") or []),
        "characters": len(analysis.get("characters") or []),
        "factions": len(analysis.get("factions") or []),
        "artifacts": len(analysis.get("artifacts") or []),
        "relations": len(analysis.get("characterRelations") or {}),
        "story_prompt": bool(analysis.get("story_prompt")),
    }
    return result
