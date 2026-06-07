"""
engine.experience — ADR-001 Mode Layer strategy skeleton (Phase 1).

Interfaces only; existing code paths do not import these modules yet.
Phase 2 will wire PromptStrategy into builder.py.
"""

from engine.experience.experience_strategy import (
    get_experience_mode,
    is_adult,
    is_story,
)
from engine.experience.prompt_strategy import PromptStrategy, ModeContext, get_prompt_strategy
from engine.experience.theme_strategy import ThemeStrategy, get_theme_strategy

__all__ = [
    "get_experience_mode",
    "is_adult",
    "is_story",
    "PromptStrategy",
    "ModeContext",
    "get_prompt_strategy",
    "ThemeStrategy",
    "get_theme_strategy",
]
