"""
experience_strategy.py — ADR-001 Mode Layer: experience mode access.

Classification: Mode Layer
Delegates to config experience_mode compatibility layer (Phase 1).
"""

from __future__ import annotations

import config


def get_experience_mode() -> str:
    """Return current experience mode: ``story`` or ``adult``."""
    return config.get_experience_mode()


def is_story() -> bool:
    return get_experience_mode() == config.EXPERIENCE_MODE_STORY


def is_adult() -> bool:
    return get_experience_mode() == config.EXPERIENCE_MODE_ADULT
