from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SpellPotencyModifier:
    rule_id: str
    amount: int

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.rule_id, "Potency modifier rule_id")
        if not isinstance(self.amount, int) or isinstance(self.amount, bool):
            raise TypeError("Potency modifier amount must be an integer")
        if self.amount == 0:
            raise ValueError("Potency modifier amount must not be zero")


@dataclass(frozen=True, slots=True)
class SpellPotencyRequest:
    id: str
    spell_rule_id: str
    target_id: str
    base_potency: int
    modifiers: tuple[SpellPotencyModifier, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "Spell Potency request id")
        _validate_non_empty_string(self.spell_rule_id, "spell_rule_id")
        _validate_non_empty_string(self.target_id, "target_id")
        if not isinstance(self.base_potency, int) or isinstance(
            self.base_potency,
            bool,
        ):
            raise TypeError("base_potency must be an integer")
        if self.base_potency < 1:
            raise ValueError("base_potency must be positive")
        modifiers = tuple(self.modifiers)
        if not all(isinstance(item, SpellPotencyModifier) for item in modifiers):
            raise TypeError(
                "modifiers must contain SpellPotencyModifier values"
            )
        rule_ids = tuple(item.rule_id for item in modifiers)
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("Potency modifier rule IDs must be unique")
        object.__setattr__(self, "modifiers", modifiers)


@dataclass(frozen=True, slots=True)
class SpellPotencyResult:
    request_id: str
    spell_rule_id: str
    target_id: str
    base_potency: int
    potency_delta: int
    effective_potency: int
    has_effect: bool
    applied_rule_ids: tuple[str, ...]


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
