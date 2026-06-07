"""
constants.py — Centralised Magic Numbers & Dictionaries
=========================================================
All hardcoded values previously scattered across memory.py,
memory_updater.py, world_driver.py, and config.py live here
so they can be tuned without hunting through source files.
"""

# ── Trust keyword deltas ───────────────────────────────────────────
# Positive keywords → trust delta (0.0–1.0 range)
TRUST_KEYWORDS_POSITIVE: dict[str, float] = {
    # Universal
    "信任": 0.08, "感激": 0.10, "坦诚": 0.08, "理解": 0.08,
    "共鸣": 0.10, "微笑": 0.03, "并肩": 0.08, "保护": 0.10,
    "拯救": 0.15, "牺牲": 0.20,
    # Romance / relationship
    "握住": 0.08, "拥抱": 0.12, "牵手": 0.08, "告白": 0.15,
    "心动": 0.08, "温柔": 0.05,
    # Business / political
    "合作": 0.06, "结盟": 0.10, "支援": 0.08, "投资": 0.05,
    "共赢": 0.08, "守信": 0.10, "赏识": 0.08, "提拔": 0.10,
    # Conflict resolution
    "和解": 0.12, "道歉": 0.08, "原谅": 0.12, "让步": 0.06,
}

TRUST_KEYWORDS_NEGATIVE: dict[str, float] = {
    # Universal
    "怀疑": -0.08, "背叛": -0.25, "隐瞒": -0.08, "欺骗": -0.20,
    "愤怒": -0.08, "冷漠": -0.08, "伤害": -0.15, "威胁": -0.10,
    # Romance / relationship
    "离开": -0.10, "分手": -0.20, "失望": -0.10, "疏远": -0.08,
    "嫉妒": -0.08,
    # Business / political
    "算计": -0.10, "利用": -0.12, "出卖": -0.20, "毁约": -0.15,
    "打压": -0.10, "陷害": -0.20, "窃取": -0.15, "背刺": -0.25,
    # Hostile
    "攻击": -0.12, "敌对": -0.10, "警告": -0.06,
}

# Story-level flag keywords and their labels
FLAG_KEYWORDS: dict[str, str] = {
    "遗迹核心": "接触遗迹核心",
    "星痕": "感知星痕能量",
    "守护者": "遭遇守护者",
    "星联": "星联介入",
    "自由航行": "自由航行者介入",
    "牺牲": "重大牺牲事件",
}

# ── Common Chinese non-name words (filtered in name detection) ────
COMMON_WORDS: frozenset[str] = frozenset({
    '的是', '我也', '这不', '一个', '他们', '我们', '自己', '可以',
    '什么', '没有', '已经', '因为', '所以', '但是', '如果', '虽然',
    '这个', '那个', '这里', '那里', '怎么', '这样', '那样',
    '不过', '而且', '或者', '还是', '只是', '就是', '不是',
    '不能', '不会', '不要', '应该', '可能', '一定', '必须',
    '之间', '之中', '之后', '之前', '之上', '之下',
    '的时候', '有时候', '周围', '所有', '一些', '很多',
    '主角', '两人', '他们', '这时', '突然', '然后', '接着',
    '其中', '某种', '任何', '什么', '怎么', '怎样',
    '觉得', '知道', '看到', '听到', '感到', '想到',
})

# ── Artifact transfer keywords ─────────────────────────────────
# Story-text keywords that signal an artifact changed hands.
# Format: keyword → (action_label, direction)
#   direction: "acquire" = 获得, "lose" = 失去, "transfer" = 转移
ARTIFACT_TRANSFER_KEYWORDS: dict[str, tuple[str, str]] = {
    "获得": ("acquire", "acquire"),
    "得到": ("acquire", "acquire"),
    "找到": ("acquire", "acquire"),
    "发现": ("acquire", "acquire"),
    "拿到": ("acquire", "acquire"),
    "入手": ("acquire", "acquire"),
    "夺取": ("acquire", "acquire"),
    "夺回": ("acquire", "acquire"),
    "抢走": ("transfer", "acquire"),
    "遗失": ("lose", "lose"),
    "丢失": ("lose", "lose"),
    "失窃": ("lose", "lose"),
    "被盗": ("lose", "lose"),
    "交出": ("transfer", "lose"),
    "交给": ("transfer", "transfer"),
    "赠予": ("transfer", "transfer"),
    "归还": ("transfer", "acquire"),
    "交易": ("transfer", "transfer"),
    "拍卖": ("transfer", "transfer"),
    "抵押": ("transfer", "transfer"),
    "继承": ("acquire", "acquire"),
    "偷走": ("transfer", "acquire"),
    "窃取": ("transfer", "acquire"),
    "销毁": ("destroy", "lose"),
    "毁掉": ("destroy", "lose"),
    "封印": ("seal", "lose"),
    "解锁": ("unlock", "acquire"),
}

# ── Relationship → initial trust mapping ───────────────────────────
RELATIONSHIP_TRUST: dict[str, float] = {
    # Positive / allied
    "自身": 0.50,
    "盟友": 0.55,
    "挚友": 0.60,
    "恋人": 0.65,
    "灵魂伴侣": 0.70,
    "潜在合作者": 0.40,
    "合作": 0.45,
    "同盟": 0.50,
    "羁绊": 0.55,
    # Neutral
    "试探": 0.35,
    "认识": 0.35,
    "熟悉": 0.40,
    "朋友": 0.45,
    # Negative / hostile
    "疏远": 0.25,
    "商业对手": 0.30,
    "竞争": 0.30,
    "对手": 0.25,
    "冷漠": 0.20,
    "对立": 0.15,
    "敌视": 0.10,
    "崩坏": 0.05,
    "终极敌人": 0.10,
}

RELATION_TO_PLAYER_MAP: dict[str, float] = {
    "ally": 0.70, "friendly": 0.60, "neutral": 0.50,
    "hostile": 0.25, "enemy": 0.10,
}

# ── Faction dynamics ───────────────────────────────────────────────
FACTION_REPUTATION_DELTA = 0.05         # per positive/negative keyword hit
INTER_FACTION_ATTITUDE_DELTA = 0.03     # positive between two factions
INTER_FACTION_ATTITUDE_DELTA_REVERSE = 0.02
INTER_FACTION_ATTITUDE_DELTA_NEG = -0.05
INTER_FACTION_ATTITUDE_DELTA_NEG_REVERSE = -0.04

# Passive drift ranges by current attitude
PASSIVE_DRIFT_ALLIED_MAX = 0.02       # ≥ 0.7 → [0, 0.02]
PASSIVE_DRIFT_HOSTILE_MIN = -0.02     # ≤ 0.3 → [-0.02, 0]
PASSIVE_DRIFT_NEUTRAL_RANGE = 0.01    # else → [-0.01, 0.01]
PASSIVE_DRIFT_THRESHOLD = 0.001       # skip below this magnitude

# ── Faction relation badge colours ─────────────────────────────────
RELATION_BADGE_COLORS: dict[str, str] = {
    "ally": "#2ea043", "friendly": "#3fb950",
    "neutral": "#8b949e", "hostile": "#d29922", "enemy": "#da3633",
}

# ── Logging ────────────────────────────────────────────────────────
LOG_MAX_BYTES = 2 * 1024 * 1024       # RotatingFileHandler maxBytes
LOG_BACKUP_COUNT = 5
ERROR_LOG_MAX_BYTES = 1 * 1024 * 1024
ERROR_LOG_BACKUP_COUNT = 3

# ── Save system ────────────────────────────────────────────────────
MAX_CHAPTER_BYTES_IN_SAVE = 50_000

# ── Trust display ──────────────────────────────────────────────────
DEFAULT_INITIAL_TRUST = 0.30           # unknown NPCs
DEFAULT_NEUTRAL_TRUST = 0.50           # world_pack characters without tags
STORY_DETECTED_TRUST_FACTOR = 0.80     # multiply initial trust for story-detected chars
