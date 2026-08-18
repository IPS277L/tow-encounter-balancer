from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class DicePool:
    """A d10 pool written in the rules as dice/threshold."""

    dice: int
    threshold: int

    def __post_init__(self) -> None:
        if not 1 <= self.dice <= 10:
            raise ValueError("dice must be between 1 and 10")
        if not 1 <= self.threshold <= 10:
            raise ValueError("threshold must be between 1 and 10")

    def is_success(self, value: int) -> bool:
        if not 1 <= value <= 10:
            raise ValueError("a d10 result must be between 1 and 10")
        if self.dice == 1:
            return value == 1
        return value <= self.threshold


@dataclass(frozen=True, slots=True)
class StatBlock:
    """Extensible collection of roll profiles and scalar characteristics."""

    rolls: Mapping[str, DicePool] = field(default_factory=dict)
    values: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if any(value < 0 for value in self.values.values()):
            raise ValueError("scalar stats must not be negative")
        object.__setattr__(self, "rolls", MappingProxyType(dict(self.rolls)))
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))

    def roll(self, name: str) -> DicePool:
        try:
            return self.rolls[name]
        except KeyError as error:
            raise KeyError(f"missing roll stat: {name}") from error

    def value(self, name: str) -> int:
        try:
            return self.values[name]
        except KeyError as error:
            raise KeyError(f"missing scalar stat: {name}") from error
