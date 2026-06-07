"""Analyze player-supplied lore and merge into world_pack / runtime state."""

from __future__ import annotations

import json
import logging
from typing import Any

import config
from engine import io_utils
from engine.character_registry import initial_relation_label
from engine.deepseek_client import call_deepseek, DeepSeekError
from engine.memory import init_factions, load_memory, save_memory
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


def _build_analysis_context(world_pack: dict, session_state: dict) -> str:
    world = world_pack.get("world", {}) or {}
    chars = world.get("characters") or []
    factions = world.get("factions") or []
    custom = world_pack.get("custom") or {}

    char_lines = []
    for ch in chars[:24]:
        if not isinstance(ch, dict):
            continue
        name = ch.get("name", "?")
        tag = "主角" if ch.get("is_main") else "NPC"
        role = " / ".join(ch.get("role_tags") or []) if isinstance(ch.get("role_tags"), list) else ""
        char_lines.append(f"- {name}（{tag}）{(' · ' + role) if role else ''}")

    fac_lines = []
    for fac in factions[:16]:
        if not isinstance(fac, dict):
            continue
        fac_lines.append(f"- {fac.get('name', '?')}：{str(fac.get('description', ''))[:60]}")

    rel_raw = custom.get("characterRelations") or {}
    rel_lines = []
    if isinstance(rel_raw, dict):
        for npc, rel in list(rel_raw.items())[:12]:
            if isinstance(rel, dict):
                rel_lines.append(f"- {npc}：{rel.get('relationshipType', '?')} affection={rel.get('affection', '?')}")

    history = session_state.get("history") or []
    recent = ""
    if history:
        last = history[-1]
        recent = str(last.get("story") or last.get("summary") or "")[:600]

    existing_prompt = str(custom.get("story_prompt") or "").strip()
    prompt_note = existing_prompt[:400] + ("…" if len(existing_prompt) > 400 else "")

    return f"""【故事标题】{world.get('title', '')}
【世界观】{str(world.get('setting', ''))[:200]}
【主线】{str(world.get('main_goal', ''))[:120]}
【当前场景】{session_state.get('scene', '')}
【当前回合】T{session_state.get('turn', 0)} 状态={session_state.get('status', '')}

【已有角色】
{chr(10).join(char_lines) or '（无）'}

【已有势力】
{chr(10).join(fac_lines) or '（无）'}

【已有关系种子】
{chr(10).join(rel_lines) or '（无）'}

【已有故事补充 prompt（摘要）】
{prompt_note or '（无）'}

【最近剧情摘要】
{recent or '（故事尚未开始）'}"""


def _analysis_prompt(context: str, user_text: str) -> tuple[str, str]:
    system = (
        "你是 Galgame 设定分析师。玩家会在进行中补充世界观/角色/关系/叙事规则。"
        "请分析补充内容，输出合法 JSON。只输出 JSON，不要 markdown。"
    )
    user = f"""{context}

【玩家补充设定】
{user_text.strip()}

请分析并输出 JSON：
{{
  "story_prompt": "应写入本故事专属 prompt 的内容：叙事规则、风格禁忌、世界观细节、剧情约束等。与角色/势力/关系无关的 prompt 类内容放这里。无则空字符串。",
  "characters": [
    {{
      "action": "add 或 update",
      "name": "角色名（update 必须与已有角色名一致）",
      "is_main": false,
      "faction": "主要明面势力（可选）",
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
      "action": "add 或 update",
      "name": "势力名",
      "type": "organization",
      "description": "描述",
      "goals": ["目标"],
      "leader": "首领角色名",
      "power": {{"military": 50, "economic": 50, "political": 50, "technology": 50}},
      "influence": 50,
      "relation_to_player": "neutral"
    }}
  ],
  "characterRelations": {{
    "NPC姓名": {{
      "relationshipType": "friend|lover|family|teacher|rival|ally|enemy",
      "affection": 0,
      "trust": 0,
      "respect": 0,
      "dependence": 0,
      "hostility": 0,
      "attraction": 0,
      "tags": ["标签"]
    }}
  }},
  "summary": "用中文简要说明本次更新了哪些内容（给玩家看）"
}}

规则：
1. 仅根据玩家补充内容提取/推断，不要编造无关设定
2. prompt 类（写作风格、禁忌、剧情规则）→ story_prompt；实体类 → characters/factions/relations
3. update 只填需要变更的字段；add 需填完整基础信息
4. 不要修改主角 is_main=true 的身份；新增 NPC 默认 is_main=false
5. characterRelations 的 key 必须与 NPC 姓名一致
6. 若无某类更新，对应字段用空数组 {{}} 或空字符串"""
    return system, user


def _normalize_analysis(raw: dict, npc_names: list[str]) -> dict:
    out = {
        "story_prompt": str(raw.get("story_prompt") or "").strip(),
        "characters": [],
        "factions": [],
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

    rel_raw = raw.get("characterRelations")
    if isinstance(rel_raw, dict):
        for npc in npc_names:
            if npc not in rel_raw or not isinstance(rel_raw.get(npc), dict):
                continue
            rel = rel_raw[npc]
            rel_type = rel.get("relationshipType", "friend")
            if rel_type not in _REL_TYPES:
                rel_type = "friend"
            tags = rel.get("tags") or []
            if not isinstance(tags, list):
                tags = [tags] if tags else []
            out["characterRelations"][npc] = {
                "relationshipType": rel_type,
                **{m: _clamp_rel_metric(rel.get(m), 50) for m in _REL_METRICS},
                "tags": [str(t).strip() for t in tags if t and str(t).strip()][:6],
            }
    return out


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
            if action == "add":
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
    npc_names = [
        str(c.get("name", "")).strip()
        for c in (world.get("characters") or [])
        if isinstance(c, dict) and c.get("name") and not c.get("is_main")
    ]
    return _normalize_analysis(raw, npc_names)


def apply_supplement(analysis: dict) -> dict:
    """Merge analyzed supplement into world_pack and runtime. Returns change summary."""
    world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)
    runtime = load_runtime(clear_cache=True)
    session_state = runtime.session
    memory = runtime.memory
    custom = world_pack.setdefault("custom", {})

    all_changes: list[str] = []

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
        "characters": len(analysis.get("characters") or []),
        "factions": len(analysis.get("factions") or []),
        "relations": len(analysis.get("characterRelations") or {}),
    }
    return result
