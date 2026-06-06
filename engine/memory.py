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

logger = logging.getLogger(__name__)


def load_memory() -> dict:
    """Load the memory from disk."""
    return io_utils.read_json(config.MEMORY_PATH)


def save_memory(memory: dict) -> None:
    """Persist memory to disk."""
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
    entry = chars.setdefault(character, {"trust": 0.5, "flags": [], "relationship": ""})

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
            mem_factions[name] = {
                "reputation": 0.5,
                "flags": [],
                "role": faction.get("role", ""),
                "metric_history": {"reputation": []},
            }
            logger.info("Memory: auto-registered faction '%s'", name)


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


def guess_trust_delta_from_story(story: str) -> list[tuple[str, float, str | None]]:
    """
    Heuristic: scan the story text for character names and sentiment
    keywords to guess trust changes and flags.

    Returns a list of (character, delta, optional_flag).
    This is a simple keyword-based heuristic — not AI-powered.
    """
    results: list[tuple[str, float, str | None]] = []

    # Simple keyword → delta mappings
    positive_keywords = {
        "信任": 0.1, "感激": 0.15, "依赖": 0.1, "坦诚": 0.1,
        "微笑": 0.05, "握住": 0.1, "拥抱": 0.15, "并肩": 0.1,
        "拯救": 0.2, "保护": 0.15, "理解": 0.1, "共鸣": 0.15,
    }
    negative_keywords = {
        "怀疑": -0.1, "背叛": -0.3, "隐瞒": -0.1, "欺骗": -0.2,
        "愤怒": -0.1, "冷漠": -0.1, "离开": -0.1, "伤害": -0.2,
    }
    flag_keywords = {
        "遗迹核心": "接触遗迹核心",
        "星痕": "感知星痕能量",
        "守护者": "遭遇守护者",
        "星联": "星联介入",
        "自由航行": "自由航行者介入",
        "牺牲": "重大牺牲事件",
    }

    # Characters we track (from memory)
    # We'll just scan for any keyword matches and return them;
    # the caller decides which character they apply to.

    for kw, delta in positive_keywords.items():
        if kw in story:
            results.append(("__any__", delta, None))

    for kw, delta in negative_keywords.items():
        if kw in story:
            results.append(("__any__", delta, None))

    for kw, flag in flag_keywords.items():
        if kw in story:
            results.append(("__any__", 0.02, flag))

    return results


# ── UI helpers ─────────────────────────────────────────────────────

# 7-stage affection progression
_AFFECTION_STAGES = [
    (0,   "陌生"),
    (15,  "认识"),
    (30,  "熟悉"),
    (45,  "朋友"),
    (60,  "暧昧"),
    (80,  "恋人"),
    (100, "灵魂伴侣"),
]

_BAD_STAGES = [
    (0,   "正常"),
    (-20, "疏远"),
    (-40, "冷漠"),
    (-60, "对立"),
    (-80, "敌视"),
    (-100,"崩坏"),
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

        # Convert 0-1 trust to -100..100 (center at 0.5 = 0)
        trust_pct = round((trust - 0.5) * 200)

        # Determine stage (use custom stages if available)
        if custom_stages:
            # Map trust_pct to custom stage index
            stage_count = len(custom_stages)
            # trust_pct -100..100 → stage index 0..stage_count-1
            normalized = (trust_pct + 100) / 200  # 0..1
            stage_idx = min(stage_count - 1, max(0, int(normalized * stage_count)))
            stage = custom_stages[stage_idx]
            stages_list = custom_stages
        else:
            stage = "陌生"
            stages_list = _AFFECTION_STAGES if trust_pct >= 0 else _BAD_STAGES
            for threshold, label in stages_list:
                if trust_pct >= threshold:
                    stage = label
                else:
                    break

        # Hearts: 5 hearts, filled count based on abs(trust_pct)/20
        filled = min(5, max(0, round(abs(trust_pct) / 20)))
        hearts = "♥" * filled + "♡" * (5 - filled)
        if trust_pct < 0:
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
        trust_pct = round((trust - 0.5) * 200)
        if custom_stages:
            normalized = (trust_pct + 100) / 200
            stage_idx = min(len(custom_stages) - 1, max(0, int(normalized * len(custom_stages))))
            stage = custom_stages[stage_idx]
        else:
            stages_list = _AFFECTION_STAGES if trust_pct >= 0 else _BAD_STAGES
            stage = stages_list[0][1]
            for threshold, label in stages_list:
                if trust_pct >= threshold:
                    stage = label
                else:
                    break
        filled = min(5, max(0, round(abs(trust_pct) / 20)))
        hearts = "♥" * filled + "♡" * (5 - filled)
        if trust_pct < 0:
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
