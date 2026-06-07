"""Tests for V2 turn attempt budget."""
from engine.turn_budget import TurnAttemptBudget
import config


def test_max_two_generations():
    b = TurnAttemptBudget(max_generations=2)
    assert b.can_generate()
    b.use_generation()
    assert b.can_generate()
    b.use_generation()
    assert not b.can_generate()
    assert b.remaining == 0


def test_default_matches_config():
    b = TurnAttemptBudget()
    assert b.max_generations == config.TURN_MAX_GENERATIONS
