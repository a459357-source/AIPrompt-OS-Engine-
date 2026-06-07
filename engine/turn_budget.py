"""Per-turn AI generation attempt budget (V2: max 2 generations)."""

from __future__ import annotations

from dataclasses import dataclass, field

import config


@dataclass
class TurnAttemptBudget:
    """Shared quota for normal generation + continuation within one turn."""

    max_generations: int = field(default_factory=lambda: config.TURN_MAX_GENERATIONS)
    generations_used: int = 0

    def can_generate(self) -> bool:
        return self.generations_used < self.max_generations

    def use_generation(self) -> None:
        self.generations_used += 1

    @property
    def remaining(self) -> int:
        return max(0, self.max_generations - self.generations_used)
