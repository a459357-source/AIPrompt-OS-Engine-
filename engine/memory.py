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
        # "名叫X" / "叫做X" / "称为X" — explicit naming
        rf'(?:名叫|叫做|称为)\s*({_NC}{{2,3}})',
        # Bare "叫X" — but NOT "名叫" or "叫做" (already covered above)
        rf'(?<!名)(?<!做)叫\s*({_NC}{{2,3}})',
        # "自称X" — but NOT "自称是…" (which means "claimed that…")
        rf'自称\s*(?!是)({_NC}{{2,3}})',
        # "一位叫X" / "一个叫X" / "名为X" / "姓X"
        rf'(?:一位叫|一个叫|名为|姓)\s*({_NC}{{2,3}})',
    ]

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
            candidates.append(name)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    return unique


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
    import re

    results: list[tuple[str, float]] = []

    # Pattern: Chinese/English name followed by ↑↓+-➕➖ and a number
    # Chinese names: up to 12 chars including middle dot (e.g. 卡洛琳·福斯特)
    # ASCII names: 2-20 word chars
    pattern = re.compile(
        r'([\u4e00-\u9fff·]{1,12}|[A-Za-z_]\w{1,19})\s*'
        r'([↑➕\+↓➖\-])\s*'
        r'(\d+)'
    )

    for opt in options:
        if not isinstance(opt, str):
            continue
        # Focus on the third segment (trust hints) if pipe-delimited
        # Format: "action→consequence|attitude|trust hints"
        segments = opt.split("|")
        target = segments[-1] if segments else opt

        for match in pattern.finditer(target):
            name = match.group(1)
            arrow = match.group(2)
            value = int(match.group(3))

            # Determine direction and magnitude.
            # AI outputs trust hints on a 0-100 feel scale (e.g. ↑3 = +3%).
            # Divide by 100:  ↑1 → +0.01    ↑5 → +0.05    ↑20 → +0.20
            if arrow in ('↑', '➕', '+'):
                delta = value / 100.0
            elif arrow in ('↓', '➖', '-'):
                delta = -value / 100.0
            else:
                continue  # shouldn't happen due to regex

            # Clamp to reasonable bounds
            delta = max(-1.0, min(1.0, delta))
            results.append((name, delta))

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
