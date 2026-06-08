"""
freeze_guard.py — V6 architecture freeze runtime guard
"""

from __future__ import annotations

import config

ALLOWED_FREEZE_CATEGORIES = frozenset({
    "content",
    "prefetch",
    "ui",
    "fix",
    "docs",
    "test",
    "config",
})


class V6FreezeViolation(RuntimeError):
    """Raised when a change violates V6 architecture freeze."""


def is_v6_frozen() -> bool:
    return bool(getattr(config, "V6_ARCHITECTURE_FROZEN", True))


def assert_no_arch_change(feature_name: str) -> None:
    """Block new architecture layers at runtime (dev/test hook)."""
    if is_v6_frozen():
        raise V6FreezeViolation(
            f"[V6 FREEZE] Forbidden architecture change: {feature_name}"
        )


def assert_freeze_category(category: str) -> None:
    """Optional guard for feature flags — category must be allow-listed."""
    if not is_v6_frozen():
        return
    cat = str(category or "").strip().lower()
    if cat and cat not in ALLOWED_FREEZE_CATEGORIES:
        raise V6FreezeViolation(
            f"[V6 FREEZE] Change category '{category}' not allowed during freeze. "
            f"Allowed: {sorted(ALLOWED_FREEZE_CATEGORIES)}"
        )
