from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TrappingSnapshot:
    """Minimal carried-item identity; value is an external GM assessment."""

    id: str
    definition_id: str
    owner_actor_id: str
    is_valuable: bool

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.id, "trapping id")
        _validate_non_empty_string(self.definition_id, "trapping definition_id")
        _validate_non_empty_string(self.owner_actor_id, "trapping owner_actor_id")
        if not isinstance(self.is_valuable, bool):
            raise TypeError("is_valuable must be a bool")


@dataclass(frozen=True, slots=True)
class CarriedInventoryState:
    owner_actor_id: str
    trappings: tuple[TrappingSnapshot, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.owner_actor_id,
            "inventory owner_actor_id",
        )
        trappings = tuple(self.trappings)
        if not all(isinstance(item, TrappingSnapshot) for item in trappings):
            raise TypeError("trappings must contain TrappingSnapshot values")
        if any(item.owner_actor_id != self.owner_actor_id for item in trappings):
            raise ValueError("all carried trappings must belong to the inventory owner")
        ids = tuple(item.id for item in trappings)
        if len(set(ids)) != len(ids):
            raise ValueError("carried trapping IDs must be unique")
        object.__setattr__(self, "trappings", trappings)

    def trapping(self, trapping_id: str) -> TrappingSnapshot | None:
        _validate_non_empty_string(trapping_id, "trapping id")
        return next(
            (item for item in self.trappings if item.id == trapping_id),
            None,
        )


def _validate_non_empty_string(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
