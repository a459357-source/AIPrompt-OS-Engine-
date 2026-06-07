"""
theme_strategy.py — ADR-001 Mode Layer: UI theme decision interface (stub).

Classification: Mode Layer

Phase 1: stub mapping only. Frontend still uses AdultThemeContext directly.
Phase 3: wire Game/Dashboard to this module.
"""

from __future__ import annotations

import config
from engine.experience.experience_strategy import get_experience_mode, is_adult


class ThemeStrategy:
    """UI theme id resolution (Phase 1 stub)."""

    def get_ui_theme_id(self) -> str:
        """Return ``normal`` for story mode; ``desire`` stub for adult."""
        if is_adult():
            return config.VISUAL_THEME if config.VISUAL_THEME in config.VISUAL_THEME_OPTIONS else "desire"
        return "normal"

    def get_adult_theme_pack(self) -> str | None:
        """Color pack id when in adult experience; None in story mode."""
        if get_experience_mode() == config.EXPERIENCE_MODE_ADULT:
            return config.ADULT_THEME
        return None


_default_strategy: ThemeStrategy | None = None


def get_theme_strategy() -> ThemeStrategy:
    global _default_strategy
    if _default_strategy is None:
        _default_strategy = ThemeStrategy()
    return _default_strategy
