"""
background_tasks.py — Non-blocking deferred work (dashboard HTML, etc.)
"""

from __future__ import annotations

import logging
import threading
import traceback

logger = logging.getLogger(__name__)

_DASHBOARD_LOCK = threading.Lock()
_DASHBOARD_TIMER: threading.Timer | None = None
_DASHBOARD_DIRTY = False

# Debounce: coalesce rapid turns into one write
DASHBOARD_DEBOUNCE_SEC = 15.0


def schedule_dashboard_write(*, delay_sec: float = DASHBOARD_DEBOUNCE_SEC) -> None:
    """Queue dashboard HTML regeneration off the turn hot path."""
    global _DASHBOARD_TIMER, _DASHBOARD_DIRTY

    with _DASHBOARD_LOCK:
        _DASHBOARD_DIRTY = True
        if _DASHBOARD_TIMER is not None:
            _DASHBOARD_TIMER.cancel()
        _DASHBOARD_TIMER = threading.Timer(delay_sec, _flush_dashboard)
        _DASHBOARD_TIMER.daemon = True
        _DASHBOARD_TIMER.start()


def flush_dashboard_now() -> bool:
    """Write dashboard immediately (e.g. tests or manual refresh)."""
    return _flush_dashboard()


def _flush_dashboard() -> bool:
    global _DASHBOARD_DIRTY, _DASHBOARD_TIMER

    with _DASHBOARD_LOCK:
        if not _DASHBOARD_DIRTY:
            return True
        _DASHBOARD_DIRTY = False
        _DASHBOARD_TIMER = None

    try:
        from engine.dashboard import write_standalone

        path = write_standalone()
        logger.info("Dashboard written (background) → %s", path)
        return True
    except Exception:
        logger.error("Dashboard background write failed:\n%s", traceback.format_exc())
        with _DASHBOARD_LOCK:
            _DASHBOARD_DIRTY = True
        return False
