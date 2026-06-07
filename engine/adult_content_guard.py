"""Ensure adult-mode turns include intimate options (and optionally story markers)."""

from __future__ import annotations

import json
import logging
from typing import Any

import config

logger = logging.getLogger(__name__)

_MISSION_MARKERS = (
    "前往", "对接", "搜索", "调查", "部署", "窃听", "准备", "战斗", "任务", "基地",
    "货舱", "驾驶舱", "通讯室", "获取情报", "推进主线", "谨慎",
)


def _partner_names(characters: dict) -> list[str]:
    names: list[str] = []
    for key, ch in (characters or {}).items():
        if not isinstance(ch, dict):
            continue
        name = str(ch.get("name") or key).strip()
        if name and name not in names:
            names.append(name)
    return names[:4]


def _is_mission_option(text: str) -> bool:
    t = str(text or "")
    intimate = config.count_intimate_markers(t)
    mission = sum(1 for m in _MISSION_MARKERS if m in t)
    return mission >= 2 and intimate == 0


def _fallback_adult_options(partners: list[str], need: int, count: int) -> list[str]:
    p = partners[0] if partners else "她"
    p2 = partners[1] if len(partners) > 1 else p
    pool = [
        f"把{p}拉进就近私密空间，解开衣扣深吻，手探入衣内抚摸胸腰→情欲升温|欲望|{p} affection+5 attraction+6",
        f"要求{p}跪下用嘴服务，同时手抚摸其头发与后颈→支配/亲密|控制|{p} dependence+4 attraction+5",
        f"与{p2}在角落交缠，褪下衣物直接进入，在喘息中继续→性行为|激情|{p2} affection+6 attraction+7",
        f"把{p}按在墙边，撩起衣摆抚摸大腿内侧，低声命令她别出声→前戏|紧张|{p} attraction+5 trust+2",
    ]
    out: list[str] = []
    for i in range(count):
        out.append(pool[i % len(pool)])
    return out


def _merge_adult_options(
    options: list[str],
    *,
    partners: list[str],
    need: int,
    count: int,
) -> list[str]:
    merged = [str(o).strip() for o in options if str(o).strip()]
    while len(merged) < count:
        merged.append("")
    fallbacks = _fallback_adult_options(partners, need, count)
    fi = 0
    for i, opt in enumerate(merged):
        if config.count_intimate_markers(opt) >= 1:
            continue
        if _is_mission_option(opt) or not opt:
            merged[i] = fallbacks[fi % len(fallbacks)]
            fi += 1
        if config.intimate_option_count(merged) >= need:
            break
    while config.intimate_option_count(merged) < need and fi < len(fallbacks):
        for i, opt in enumerate(merged):
            if config.count_intimate_markers(opt) < 1:
                merged[i] = fallbacks[fi]
                fi += 1
                break
        else:
            break
    return merged[:count]


def _regenerate_options(
    *,
    story: str,
    scene: str,
    partners: list[str],
    tier: str,
) -> list[str] | None:
    from engine.deepseek_client import call_deepseek, DeepSeekError

    need = config.adult_required_intimate_options()
    count = config.OPTION_COUNT
    partner_line = "、".join(partners) if partners else "在场女性角色"
    req_line = (
        f"至少 {need} 个须为露骨色情向具体行动（动词+身体部位/动作），"
        "禁止全部为任务/调查/战斗/对接类。"
    )
    system = (
        config.adult_system_override_text()
        + "\n"
        + config.content_preference_rules_text()
        + f"\n只输出合法 JSON：{{\"options\": [...]}}，恰好 {count} 个字符串。"
    )
    user = (
        f"场景：{scene or '未知'}\n"
        f"可互动角色：{partner_line}\n"
        f"正文摘要（末尾）：{(story or '')[-1200:]}\n\n"
        f"TASK: 根据上文生成下一轮 {count} 个 options。{req_line}\n"
        "格式：行动→推测发展|态度|关系影响(角色 metric±N)。"
    )
    try:
        result = call_deepseek(system, user, skip_validation=True, stream=False)
    except DeepSeekError as exc:
        logger.warning("成人 options 补生成失败: %s", exc)
        return None
    opts = result.get("options") if isinstance(result, dict) else None
    if not isinstance(opts, list):
        return None
    cleaned = [str(o).strip() for o in opts if str(o).strip()]
    return cleaned[:count] if cleaned else None


def ensure_adult_turn_content(
    response: dict,
    *,
    scene: str = "",
    characters: dict | None = None,
) -> dict:
    """Patch options (and log story gaps) when adult mode requirements are not met."""
    config.reload_app_behavior()
    if not config.ADULT_MODE:
        return response

    tier = config.adult_intensity_tier()
    if tier == "low":
        return response

    need = config.adult_required_intimate_options()
    if need <= 0:
        return response

    out = dict(response)
    options = list(out.get("options") or [])
    story = str(out.get("story") or "")

    if config.intimate_option_count(options) >= need:
        return out

    partners = _partner_names(characters or {})
    logger.warning(
        "成人模式 options 露骨不足：intimate=%d need=%d tier=%s scene=%s",
        config.intimate_option_count(options),
        need,
        tier,
        scene,
    )

    regen = _regenerate_options(story=story, scene=scene, partners=partners, tier=tier)
    if regen and config.intimate_option_count(regen) >= need:
        out["options"] = regen
        logger.info("成人 options 已通过补生成满足要求")
        return out

    merged = _merge_adult_options(
        options,
        partners=partners,
        need=need,
        count=config.OPTION_COUNT,
    )
    out["options"] = merged
    logger.info(
        "成人 options 已本地注入 fallback（intimate=%d）",
        config.intimate_option_count(merged),
    )

    if tier in ("extreme", "high") and config.count_intimate_markers(story) < 2:
        logger.warning("成人模式 story 亲密标记偏少，建议下轮选择色情向 option")

    return out
