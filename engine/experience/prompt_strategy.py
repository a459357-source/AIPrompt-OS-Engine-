"""
prompt_strategy.py — ADR-001 Mode Layer: prompt decision interface (stub).

Classification: Mode Layer

Phase 1: interface + default stub only. Does NOT call config.adult_*_text().
Phase 2: migrate prompt weighting and mode context here; builder imports this module.
"""

from __future__ import annotations

from dataclasses import dataclass

import config
from engine.experience.experience_strategy import get_experience_mode


@dataclass(frozen=True)
class PromptWeights:
    """ADR §八 style weights (World / Plot / Relationship). Stub defaults."""

    world: float = 0.45
    plot: float = 0.35
    relationship: float = 0.20


_DEFAULT_STORY_WEIGHTS = PromptWeights(world=0.45, plot=0.35, relationship=0.20)
_DEFAULT_ADULT_WEIGHTS = PromptWeights(world=0.20, plot=0.25, relationship=0.55)


class PromptStrategy:
    """Central prompt mode decisions (Phase 1 stub)."""

    def get_prompt_weights(self) -> PromptWeights:
        if get_experience_mode() == config.EXPERIENCE_MODE_ADULT:
            return _DEFAULT_ADULT_WEIGHTS
        return _DEFAULT_STORY_WEIGHTS

    def get_mode_context_block(self) -> str:
        """Mode Context text appended to Base Prompt (Phase 2)."""
        return ""

    def get_template_path_hint(self) -> str | None:
        """Phase 2: optional override; Phase 1 returns None (use config default)."""
        return None


_default_strategy: PromptStrategy | None = None


def get_prompt_strategy() -> PromptStrategy:
    global _default_strategy
    if _default_strategy is None:
        _default_strategy = PromptStrategy()
    return _default_strategy
