"""Tests for current-turn option regeneration."""

from engine.regenerate_options import regenerate_current_turn_options


def test_regenerate_options_no_history():
    out = regenerate_current_turn_options()
    assert out.get("ok") is False
    assert "error" in out
