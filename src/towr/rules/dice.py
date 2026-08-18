from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from towr.domain.stats import DicePool


class RandomSource(Protocol):
    def randint(self, start: int, end: int) -> int: ...


@dataclass(frozen=True, slots=True)
class RollResult:
    values: tuple[int, ...]
    successes: int


def roll_pool(profile: DicePool, rng: RandomSource) -> RollResult:
    values = tuple(rng.randint(1, 10) for _ in range(profile.dice))
    return RollResult(
        values=values,
        successes=sum(profile.is_success(value) for value in values),
    )

