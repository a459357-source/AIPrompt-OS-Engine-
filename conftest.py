"""Pytest hooks for PromptOS."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _adult_unlock_test_bypass():
    """Let legacy tests enable adult mode without a stored unlock key."""
    os.environ["PROMPTOS_SKIP_ADULT_UNLOCK"] = "1"
    yield
    os.environ.pop("PROMPTOS_SKIP_ADULT_UNLOCK", None)
