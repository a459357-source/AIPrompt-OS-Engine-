"""
prompt_strategy.py — ADR-001 Mode Layer: prompt decision interface.

Classification: Mode Layer

Centralizes experience-mode prompt decisions. Builder imports this module only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import config
from engine.experience.experience_strategy import get_experience_mode, is_adult, is_story


@dataclass(frozen=True)
class PromptWeights:
    """ADR §八 style weights (World / Plot / Relationship)."""

    world: float = 0.45
    plot: float = 0.35
    relationship: float = 0.20


@dataclass(frozen=True)
class ModeContext:
    """Mode Layer blocks interpolated into the unified Base Prompt template."""

    system_block: str
    user_block: str
    behavior_rules: str
    task_hint: str
    options_hint: str
    main_goal_suffix: str
    narrative_style_line: str


_DEFAULT_STORY_WEIGHTS = PromptWeights(world=0.45, plot=0.35, relationship=0.20)
_DEFAULT_ADULT_WEIGHTS = PromptWeights(world=0.20, plot=0.25, relationship=0.55)

_EXTREME_PRIORITY_BLOCK = (
    "【优先级】禁止男男（最高铁律；允许男↔女含男性角色、女↔女）> 其他成人铁律 > 玩家本轮选择 > "
    "long_term_goal > 状态机（COOLDOWN 可降性强度但不许整轮无性）> 势力/关键物品 > 角色分级"
)

_STORY_NARRATIVE_STYLE = "注重心理描写与环境氛围。"
_ADULT_NARRATIVE_STYLE = "注重心理描写、环境氛围与角色情感互动。"
_EXTREME_NARRATIVE_STYLE = "正文以感官与身体互动为主，辅以必要的心理与环境点缀。"


def _pct(weight: float) -> int:
    return int(round(max(0.0, min(1.0, weight)) * 100))


def _build_weight_block(weights: PromptWeights) -> str:
    w, p, r = _pct(weights.world), _pct(weights.plot), _pct(weights.relationship)
    if is_story():
        label = "Story Mode（World Perspective）"
        guidance = "优先主线推进、世界探索与世界状态变化；关系推进服务于剧情。"
    else:
        label = "Adult Mode（Character Perspective）"
        guidance = "优先角色互动、情感发展与关系变化；世界事件作为关系发展的背景。"
    return (
        f"【体验模式 — 叙事优先级】\n"
        f"当前模式：{label}\n"
        f"World: {w}% | Plot: {p}% | Relationship: {r}%\n"
        f"生成要求：{guidance}"
    )


class PromptStrategy:
    """Central prompt mode decisions for Base Prompt + Mode Context architecture."""

    def get_prompt_weights(self) -> PromptWeights:
        if is_adult():
            return _DEFAULT_ADULT_WEIGHTS
        return _DEFAULT_STORY_WEIGHTS

    def get_intensity_tier(self) -> str:
        if is_story():
            return "low"
        return config.adult_intensity_tier()

    def get_choice_execution_hint(self, choice_text: str) -> str:
        return config.adult_choice_execution_hint(choice_text)

    def requires_content_guard(self) -> bool:
        if is_story():
            return False
        tier = self.get_intensity_tier()
        if tier not in ("medium", "high", "extreme"):
            return False
        return config.adult_required_intimate_options() > 0

    def get_guard_min_intimate_options(self) -> int:
        return config.adult_required_intimate_options()

    def build_mode_context(
        self,
        *,
        world_pack: dict,
        session_state: dict,
        engine_config: dict | None = None,
    ) -> ModeContext:
        del engine_config  # reserved for Phase 3 prompt tuning
        weights = self.get_prompt_weight_block()
        tier = self.get_intensity_tier()
        vocab_domain = config.vocabulary_domain_text(world_pack)
        norm_block = config.normalized_intimacy_block(world_pack)

        system_parts: list[str] = [weights]
        narrative_style = _STORY_NARRATIVE_STYLE

        if is_adult():
            override = config.adult_system_override_text()
            if override:
                system_parts.append(override)
            if tier == "extreme" and not config.use_legacy_extreme_template_file():
                system_parts.append(_EXTREME_PRIORITY_BLOCK)
                content_rules = config.adult_extreme_content_rules_text()
                if content_rules:
                    system_parts.append(content_rules)
                narrative_style = _EXTREME_NARRATIVE_STYLE
            elif is_adult():
                narrative_style = _ADULT_NARRATIVE_STYLE

        behavior_rules = self._resolve_behavior_rules(
            vocab_domain=vocab_domain,
            norm_block=norm_block,
            tier=tier,
        )

        options_hint = config.adult_options_hint_text() if is_adult() else "，应包含结识新角色的选项"
        task_hint = self._resolve_task_hint(tier)
        user_block = config.intimacy_escalation_hint(session_state) if is_adult() else ""
        if user_block:
            user_block = user_block + "\n"

        return ModeContext(
            system_block="\n\n".join(p for p in system_parts if p),
            user_block=user_block,
            behavior_rules=behavior_rules,
            task_hint=task_hint,
            options_hint=options_hint,
            main_goal_suffix=config.adult_main_goal_suffix() if is_adult() else "",
            narrative_style_line=narrative_style,
        )

    def get_prompt_weight_block(self) -> str:
        return _build_weight_block(self.get_prompt_weights())

    def _resolve_behavior_rules(
        self,
        *,
        vocab_domain: str,
        norm_block: str,
        tier: str,
    ) -> str:
        if is_adult() and tier == "extreme":
            extreme_rules = config.adult_extreme_behavior_rules_text(
                vocabulary_domain=vocab_domain,
                normalized_block=norm_block,
            )
            if extreme_rules:
                pref = config.content_preference_rules_text()
                return extreme_rules + ("\n" + pref if pref else "")
        return config.ai_behavior_rules_text()

    def _resolve_task_hint(self, tier: str) -> str:
        if is_story():
            return ""
        if tier == "extreme" and not config.use_legacy_extreme_template_file():
            parts = [
                config.adult_extreme_task_hint_text(),
                "每轮必须有性内容推进——性描写为主体（70%+），剧情交代为辅助（2-3句）。",
            ]
            extra = config.adult_task_hint_text()
            if extra and extra not in parts[0]:
                parts.append(extra.strip())
            return " ".join(p.strip() for p in parts if p.strip())
        return config.adult_task_hint_text()


_default_strategy: PromptStrategy | None = None


def get_prompt_strategy() -> PromptStrategy:
    global _default_strategy
    if _default_strategy is None:
        _default_strategy = PromptStrategy()
    return _default_strategy
