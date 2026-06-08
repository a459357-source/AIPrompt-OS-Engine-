"""V6 architecture freeze automated checks."""

from __future__ import annotations

from engine.visual.freeze_check import run_all_checks
from engine.visual.freeze_guard import (
    V6FreezeViolation,
    assert_no_arch_change,
    is_v6_frozen,
)


def test_v6_freeze_checks_pass():
    ok, errors = run_all_checks()
    assert ok, "freeze violations:\n" + "\n".join(errors)


def test_freeze_guard_blocks_arch_change(monkeypatch):
    import config

    monkeypatch.setattr(config, "V6_ARCHITECTURE_FROZEN", True)
    assert is_v6_frozen()
    try:
        assert_no_arch_change("memory_graph layer")
        assert False, "expected V6FreezeViolation"
    except V6FreezeViolation as exc:
        assert "memory_graph" in str(exc)


def test_freeze_guard_disabled_allows(monkeypatch):
    import config

    monkeypatch.setattr(config, "V6_ARCHITECTURE_FROZEN", False)
    assert_no_arch_change("experimental layer")
