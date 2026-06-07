"""
memory.py — Character Memory System
=====================================
Tracks character trust levels, relationship flags, and world events
across turns. Feeds memory context back into the prompt so the AI
"remembers" what happened.

Data model (memory.json):
  {
    "characters": {
      "<name>": {
        "trust": 0.0–1.0,
        "flags": ["事件标识1", "事件标识2"],
        "relationship": "当前关系描述"
      }
    },
    "world_flags": ["全局事件标识"],
    "global_trust": 0.0–1.0
  }
"""

import logging

import config
from engine import io_utils
from engine.constants import (
    TRUST_KEYWORDS_POSITIVE, TRUST_KEYWORDS_NEGATIVE, FLAG_KEYWORDS,
    COMMON_WORDS, RELATIONSHIP_TRUST, RELATION_TO_PLAYER_MAP,
    DEFAULT_INITIAL_TRUST, DEFAULT_NEUTRAL_TRUST, STORY_DETECTED_TRUST_FACTOR,
)

logger = logging.getLogger(__name__)


def load_memory() -> dict:
    """Load the memory from disk."""
    return io_utils.read_json(config.MEMORY_PATH)


def save_memory(memory: dict, *, persist: bool = True) -> None:
    """Persist memory to disk (skipped when persist=False)."""
    if persist:
        io_utils.write_json(config.MEMORY_PATH, memory)


def update_trust(memory: dict, character: str, delta: float, turn: int = 0,
                 metric: str = "trust") -> None:
    """
    Adjust a character's numeric metric by delta (clamped to 0.0–1.0).
    Creates the character entry if it doesn't exist.
    If turn > 0, appends to metric_history for analytics.

    Args:
        metric: Name of the metric to update (default "trust").
                Different stories may track different metrics:
                好感度, 恐惧值, 羁绊, 声望, etc.
    """
    chars = memory.setdefault("characters", {})
    entry = chars.setdefault(character, {"trust": 0.3, "flags": [], "relationship": ""})

    # Backward-compat: also set top-level field for the primary metric
    old = entry.get(metric, 0.5 if metric == "trust" else 0.0)
    new = round(max(0.0, min(1.0, old + delta)), 2)
    entry[metric] = new

    # Generic metric history tracking (per-metric, not just trust)
    if turn > 0:
        all_history = entry.setdefault("metric_history", {})
        hist = all_history.setdefault(metric, [])
        # Deduplicate: only append if value actually changed
        if not hist or hist[-1][1] != new:
            hist.append([turn, new])

    logger.info("Memory: %s %s %s → %s", character, metric, old, entry[metric])


def set_flag(memory: dict, character: str | None, flag: str) -> None:
    """
    Add a flag to a character (or to world_flags if character is None).
    Idempotent — won't duplicate.
    """
    if character is None:
        flags = memory.setdefault("world_flags", [])
        if flag not in flags:
            flags.append(flag)
            logger.info("Memory: world flag set → %s", flag)
    else:
        chars = memory.setdefault("characters", {})
        entry = chars.setdefault(character, {"trust": 0.5, "flags": [], "relationship": ""})
        if flag not in entry.setdefault("flags", []):
            entry["flags"].append(flag)
            logger.info("Memory: %s flag set → %s", character, flag)


def update_relationship(memory: dict, character: str, relationship: str) -> None:
    """Set the relationship descriptor for a character."""
    chars = memory.setdefault("characters", {})
    entry = chars.setdefault(character, {"trust": 0.5, "flags": [], "relationship": ""})
    entry["relationship"] = relationship


def get_context_for_prompt(memory: dict) -> str:
    """
    Build a concise context string for injection into the LLM prompt.
    Summarizes trust levels and recent flags.
    """
    lines: list[str] = []
    chars = memory.get("characters", {})

    if chars:
        lines.append("【角色关系记忆】")
        for name, data in chars.items():
            trust = data.get("trust", 0.5)
            rel = data.get("relationship", "")
            flags = data.get("flags", [])
            metric_history = data.get("metric_history", {})
            trust_label = _trust_label(trust)
            line = f"  {name}: 信任度 {trust:.0%}（{trust_label}）, 关系: {rel or '无'}"
            # Include other tracked metrics
            for metric_key, hist in metric_history.items():
                if metric_key != "trust" and hist:
                    line += f", {metric_key}: {hist[-1][1]:.0%}"
            lines.append(line)
            if flags:
                lines.append(f"    已触发事件: {', '.join(flags)}")

    # Include relationship system info if present
    rel_system = memory.get("relationship_system", {})
    if rel_system:
        stages = rel_system.get("stages", [])
        if stages:
            lines.append(f"【关系阶段系统】{' → '.join(stages)}")

    # ── Faction status ────────────────────────────────────────
    factions = memory.get("factions", {})
    if factions:
        lines.append("【势力状态】")
        for fname, fdata in factions.items():
            rep = fdata.get("reputation", 0.5)
            label = _attitude_label(rep)
            ftype = fdata.get("type", "other")
            goals = fdata.get("goals", [])
            resources = fdata.get("resources", [])
            influence = fdata.get("influence", 50)
            flags = fdata.get("flags", [])
            line = f"  {fname}（{ftype}）: 声望 {rep:.0%}（{label}）, 影响力 {influence}"
            lines.append(line)
            if goals:
                lines.append(f"    目标: {'; '.join(goals[:3])}")
            if resources:
                lines.append(f"    资源: {', '.join(resources[:5])}")
            if flags:
                lines.append(f"    事件: {', '.join(flags)}")

    # ── Key inter-faction attitudes (non-neutral only) ────────
    attitudes = memory.get("faction_attitudes", {})
    if attitudes:
        significant: list[str] = []
        for a, targets in attitudes.items():
            for b, data in targets.items():
                att = data.get("attitude", 0.5)
                if abs(att - 0.5) >= 0.15:  # only show non-trivial
                    label = _attitude_label(att)
                    significant.append(f"{a}→{b}: {label}({att:.0%})")
        if significant:
            lines.append("【势力间关键态度】")
            for s in significant:
                lines.append(f"  {s}")

    world_flags = memory.get("world_flags", [])
    if world_flags:
        lines.append("【全局事件】")
        for f in world_flags:
            lines.append(f"  • {f}")

    return "\n".join(lines) if lines else ""


def _trust_label(trust: float) -> str:
    """Human-readable trust level."""
    if trust >= 0.8:
        return "深厚信任"
    elif trust >= 0.6:
        return "信任"
    elif trust >= 0.4:
        return "初步信任"
    elif trust >= 0.2:
        return "戒备"
    else:
        return "敌对/疏远"


# ── Faction tracking ────────────────────────────────────────────────

def init_factions(memory: dict) -> None:
    """Auto-register factions from world_pack.yaml into memory."""
    world = io_utils.read_yaml(config.WORLD_PACK_PATH)
    factions_raw = world.get("world", {}).get("factions", [])
    mem_factions = memory.setdefault("factions", {})

    for faction in factions_raw:
        name = faction.get("name", "")
        if not name:
            continue
        if name not in mem_factions:
            # Compute initial reputation from relation_to_player
            rel = faction.get("relation_to_player", "neutral")
            init_rep = RELATION_TO_PLAYER_MAP.get(rel, 0.50)
            influence = faction.get("influence", 50)
            power = faction.get("power", {})
            mem_factions[name] = {
                "reputation": init_rep,
                "flags": [],
                "role": faction.get("role", ""),
                "type": faction.get("type", "other"),
                "goals": faction.get("goals", []),
                "resources": faction.get("resources", []),
                "controlledTerritories": faction.get("controlledTerritories", []),
                "subordinateOrganizations": faction.get("subordinateOrganizations", []),
                "keyAssets": faction.get("keyAssets", []),
                "power": {
                    "military": power.get("military", 0),
                    "economic": power.get("economic", 0),
                    "political": power.get("political", 0),
                    "technology": power.get("technology", 0),
                },
                "influence": influence,
                "leader": faction.get("leader", ""),
                "relation_to_player": rel,
                "metric_history": {"reputation": [[0, init_rep]]},
            }
            logger.info("Memory: auto-registered faction '%s' (type=%s, rep=%.2f, influence=%d)",
                        name, faction.get("type", "?"), init_rep, influence)


def update_faction_reputation(memory: dict, faction: str, delta: float,
                               turn: int = 0) -> None:
    """Adjust a faction's reputation by delta (0.0-1.0)."""
    factions = memory.setdefault("factions", {})
    entry = factions.setdefault(faction, {
        "reputation": 0.5, "flags": [], "role": "",
        "metric_history": {"reputation": []},
    })
    old = entry.get("reputation", 0.5)
    new = round(max(0.0, min(1.0, old + delta)), 2)
    entry["reputation"] = new

    if turn > 0:
        mh = entry.setdefault("metric_history", {}).setdefault("reputation", [])
        if not mh or mh[-1][1] != new:
            mh.append([turn, new])

    logger.info("Memory: faction %s reputation %s → %s", faction, old, new)


def set_faction_flag(memory: dict, faction: str, flag: str) -> None:
    """Add a flag to a faction."""
    factions = memory.setdefault("factions", {})
    entry = factions.setdefault(faction, {
        "reputation": 0.5, "flags": [], "role": "",
        "metric_history": {"reputation": []},
    })
    if flag not in entry.setdefault("flags", []):
        entry["flags"].append(flag)


def update_faction_influence(memory: dict, faction: str, delta: int) -> None:
    """Adjust a faction's influence by delta (0-100 scale)."""
    factions = memory.setdefault("factions", {})
    entry = factions.setdefault(faction, {
        "reputation": 0.5, "flags": [], "role": "",
        "type": "other", "goals": [], "resources": [],
        "influence": 50, "leader": "", "relation_to_player": "neutral",
        "metric_history": {"reputation": []},
    })
    old = entry.get("influence", 50)
    new = max(0, min(100, old + delta))
    entry["influence"] = new
    logger.info("Memory: faction %s influence %d → %d", faction, old, new)


# ── Inter-faction attitude tracking ────────────────────────────────
# Directed graph: Faction A's attitude toward Faction B.
# Stored as memory["faction_attitudes"][faction_a][faction_b] = {
#     "attitude": 0.0–1.0 (0=hostile, 0.5=neutral, 1=allied),
#     "flags": [], "metric_history": {"attitude": [[turn, value]]}
# }

def init_faction_attitudes(memory: dict) -> None:
    """Ensure the faction_attitudes dict exists and seed defaults."""
    attitudes = memory.setdefault("faction_attitudes", {})
    factions = memory.get("factions", {})

    # Ensure every faction pair has an entry
    fnames = list(factions.keys())
    for a in fnames:
        ad = attitudes.setdefault(a, {})
        for b in fnames:
            if a == b:
                continue
            if b not in ad:
                # Default: neutral (0.5), or slightly cooperative if same world
                ad[b] = {
                    "attitude": 0.5,
                    "flags": [],
                    "metric_history": {"attitude": []},
                }
    logger.info("Memory: faction_attitudes initialized for %d factions", len(fnames))


def update_faction_attitude(memory: dict, faction_a: str, faction_b: str,
                            delta: float, turn: int = 0) -> None:
    """
    Adjust faction_a's attitude toward faction_b by delta (0.0–1.0).
    Creates entries if missing.
    """
    if faction_a == faction_b:
        return
    attitudes = memory.setdefault("faction_attitudes", {})
    ad = attitudes.setdefault(faction_a, {})
    entry = ad.setdefault(faction_b, {
        "attitude": 0.5, "flags": [],
        "metric_history": {"attitude": []},
    })
    old = entry.get("attitude", 0.5)
    new = round(max(0.0, min(1.0, old + delta)), 2)
    entry["attitude"] = new

    if turn > 0:
        mh = entry.setdefault("metric_history", {}).setdefault("attitude", [])
        if not mh or mh[-1][1] != new:
            mh.append([turn, new])

    logger.info("Memory: %s → %s attitude %s → %s", faction_a, faction_b, old, new)


def set_faction_attitude_flag(memory: dict, faction_a: str, faction_b: str,
                               flag: str) -> None:
    """Add a flag to an inter-faction relationship."""
    if faction_a == faction_b:
        return
    attitudes = memory.setdefault("faction_attitudes", {})
    ad = attitudes.setdefault(faction_a, {})
    entry = ad.setdefault(faction_b, {
        "attitude": 0.5, "flags": [],
        "metric_history": {"attitude": []},
    })
    if flag not in entry.setdefault("flags", []):
        entry["flags"].append(flag)


def _attitude_label(attitude: float) -> str:
    """Human-readable inter-faction attitude label."""
    if attitude >= 0.8:
        return "同盟"
    elif attitude >= 0.6:
        return "友好"
    elif attitude >= 0.4:
        return "中立"
    elif attitude >= 0.2:
        return "冷淡"
    else:
        return "敌对"


def get_faction_attitude_context(memory: dict) -> str:
    """Build a prompt-ready summary of inter-faction attitudes."""
    attitudes = memory.get("faction_attitudes", {})
    if not attitudes:
        return ""

    lines: list[str] = ["【势力间态度】"]
    for a, targets in sorted(attitudes.items()):
        for b, data in sorted(targets.items()):
            att = data.get("attitude", 0.5)
            label = _attitude_label(att)
            flags = data.get("flags", [])
            flag_str = f" ({', '.join(flags)})" if flags else ""
            lines.append(f"  {a} → {b}: {label} ({att:.0%}){flag_str}")
    return "\n".join(lines)


def get_faction_stats_for_ui(memory: dict) -> list[dict]:
    """
    Return faction data for UI display — similar to get_char_stats_for_ui.
    Each entry: {name, role, reputation_pct, attitude_label, flags, attitudes}
    """
    factions = memory.get("factions", {})
    attitudes = memory.get("faction_attitudes", {})
    result: list[dict] = []

    for name, data in factions.items():
        rep = data.get("reputation", 0.5)
        rep_pct = round((rep - 0.5) * 200)  # -100..100

        # Build inter-faction attitude summary
        faction_attitudes: list[dict] = []
        ad = attitudes.get(name, {})
        for target, adata in sorted(ad.items()):
            faction_attitudes.append({
                "target": target,
                "attitude": adata.get("attitude", 0.5),
                "label": _attitude_label(adata.get("attitude", 0.5)),
                "flags": adata.get("flags", []),
            })

        result.append({
            "name": name,
            "role": data.get("role", ""),
            "type": data.get("type", "other"),
            "goals": data.get("goals", []),
            "resources": data.get("resources", []),
            "controlledTerritories": data.get("controlledTerritories", []),
            "subordinateOrganizations": data.get("subordinateOrganizations", []),
            "keyAssets": data.get("keyAssets", []),
            "power": data.get("power", {}),
            "influence": data.get("influence", 50),
            "leader": data.get("leader", ""),
            "relation_to_player": data.get("relation_to_player", "neutral"),
            "reputation_pct": rep_pct,
            "reputation": rep,
            "attitude_label": _attitude_label(rep),
            "flags": data.get("flags", []),
            "attitudes": faction_attitudes,
        })

    return result


def get_faction_context_for_prompt(memory: dict) -> str:
    """
    Build a detailed faction scope summary for the AI prompt.
    Includes controlled territories, subordinate organizations,
    key assets, and power scores — so AI can generate concrete
    faction actions instead of vague ones.
    """
    factions = memory.get("factions", {})
    if not factions:
        return ""

    lines: list[str] = ["【势力掌控范围 — AI必须据此生成具体行动】"]
    for name, data in factions.items():
        ftype = data.get("type", "other")
        goals = data.get("goals", [])
        territories = data.get("controlledTerritories", [])
        orgs = data.get("subordinateOrganizations", [])
        assets = data.get("keyAssets", [])
        power = data.get("power", {})
        rel_player = data.get("relation_to_player", "neutral")

        lines.append(f"\n  [{name}] 类型:{ftype} 对主角:{rel_player}")
        if goals:
            lines.append(f"    目标: {'; '.join(goals[:3])}")
        if territories:
            lines.append(f"    控制区域: {', '.join(territories)}")
        if orgs:
            lines.append(f"    下属机构: {', '.join(orgs)}")
        if assets:
            lines.append(f"    关键资产: {', '.join(assets)}")
        if power:
            pw = power
            lines.append(f"    实力: 军事{pw.get('military',0)} 经济{pw.get('economic',0)} 政治{pw.get('political',0)} 科技{pw.get('technology',0)}")

        # Allowed action hints per type
        hints = _faction_action_hints(ftype, territories, orgs, assets)
        if hints:
            lines.append(f"    可执行行动: {', '.join(hints[:5])}")

    lines.append("")
    lines.append("  【AI规则】生成势力行动时必须：1) 行动范围不超过控制区域 2) 执行者来自下属机构 3) 手段基于关键资产 4) 规模匹配实力评分")
    return "\n".join(lines)


def _faction_action_hints(
    ftype: str, territories: list[str],
    orgs: list[str], assets: list[str],
) -> list[str]:
    """Generate allowed-action hints based on faction scope."""
    hints: list[str] = []

    if territories:
        hints.append(f"在{territories[0]}部署力量")
    if orgs:
        hints.append(f"通过{orgs[0]}执行任务")
    if assets:
        hints.append(f"利用{assets[0]}")
    if ftype == "government":
        hints.extend(["颁布法令", "调动国家资源", "外交谈判", "封锁区域"])
    elif ftype == "corporation":
        hints.extend(["资本运作", "收购资产", "市场操控", "游说政府"])
    elif ftype == "family":
        hints.extend(["暗中布局", "人脉运作", "联姻结盟", "信息交易"])
    elif ftype in ("organization", "guild", "school"):
        hints.extend(["成员行动", "资源调配", "情报收集", "同盟协作"])
    elif ftype in ("religion",):
        hints.extend(["信徒动员", "教义传播", "朝圣行动", "神谕解读"])
    elif ftype in ("kingdom",):
        hints.extend(["出兵讨伐", "王室联姻", "册封领地", "发布诏令"])

    return hints


# ── Artifact tracking ──────────────────────────────────────────────

def init_artifacts(memory: dict) -> None:
    """Auto-register artifacts from world_pack.yaml into memory."""
    world = io_utils.read_yaml(config.WORLD_PACK_PATH)
    artifacts_raw = world.get("world", {}).get("artifacts", [])
    mem_artifacts = memory.setdefault("artifacts", {})

    for art in artifacts_raw:
        name = art.get("name", "")
        if not name:
            continue
        if name not in mem_artifacts:
            mem_artifacts[name] = {
                "type": art.get("type", "personal"),
                "description": art.get("description", ""),
                "ownerType": art.get("ownerType", "none"),
                "ownerId": art.get("ownerId", ""),
                "previousOwners": art.get("previousOwners", []),
                "importance": art.get("importance", 50),
                "abilities": art.get("abilities", []),
                "tags": art.get("tags", []),
                "relatedCharacters": art.get("relatedCharacters", []),
                "relatedFactions": art.get("relatedFactions", []),
                "status": art.get("status", "active"),
                "transferHistory": [],
            }
            logger.info("Memory: auto-registered artifact '%s' (type=%s, owner=%s)",
                        name, art.get("type", "?"), art.get("ownerId", "none"))


def transfer_artifact(memory: dict, artifact_name: str, new_owner_type: str,
                      new_owner_id: str, turn: int = 0, reason: str = "") -> bool:
    """Transfer an artifact to a new owner. Records transfer history."""
    arts = memory.setdefault("artifacts", {})
    if artifact_name not in arts:
        return False
    art = arts[artifact_name]
    old_owner = f"{art.get('ownerType','?')}:{art.get('ownerId','')}"
    art["previousOwners"].append(art.get("ownerId", ""))
    art["ownerType"] = new_owner_type
    art["ownerId"] = new_owner_id
    art["transferHistory"].append({
        "turn": turn,
        "from": old_owner,
        "to": f"{new_owner_type}:{new_owner_id}",
        "reason": reason,
    })
    logger.info("Artifact: '%s' transferred %s → %s:%s (turn %d)",
                artifact_name, old_owner, new_owner_type, new_owner_id, turn)
    return True


def set_artifact_status(memory: dict, artifact_name: str, status: str) -> bool:
    """Set artifact status: active, lost, destroyed, sealed."""
    arts = memory.setdefault("artifacts", {})
    if artifact_name not in arts:
        return False
    arts[artifact_name]["status"] = status
    logger.info("Artifact: '%s' status → %s", artifact_name, status)
    return True


def get_artifact_context_for_prompt(memory: dict) -> str:
    """Build a prompt-ready summary of key artifacts."""
    arts = memory.get("artifacts", {})
    if not arts:
        return ""

    lines: list[str] = ["【关键物品】"]
    for name, data in arts.items():
        status = data.get("status", "active")
        if status != "active":
            continue
        owner_type = data.get("ownerType", "none")
        owner_id = data.get("ownerId", "")
        importance = data.get("importance", 50)
        abilities = data.get("abilities", [])
        tags = data.get("tags", [])
        lines.append(f"  [{name}] 重要性:{importance} 持有者:{owner_type}:{owner_id} 状态:{status}")
        if abilities:
            lines.append(f"    能力: {'; '.join(abilities[:3])}")
        if tags:
            lines.append(f"    标签: {', '.join(tags)}")
    lines.append("  【AI规则】物品可转移、可争夺、可遗失——围绕物品状态变化生成剧情冲突。")
    return "\n".join(lines)


def get_artifact_stats_for_ui(memory: dict) -> list[dict]:
    """Return artifact data for UI display."""
    arts = memory.get("artifacts", {})
    result: list[dict] = []
    for name, data in arts.items():
        result.append({
            "name": name,
            "type": data.get("type", "personal"),
            "description": data.get("description", "")[:80],
            "ownerType": data.get("ownerType", "none"),
            "ownerId": data.get("ownerId", ""),
            "importance": data.get("importance", 50),
            "status": data.get("status", "active"),
            "abilities": data.get("abilities", []),
            "tags": data.get("tags", []),
            "transferCount": len(data.get("transferHistory", [])),
        })
    return sorted(result, key=lambda x: x["importance"], reverse=True)


def guess_trust_delta_from_story(story: str) -> list[tuple[str, float, str | None]]:
    """
    Heuristic: scan the story text for character names near sentiment
    keywords to guess trust changes and flags.

    For each keyword match, looks for known character names within a
    30-char window around the keyword.  If a specific character is
    found, the delta applies only to that character.  If no character
    is found nearby, the delta is halved and applied to all characters
    in the story (generic scene sentiment).

    Returns a list of (character, delta, optional_flag).
    This is a simple keyword-based heuristic — not AI-powered.
    """
    import re

    results: list[tuple[str, float, str | None]] = []

    positive_keywords = TRUST_KEYWORDS_POSITIVE
    negative_keywords = TRUST_KEYWORDS_NEGATIVE
    flag_keywords = FLAG_KEYWORDS

    def _find_nearby_char(kw: str) -> str | None:
        """Find a known character name within ~30 chars of the keyword."""
        idx = story.find(kw)
        if idx < 0:
            return None
        window_start = max(0, idx - 30)
        window_end = min(len(story), idx + len(kw) + 30)
        window = story[window_start:window_end]
        # Look for 2-4 char Chinese names (simple heuristic)
        for m in re.finditer(r'[\u4e00-\u9fff]{2,4}', window):
            name = m.group()
            if name in COMMON_WORDS:
                continue
            # Also skip if the name contains only extremely common chars
            if all(c in '的一是不了在有人我他这来们说个到和地着就你也那要看没' for c in name):
                continue
            return name
        return None

    for kw, delta in positive_keywords.items():
        if kw in story:
            char = _find_nearby_char(kw)
            if char:
                results.append((char, delta, None))
            else:
                # No specific character found — apply halved delta to all
                results.append(("__all_present__", round(delta * 0.5, 2), None))

    for kw, delta in negative_keywords.items():
        if kw in story:
            char = _find_nearby_char(kw)
            if char:
                results.append((char, delta, None))
            else:
                results.append(("__all_present__", round(delta * 0.5, 2), None))

    for kw, flag in flag_keywords.items():
        if kw in story:
            char = _find_nearby_char(kw)
            target = char if char else "__all_present__"
            results.append((target, 0.02, flag))

    return results


# ── Initial trust from world_pack relationships ─────────────────

# All hardcoded dicts moved to engine/constants.py — imported at top of file.


def get_initial_trust(name: str, world_pack: dict | None = None) -> float:
    """
    Compute initial trust for a character based on their world_pack
    relationship tags.  Falls back to 0.30 for unknown characters
    (slightly wary, not neutral).
    """
    if not world_pack:
        return 0.30
    world_chars = world_pack.get("world", {}).get("characters", [])
    for wc in world_chars:
        if wc.get("name") == name:
            relationships = wc.get("relationship", [])
            if not relationships:
                return 0.35
            # Use the best-matching relationship tag
            best = 0.30
            for rel in relationships:
                if rel in RELATIONSHIP_TRUST:
                    best = max(best, RELATIONSHIP_TRUST[rel])
            # Also check negative tags — take the minimum
            for rel in relationships:
                if rel in RELATIONSHIP_TRUST:
                    val = RELATIONSHIP_TRUST[rel]
                    if val < 0.35:  # negative relationship
                        best = min(best, val)
            return round(best, 2)
    # Not in world_pack — NPC, slightly wary
    return 0.30


def detect_new_characters_from_story(story: str,
                                     known_names: set[str]) -> list[str]:
    """
    Scan story text for likely Chinese character names that aren't
    already in memory.  Used as a fallback when the AI forgets to
    register a new character in state.characters.

    Heuristic:
      - Find 2-4 char Chinese sequences that appear near introduction
        patterns: "名叫", "自称", "一位…的", "来了", "出现", "走进"
      - Filter out anything already known.
      - Only return names that appear multiple times or near verbs.

    Returns list of candidate names (may include false positives).
    """
    import re

    candidates: list[str] = []

    # Pattern: explicit character introduction phrases.
    # Only use high-precision patterns to avoid false positives.
    #   "名叫X" / "叫做X" / "自称X" / "一位叫X的Y"
    # X is 2-3 chars; the trailing particle (的/，/。) acts as a boundary.
    _NC = r'[\u4e00-\u9fff]'  # name char
    intro_patterns = [
        # "名叫X" / "叫做X" / "称为X" — explicit naming, highest precision
        rf'(?:名叫|叫做|称为)\s*({_NC}{{2,4}})',
        # "自称X" — but NOT "自称是…" (which means "claimed that…")
        rf'自称\s*(?!是)({_NC}{{2,4}})',
        # "一位叫X" / "一个叫X" / "名为X" / "姓X"
        rf'(?:一位叫|一个叫|名为|姓)\s*({_NC}{{2,4}})',
        # AI explicitly introduced a character in state: "新角色：X" or "X加入了"
        rf'(?:新角色|新人)[：:]\s*({_NC}{{2,4}})',
    ]
    # NOTE: bare "叫X" pattern removed — too many false positives
    # from sentences like "林夜叫停了操作" / "这叫什么事"

    for pat in intro_patterns:
        for m in re.finditer(pat, story):
            name = m.group(1).strip()
            if not name or name in known_names or len(name) < 2:
                continue
            # Strip trailing particle if greedy match overshot
            while len(name) > 2 and name[-1] in '的了是出到来去说看':
                name = name[:-1]
            if len(name) < 2:
                continue
            # Reject if all high-frequency particles
            if all(c in '的了是我也就不这人一个来去说看' for c in name):
                continue
            # Reject story fragments: names containing common verbs/particles
            _FRAGMENT_CHARS = set('倒吸盯着露出启动紧急主控要巨大知道彻底关闭接近'
                                 '把能也是远前个成半觉次再开室起过')
            if any(c in _FRAGMENT_CHARS for c in name):
                continue
            candidates.append(name)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    return unique


def parse_option_metric_deltas(options: list[str]) -> list[tuple[str, str, float]]:
    """
    Parse relationship hints from option strings.

    Supports:
      - 艾琳↑5 / 林夜↓3  → trust
      - 艾琳 affection+3 trust-1
      - 艾琳信任度+10
    Returns (character_name, metric_key, delta) with delta in 0–1 scale.
    """
    import re

    METRIC_ALIASES = {
        "trust": "trust", "信任": "trust", "信任度": "trust",
        "affection": "affection", "好感": "affection", "好感度": "affection",
        "respect": "respect", "尊重": "respect", "respect度": "respect",
        "dependence": "dependence", "依赖": "dependence",
        "hostility": "hostility", "敌意": "hostility",
        "attraction": "attraction", "吸引": "attraction",
    }

    results: list[tuple[str, str, float]] = []
    arrow_pattern = re.compile(
        r'([\u4e00-\u9fff·]{1,12}|[A-Za-z_]\w{1,19})\s*'
        r'([↑➕\+↓➖\-])\s*'
        r'(\d+)'
    )
    metric_pattern = re.compile(
        r'([\u4e00-\u9fff·]{1,12}|[A-Za-z_]\w{1,19})\s*'
        r'(affection|trust|respect|dependence|hostility|attraction|好感度?|信任度?|尊重度?|依赖度?|敌意度?|吸引度?)'
        r'\s*([+\-➕➖]?)\s*'
        r'(\d+)',
        re.IGNORECASE,
    )

    def _delta_from_sign(sign: str, value: int) -> float:
        if sign in ('↑', '➕', '+', ''):
            d = value / 100.0
        else:
            d = -value / 100.0
        return max(-1.0, min(1.0, d))

    for opt in options:
        if not isinstance(opt, str):
            continue
        segments = opt.split("|")
        target = segments[-1] if segments else opt
        # Also scan full option for custom free-text hints
        for scan in (target, opt):
            for match in arrow_pattern.finditer(scan):
                name = match.group(1)
                results.append((name, "trust", _delta_from_sign(match.group(2), int(match.group(3)))))
            for match in metric_pattern.finditer(scan):
                name = match.group(1)
                raw_metric = match.group(2).lower()
                sign = match.group(3) or '+'
                value = int(match.group(4))
                metric = METRIC_ALIASES.get(raw_metric, "trust")
                results.append((name, metric, _delta_from_sign(sign if sign else '+', value)))

    # Deduplicate last wins
    seen: dict[tuple[str, str], float] = {}
    for name, metric, delta in results:
        seen[(name, metric)] = delta
    return [(n, m, d) for (n, m), d in seen.items()]


def parse_option_trust_deltas(options: list[str]) -> list[tuple[str, float]]:
    """
    Parse AI-generated trust hints from option strings.

    The AI writes hints like:
      "艾琳↑5、林夜↓3、新人+10"
      "与皋月并肩作战，近卫↑8、卡洛琳↓5"

    Patterns matched:
      name↑N   → +N/100
      name↓N   → -N/100
      name+N   → +N/100
      name-N   → -N/100
      name➕N  → +N/100
      name➖N  → -N/100

    Returns list of (character_name, delta) where delta is in 0-1 range.
    """
    return [(name, delta) for name, metric, delta in parse_option_metric_deltas(options) if metric == "trust"]


# ── UI helpers ─────────────────────────────────────────────────────

# 7-stage affection progression on 0-100 scale (50 = neutral)
_AFFECTION_STAGES = [
    (50,  "陌生"),
    (55,  "认识"),
    (65,  "熟悉"),
    (75,  "朋友"),
    (85,  "暧昧"),
    (95,  "恋人"),
    (100, "灵魂伴侣"),
]

_BAD_STAGES = [
    (50,  "正常"),
    (40,  "疏远"),
    (30,  "冷漠"),
    (20,  "对立"),
    (10,  "敌视"),
    (0,   "崩坏"),
]


def get_char_stats_for_ui(session_state: dict, memory: dict, world_pack: dict | None = None) -> list[dict]:
    """
    Merge session_state characters with memory data into a clean list
    for UI rendering. Each entry:

      { name, role, level, trust_pct, stage, hearts, flags, custom_stats }

    trust_pct: -100..100 (negative = bad stages, positive = good stages)
    stage:     human-readable stage label
    hearts:    "♥♥♥♡♡" style string (5 hearts)
    flags:     list of triggered event names
    custom_stats: list of {key, label, value} from world_pack.custom
    """
    # Load custom rules
    custom_stats_config = []
    custom_stages = []
    if world_pack:
        custom = world_pack.get("custom", {})
        custom_stats_config = custom.get("stats", [])
        custom_stages = custom.get("stages", [])
    state_chars = session_state.get("characters", {})
    mem_chars = memory.get("characters", {})

    result: list[dict] = []
    for key, sc in state_chars.items():
        name = sc.get("name", key)
        mem = mem_chars.get(name, {})
        trust = mem.get("trust", 0.5)  # 0.0–1.0
        flags = mem.get("flags", [])
        relationship = mem.get("relationship", sc.get("relation", ""))

        # Convert 0-1 trust to 0-100 (50 = neutral)
        trust_pct = round(trust * 100)

        # Determine stage (use custom stages if available)
        if custom_stages:
            # Map trust_pct to custom stage index
            stage_count = len(custom_stages)
            normalized = trust_pct / 100  # 0..1
            stage_idx = min(stage_count - 1, max(0, int(normalized * stage_count)))
            stage = custom_stages[stage_idx]
            stages_list = custom_stages
        else:
            # trust_pct >= 50: positive stages (ascending thresholds)
            # trust_pct < 50:  negative stages (descending thresholds)
            if trust_pct >= 50:
                stages_list = _AFFECTION_STAGES
                stage = stages_list[0][1]
                for threshold, label in stages_list:
                    if trust_pct >= threshold:
                        stage = label
            else:
                stages_list = _BAD_STAGES
                stage = stages_list[-1][1]  # default to worst
                for threshold, label in stages_list:
                    if trust_pct <= threshold:
                        stage = label  # keep going, tightest bound wins

        # Hearts: 5 hearts.  0-10=💔x5, 10-30=💔x4, 30-50=💔x1-3
        # 50=♡x5, 50-70=♥x1-3, 70-90=♥x4, 90-100=♥x5
        if trust_pct >= 50:
            filled = min(5, max(0, round((trust_pct - 50) / 10)))
            hearts = "♥" * filled + "♡" * (5 - filled)
        else:
            filled = min(5, max(0, round((50 - trust_pct) / 10)))
            hearts = "💔" * filled + "♡" * (5 - filled) if filled > 0 else "♡♡♡♡♡"

        # Build custom stats display values
        custom_stat_values = []
        for cs in custom_stats_config:
            # Generate a pseudo-random but stable value based on trust and stat key hash
            base = abs(hash(cs["key"] + name)) % 40 + 30  # 30-70 base
            val = min(cs.get("max", 100), base + trust_pct // 2)
            custom_stat_values.append({
                "key": cs["key"],
                "label": cs["label"],
                "value": val,
                "max": cs.get("max", 100),
            })

        result.append({
            "name": name,
            "role": sc.get("role", ""),
            "level": sc.get("level", "L0"),
            "trust_pct": trust_pct,
            "stage": stage,
            "hearts": hearts,
            "flags": flags,
            "relationship": relationship,
            "custom_stats": custom_stat_values,
        })

    # Include memory-only characters (auto-registered NPCs not in session state)
    names_seen = {r["name"] for r in result}
    for name, mem in mem_chars.items():
        if name in names_seen:
            continue
        trust = mem.get("trust", 0.5)
        trust_pct = round(trust * 100)
        if custom_stages:
            normalized = trust_pct / 100
            stage_idx = min(len(custom_stages) - 1, max(0, int(normalized * len(custom_stages))))
            stage = custom_stages[stage_idx]
        else:
            if trust_pct >= 50:
                stages_list = _AFFECTION_STAGES
                stage = stages_list[0][1]
                for threshold, label in stages_list:
                    if trust_pct >= threshold:
                        stage = label
            else:
                stages_list = _BAD_STAGES
                stage = stages_list[-1][1]  # default to worst
                for threshold, label in stages_list:
                    if trust_pct <= threshold:
                        stage = label  # keep going, tightest bound wins
        if trust_pct >= 50:
            filled = min(5, max(0, round((trust_pct - 50) / 10)))
            hearts = "♥" * filled + "♡" * (5 - filled)
        else:
            filled = min(5, max(0, round((50 - trust_pct) / 10)))
            hearts = "💔" * filled + "♡" * (5 - filled) if filled > 0 else "♡♡♡♡♡"
        result.append({
            "name": name,
            "role": mem.get("role", ""),
            "level": "L0",
            "trust_pct": trust_pct,
            "stage": stage,
            "hearts": hearts,
            "flags": mem.get("flags", []),
            "relationship": mem.get("relationship", ""),
            "custom_stats": [],
        })

    return result


# ═══════════════════════════════════════════════════════════════════
#  Character Tier Lifecycle Management
# ═══════════════════════════════════════════════════════════════════
#
#  Four tiers with hard capacity limits:
#    主角 (max 1)  → 核心 (max 6, PERMANENT)  → 重要 (max 15)  → 背景 (unlimited)
#
#  Lifecycle:
#    NEW → tier assigned (respecting caps)
#    核心 → NEVER auto-degrades; only removed via death/permanent exit/break-up/forced departure
#    重要 → inactive too long → auto-degrade to 背景
#    核心 slot opens → promote from 重要 (priority)
#    Goal complete → retire
# ═══════════════════════════════════════════════════════════════════

def get_tier_counts(memory: dict) -> dict[str, int]:
    """Return {tier: count} for all active (non-retired) characters."""
    counts: dict[str, int] = {"主角": 0, "核心": 0, "重要": 0, "背景": 0, "退休": 0}
    chars = memory.get("characters", {})
    for _name, data in chars.items():
        tier = data.get("tier", "")
        if tier in counts:
            counts[tier] += 1
    return counts


def assign_character_tier(memory: dict, name: str,
                          world_pack: dict | None = None,
                          is_main: bool = False) -> str:
    """
    Assign the highest available tier to a character, respecting capacity limits.

    Priority:
      1. If is_main=True and 主角 slot is free → 主角
      2. If character exists in world_pack → 核心 (if < 6) else 重要
      3. New NPC → 重要 (if < 15) else 背景

    Returns the assigned tier string.
    """
    chars = memory.setdefault("characters", {})
    entry = chars.setdefault(name, {"trust": 0.5, "flags": [], "relationship": ""})
    counts = get_tier_counts(memory)

    # Already has a valid tier? Keep it
    existing = entry.get("tier", "")
    if existing and existing in config.TIER_ORDER + ["退休"]:
        return existing

    # Check if this character is in world_pack
    in_world_pack = False
    if world_pack:
        world_chars = world_pack.get("world", {}).get("characters", [])
        for wc in world_chars:
            if wc.get("name") == name:
                in_world_pack = True
                if wc.get("is_main"):
                    is_main = True
                break

    # ── Assign tier ──────────────────────────────────────────
    if is_main:
        if counts.get("主角", 0) < config.CHARACTER_TIER_LIMITS["主角"]:
            entry["tier"] = "主角"
            logger.info("Tier: %s → 主角 (main character)", name)
            return "主角"
        else:
            logger.warning("Tier: 主角 slot full, assigning %s as 核心", name)

    if in_world_pack:
        if counts.get("核心", 0) < config.CHARACTER_TIER_LIMITS["核心"]:
            entry["tier"] = "核心"
            logger.info("Tier: %s → 核心 (from world_pack)", name)
            return "核心"
        elif counts.get("重要", 0) < config.CHARACTER_TIER_LIMITS["重要"]:
            entry["tier"] = "重要"
            logger.info("Tier: %s → 重要 (核心 full, from world_pack)", name)
            return "重要"

    # NPC / overflow → 重要 if space, else 背景
    if counts.get("重要", 0) < config.CHARACTER_TIER_LIMITS["重要"]:
        entry["tier"] = "重要"
        logger.info("Tier: %s → 重要 (new NPC)", name)
        return "重要"
    else:
        entry["tier"] = "背景"
        logger.info("Tier: %s → 背景 (重要 full, new NPC)", name)
        return "背景"


def degrade_inactive_characters(memory: dict, current_turn: int) -> list[str]:
    """
    Degrade characters that haven't appeared for TIER_DEGRADATION_TURNS.
    Degradation chain: 重要 → 背景.
    主角 and 核心 are never auto-degraded. 背景 is the floor.
    核心 only loses status via remove_core_status() (death/permanent exit/etc).

    Returns list of degradation messages for logging.
    """
    chars = memory.get("characters", {})
    messages: list[str] = []
    tier_order = config.TIER_ORDER  # ["主角", "核心", "重要", "背景"]

    for name, data in chars.items():
        tier = data.get("tier", "")
        if tier in ("主角", "核心", "退休", "背景"):
            continue  # never degrade these — 核心 is permanent

        last_appearance = data.get("last_appearance_turn", 0)
        if last_appearance == 0:
            continue  # no appearance data yet

        turns_inactive = current_turn - last_appearance
        if turns_inactive >= config.TIER_DEGRADATION_TURNS:
            try:
                idx = tier_order.index(tier)
            except ValueError:
                continue
            if idx + 1 < len(tier_order):
                new_tier = tier_order[idx + 1]
                data["tier"] = new_tier
                msg = (f"Tier: {name} 降级 {tier} → {new_tier} "
                       f"(已 {turns_inactive} 轮未出场)")
                messages.append(msg)
                logger.info(msg)

    return messages


# ── Core slot lifecycle ─────────────────────────────────────────
# 核心角色 is PERMANENT — only removed via death / permanent exit /
# player break-up / forced story departure.  Never auto-degrades.

# Valid reasons for losing core status
CORE_REMOVAL_REASONS = ["死亡", "永久退场", "玩家主动决裂", "剧情强制离队"]


def remove_core_status(memory: dict, name: str, reason: str) -> bool:
    """
    Strip a character's 核心 status for one of the four allowed reasons.
    The character is moved to 退休 (since these are permanent exits).

    Allowed reasons: 死亡, 永久退场, 玩家主动决裂, 剧情强制离队

    Returns True on success, False if character not found or not 核心.
    """
    chars = memory.get("characters", {})
    if name not in chars:
        logger.warning("Core: cannot remove core status from unknown '%s'", name)
        return False

    entry = chars[name]
    if entry.get("tier") != "核心":
        logger.warning("Core: '%s' is not a 核心 character (tier=%s)", name, entry.get("tier"))
        return False

    if reason not in CORE_REMOVAL_REASONS:
        logger.warning(
            "Core: reason '%s' not in allowed list %s — still applying",
            reason, CORE_REMOVAL_REASONS,
        )

    entry["tier"] = "退休"
    entry["retired"] = True
    entry["retirement_reason"] = f"核心移除: {reason}"
    entry["core_removal_reason"] = reason
    logger.info("Core: %s 失去核心身份 → 退休 (原因: %s)", name, reason)
    return True


def promote_to_core(memory: dict, name: str) -> bool:
    """
    Promote a 重要 character to 核心 when a core slot opens up.
    Checks capacity before promoting.

    Returns True on success, False if no slot or character not eligible.
    """
    chars = memory.get("characters", {})
    if name not in chars:
        logger.warning("Core: cannot promote unknown character '%s'", name)
        return False

    entry = chars[name]
    current_tier = entry.get("tier", "")

    if current_tier == "核心":
        logger.info("Core: '%s' is already 核心", name)
        return True

    if current_tier == "主角":
        logger.info("Core: '%s' is already 主角 (above 核心)", name)
        return True

    if current_tier == "退休":
        # Reactivate first, then promote
        entry.pop("retired", None)
        entry.pop("retirement_reason", None)
        logger.info("Core: '%s' reactivated from retirement for promotion", name)

    # Check capacity
    counts = get_tier_counts(memory)
    if counts.get("核心", 0) >= config.CHARACTER_TIER_LIMITS["核心"]:
        logger.warning("Core: 核心 slots full (%d/%d), cannot promote '%s'",
                       counts["核心"], config.CHARACTER_TIER_LIMITS["核心"], name)
        return False

    old_tier = current_tier
    entry["tier"] = "核心"
    # Clear any retirement flags
    entry.pop("retired", None)
    entry.pop("retirement_reason", None)
    logger.info("Core: %s 晋升 %s → 核心", name, old_tier or "未分类")
    return True


def retire_character(memory: dict, name: str, reason: str = "") -> bool:
    """
    Mark a character as retired (剧情目标完成).
    Retired characters are excluded from active tier counts and AI priority.

    Returns True if retirement was applied, False if character not found.
    """
    chars = memory.get("characters", {})
    if name not in chars:
        logger.warning("Tier: cannot retire unknown character '%s'", name)
        return False

    entry = chars[name]
    old_tier = entry.get("tier", "未知")
    entry["tier"] = "退休"
    entry["retired"] = True
    entry["retirement_reason"] = reason
    logger.info("Tier: %s 退休 (%s → 退休), reason: %s", name, old_tier, reason or "无")
    return True


def reactivate_character(memory: dict, name: str) -> str | None:
    """
    Bring a retired or background character back into active rotation.
    Assigns the best available tier within capacity limits.
    Returns the new tier, or None if character not found.
    """
    chars = memory.get("characters", {})
    if name not in chars:
        return None

    entry = chars[name]
    old_tier = entry.get("tier", "")
    if old_tier == "主角":
        return "主角"  # already highest, nothing to do

    # Clear retirement flags
    if entry.get("retired"):
        entry.pop("retired", None)
        entry.pop("retirement_reason", None)

    # Re-assign tier (temporarily clear old to force re-evaluation)
    entry.pop("tier", None)
    world = io_utils.read_yaml(config.WORLD_PACK_PATH)
    new_tier = assign_character_tier(memory, name, world)
    logger.info("Tier: %s 重新激活 (%s → %s)", name, old_tier, new_tier)
    return new_tier


def get_priority_characters(memory: dict, story_text: str = "",
                            limit: int = 3) -> list[dict]:
    """
    Return characters sorted by AI selection priority:
      1. 核心角色  (highest priority)
      2. 重要角色
      3. 最近未出场 (longer absence = higher priority)
      4. 与当前剧情最相关 (name appears in story_text)

    Returns list of {name, tier, last_appearance_turn, in_story}.
    Excludes retired characters.
    """
    chars = memory.get("characters", {})
    priority_list: list[dict] = []

    for name, data in chars.items():
        tier = data.get("tier", "")
        if tier == "退休":
            continue
        if data.get("retired"):
            continue

        last_app = data.get("last_appearance_turn", 0)
        in_story = name in story_text if story_text else False

        priority_list.append({
            "name": name,
            "tier": tier or "未分类",
            "last_appearance_turn": last_app,
            "in_story": in_story,
        })

    # Sort: 主角 > 核心 > 重要 > 背景; then in_story; then longer absence
    def _sort_key(p: dict) -> tuple[int, int, int]:
        tier_order = {"主角": 0, "核心": 1, "重要": 2, "背景": 3}
        tier_rank = tier_order.get(p["tier"], 5)
        relevance = 0 if p["in_story"] else 1
        # Negate so longer absence = higher priority
        absence = -p["last_appearance_turn"]
        return (tier_rank, relevance, absence)

    priority_list.sort(key=_sort_key)
    return priority_list[:limit]


def build_character_tier_context(memory: dict) -> str:
    """
    Build a tier-awareness context block for the AI prompt.
    Tells the AI about current tier capacities, character roster,
    and creation rules.
    """
    counts = get_tier_counts(memory)
    limits = config.CHARACTER_TIER_LIMITS

    lines: list[str] = []
    lines.append("【角色分级制度】")
    lines.append(f"  主角: {counts['主角']}/{limits['主角']} (上限 {limits['主角']})")
    lines.append(f"  核心角色: {counts['核心']}/{limits['核心']} (上限 {limits['核心']})")
    lines.append(f"  重要角色: {counts['重要']}/{limits['重要']} (上限 {limits['重要']})")
    lines.append(f"  背景角色: {counts['背景']} (无上限)")

    # Capacity warnings
    if counts["核心"] >= limits["核心"]:
        lines.append("  ⚠️ 核心角色已满 — 禁止创建新的核心角色，优先复用已有核心角色。")
    if counts["重要"] >= limits["重要"]:
        lines.append("  ⚠️ 重要角色已满 — 禁止创建新的重要角色，优先激活旧角色或使用背景角色。")

    # Character roster by tier
    chars = memory.get("characters", {})
    for tier in ["主角", "核心", "重要"]:
        tier_chars = [(n, d) for n, d in chars.items()
                      if d.get("tier") == tier and not d.get("retired")]
        if tier_chars:
            names = [n for n, _ in tier_chars]
            lines.append(f"  [{tier}] {', '.join(names)}")

    # Background characters available for reactivation
    background_chars = [(n, d) for n, d in chars.items()
                        if d.get("tier") == "背景" and not d.get("retired")]
    if background_chars:
        bg_sorted = sorted(background_chars,
                           key=lambda x: x[1].get("last_appearance_turn", 0))
        top_bg = [n for n, _ in bg_sorted[:5]]
        lines.append(f"  可激活背景角色: {', '.join(top_bg)}")

    # Retired characters
    retired = [(n, d) for n, d in chars.items() if d.get("retired")]
    if retired:
        names = [n for n, _ in retired]
        lines.append(f"  已退休: {', '.join(names)}")

    return "\n".join(lines)
