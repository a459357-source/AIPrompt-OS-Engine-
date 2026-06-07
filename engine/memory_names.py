"""
memory_names.py — NPC 名称质量检测与 roster 解析
"""

from __future__ import annotations

import re

from engine.constants import COMMON_WORDS

# 泛化 NPC 称谓 — 命中直接拒绝进入 candidate / memory
GENERIC_NPC_NAMES: frozenset[str] = frozenset({
    "路人", "旅人", "神秘人", "黑衣人", "老人", "少女", "少年",
    "守卫", "士兵", "佣兵", "刺客", "商人", "行人", "旅者",
    "陌生人", "来客", "访客", "身影", "使者", "信使",
})

# 明显称谓/修饰 — 降低注册权重（需多 1 次出现才升级）
TITLE_WEIGHT_PATTERNS: tuple[str, ...] = (
    "之人", "之者", "使徒", "化身", "来客", "访客", "身影", "使者",
    "来自", "来自深渊", "来自虚空",
)

METRIC_TOKENS: frozenset[str] = frozenset({
    "affection", "trust", "respect", "dependence", "hostility", "attraction",
    "hostility", "trust_pct",
})

_NAME_BAD_START = set("的我你他她它们这那")
_NAME_VERB_CHARS = set(
    "做说看走动跑拿送给负负责打断找觉逐低继续压力装服回"
)
_FRAGMENT_CHARS = set(
    "倒吸盯着露出启动紧急主控要巨大知道彻底关闭接近"
    "把能也是远前个成半觉次再开室起过"
)


class NameVerdict:
    REJECT = "reject"
    LOW_WEIGHT = "low_weight"
    ACCEPT = "accept"


def is_valid_character_name(name: str) -> bool:
    """Reject narrative fragments and English metric tokens mistaken as names."""
    name = (name or "").strip()
    if len(name) < 2 or len(name) > 8:
        return False
    if name in GENERIC_NPC_NAMES or name in COMMON_WORDS:
        return False
    if name.lower() in METRIC_TOKENS:
        return False
    if re.fullmatch(r"[a-zA-Z_]+", name):
        return False
    cjk = sum(1 for c in name if "\u4e00" <= c <= "\u9fff")
    if cjk < len(name):
        return False
    if name[0] in _NAME_BAD_START:
        return False
    if any(c in _NAME_VERB_CHARS for c in name[1:]):
        return False
    if any(c in _FRAGMENT_CHARS for c in name):
        return False
    return True


def assess_npc_name(name: str) -> str:
    """
    Name quality for candidate registration.
    Returns NameVerdict.REJECT | LOW_WEIGHT | ACCEPT.
    """
    name = (name or "").strip()
    if not name:
        return NameVerdict.REJECT
    if name in GENERIC_NPC_NAMES:
        return NameVerdict.REJECT
    if len(name) > 8:
        return NameVerdict.REJECT
    if not is_valid_character_name(name):
        return NameVerdict.REJECT
    if any(p in name for p in TITLE_WEIGHT_PATTERNS):
        return NameVerdict.LOW_WEIGHT
    return NameVerdict.ACCEPT


def build_roster_names(
    memory: dict | None,
    world_pack: dict | None,
    session: dict | None = None,
) -> set[str]:
    """Canonical character names from world + session (always trusted)."""
    names: set[str] = set()
    if world_pack:
        world = world_pack.get("world", world_pack)
        for ch in world.get("characters", []):
            n = (ch.get("name") or "").strip()
            if n:
                names.add(n)
    if session:
        for sc in session.get("characters", {}).values():
            if isinstance(sc, dict):
                n = (sc.get("name") or "").strip()
                if n:
                    names.add(n)
    if memory:
        for n, data in memory.get("characters", {}).items():
            if not isinstance(data, dict):
                continue
            stage = data.get("npc_stage")
            if stage == "incubating":
                continue
            if data.get("tier") in ("主角", "核心", "重要"):
                names.add(n)
            elif is_valid_character_name(n) and data.get("role") not in ("story-detected", ""):
                names.add(n)
            elif is_valid_character_name(n) and data.get("npc_stage") == "active":
                names.add(n)
    return names


def is_roster_name(name: str, memory: dict, world_pack: dict, session: dict | None = None) -> bool:
    """True if name may receive trust / flags / memory updates."""
    name = (name or "").strip()
    if not name:
        return False
    roster = build_roster_names(memory, world_pack, session)
    if name in roster:
        return True
    mem = memory.get("characters", {}).get(name, {})
    if mem.get("npc_stage") == "active":
        return True
    if mem.get("tier") == "主角" or mem.get("tier") == "核心":
        return True
    return False


def is_memory_active_npc(name: str, memory: dict) -> bool:
    """Formal NPC that may receive trust deltas (3rd+ sighting)."""
    entry = memory.get("characters", {}).get(name)
    if not entry:
        return False
    if entry.get("tier") == "主角":
        return True
    if entry.get("npc_stage") == "active":
        return True
    if entry.get("npc_stage") is None and entry.get("tier") in ("核心", "重要"):
        return True
    return False


def resolve_roster_name(name: str, memory: dict, world_pack: dict, session: dict | None = None) -> str | None:
    """Fuzzy-match parsed hint to a known roster name."""
    name = (name or "").strip()
    if not name:
        return None
    roster = build_roster_names(memory, world_pack, session)
    if name in roster:
        return name
    for rn in roster:
        if name in rn or rn in name:
            return rn
    mem_chars = memory.get("characters", {})
    if name in mem_chars and is_memory_active_npc(name, memory):
        return name
    return None


def filter_context_character_names(memory: dict, world_pack: dict, session: dict | None = None) -> set[str]:
    """Names safe to show in prompt context."""
    names: set[str] = set()
    roster = build_roster_names(memory, world_pack, session)
    names.update(roster)
    for n, data in memory.get("characters", {}).items():
        if not isinstance(data, dict):
            continue
        if n in roster:
            continue
        if data.get("npc_stage") in ("active", None) and is_valid_character_name(n):
            if data.get("tier") in ("主角", "核心", "重要", "背景") and data.get("role") != "story-detected":
                names.add(n)
            elif data.get("npc_stage") == "active":
                names.add(n)
    return names
