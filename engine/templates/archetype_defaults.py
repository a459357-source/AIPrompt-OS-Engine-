"""
archetype_defaults.py — deterministic archetype → IP visual language mappings
"""

from __future__ import annotations

CHARACTER_ARCHETYPES: dict[str, dict] = {
    "冷面贵族": {
        "visual_keywords": ["noble bearing", "cold expression", "refined attire", "minimal palette"],
        "conflict_vector": "忠诚 vs 野心",
        "personality_axis": ["克制", "威严"],
    },
    "禁欲武将": {
        "visual_keywords": ["disciplined posture", "armor accents", "stern gaze", "muted steel"],
        "conflict_vector": "秩序 vs 情感",
        "personality_axis": ["坚毅", "沉默"],
    },
    "失势公主": {
        "visual_keywords": ["elegant decay", "subtle jewelry", "resilient gaze", "royal remnant"],
        "conflict_vector": "尊严 vs 生存",
        "personality_axis": ["高贵", "隐忍"],
    },
    "游离情报商": {
        "visual_keywords": ["layered cloak", "watchful eyes", "urban shadow", "practical gear"],
        "conflict_vector": "利益 vs 信任",
        "personality_axis": ["机敏", "疏离"],
    },
    "default": {
        "visual_keywords": ["coherent fantasy character design", "story-driven costume"],
        "conflict_vector": "理想 vs 现实",
        "personality_axis": ["鲜明"],
    },
}

LOCATION_TYPES: dict[str, dict] = {
    "权力中心": {
        "function_in_world": "权力中心",
        "atmosphere": "庄严压迫",
        "visual_keywords": ["throne hall", "symmetry", "gold trim", "elevated platform"],
    },
    "军事枢纽": {
        "function_in_world": "军事枢纽",
        "atmosphere": "紧绷戒备",
        "visual_keywords": ["fortress walls", "banners", "strategic layout"],
    },
    "禁区": {
        "function_in_world": "禁区",
        "atmosphere": "神秘危险",
        "visual_keywords": ["sealed gate", "mist", "ancient seal motifs"],
    },
    "default": {
        "function_in_world": "叙事场景",
        "atmosphere": "史诗氛围",
        "visual_keywords": ["fantasy landscape", "unified architecture language"],
    },
}

FACTION_IDEOLOGIES: dict[str, dict] = {
    "military": {
        "public_image": "秩序与武力",
        "hidden_goal": "扩张边境控制权",
        "visual_keywords": ["banner insignia", "territory highlight", "martial palette"],
    },
    "political": {
        "public_image": "合法统治",
        "hidden_goal": "暗中操控继承权",
        "visual_keywords": ["crest emblem", "court colors", "map overlay"],
    },
    "default": {
        "public_image": "公开诉求",
        "hidden_goal": "未公开的真实目标",
        "visual_keywords": ["faction emblem", "controlled region map"],
    },
}

EVENT_TONES: dict[str, dict] = {
    "relationship": {"emotion_tone": "压抑", "visual_keywords": ["intimate lighting", "close framing"]},
    "objective": {"emotion_tone": "冷静", "visual_keywords": ["clue focus", "sharp contrast"]},
    "world": {"emotion_tone": "庄严", "visual_keywords": ["wide shot", "political scale"]},
    "plot": {"emotion_tone": "反转", "visual_keywords": ["dramatic reveal", "dynamic composition"]},
    "default": {"emotion_tone": "克制", "visual_keywords": ["cinematic story frame"]},
}


def infer_character_archetype(profile: dict) -> str:
    role = str(profile.get("role") or "").lower()
    tags = [str(t).lower() for t in (profile.get("personality_tags") or profile.get("tags") or [])]
    if "noble" in tags or "公主" in role or "princess" in role:
        return "失势公主" if "fallen" in tags or "失势" in role else "冷面贵族"
    if "将军" in role or "military" in role or "武将" in role:
        return "禁欲武将"
    if "spy" in tags or "情报" in role:
        return "游离情报商"
    return "default"


def archetype_bundle(archetype: str) -> dict:
    key = str(archetype or "").strip()
    return CHARACTER_ARCHETYPES.get(key, CHARACTER_ARCHETYPES["default"])
