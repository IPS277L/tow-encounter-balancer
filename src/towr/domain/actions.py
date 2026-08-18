from __future__ import annotations

from dataclasses import dataclass

from towr.domain.stats import DicePool, StatBlock


@dataclass(frozen=True, slots=True)
class StatRollSource:
    stat: str

    def resolve(self, stats: StatBlock) -> DicePool:
        return stats.roll(self.stat)


@dataclass(frozen=True, slots=True)
class InlineRollSource:
    profile: DicePool

    def resolve(self, stats: StatBlock) -> DicePool:
        del stats
        return self.profile


RollSource = StatRollSource | InlineRollSource


@dataclass(frozen=True, slots=True)
class AttackAction:
    id: str
    roll_source: RollSource
    weapon: int
    target_count: int = 1

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("action id must not be empty")
        if self.weapon < 0:
            raise ValueError("weapon must not be negative")
        if self.target_count < 1:
            raise ValueError("target_count must be positive")

