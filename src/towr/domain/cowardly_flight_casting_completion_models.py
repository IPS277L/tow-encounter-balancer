"""Source-bound completion of Curse movement before ordered Willpower.

PG1.4 Rules / Giving Ground p119; Battle Magic / Curse p162. ADR-0036.
The caller supplies completed movements and keeps the pending result until
successful application; no second Casting action or automatic route choice.
"""
from __future__ import annotations

from dataclasses import dataclass

from towr.domain.cowardly_flight_casting_result_models import (
    CowardlyFlightCastingResult, CowardlyFlightCastingStatus,
    validate_cowardly_flight_casting_movements,
)
from towr.domain.resolution_models import CowardlyFlightMovementCompletion
from towr.domain.spatial_models import SpatialBattleState


@dataclass(frozen=True, slots=True)
class CowardlyFlightCastingCompletionRequest:
    pending: CowardlyFlightCastingResult
    movement_completions: tuple[CowardlyFlightMovementCompletion, ...]
    spatial_state_after_movements: SpatialBattleState

    def __post_init__(self) -> None:
        if not isinstance(self.pending, CowardlyFlightCastingResult):
            raise TypeError("Curse completion requires the full pending Casting result")
        if self.pending.status is not CowardlyFlightCastingStatus.MOVEMENT_REQUIRED:
            raise ValueError("Curse completion requires pending movement")
        if not isinstance(self.movement_completions, (tuple, list)):
            raise TypeError("movement completions must be an ordered tuple or list")
        completions = tuple(self.movement_completions)
        validate_cowardly_flight_casting_movements(
            self.pending, completions, self.spatial_state_after_movements)
        object.__setattr__(self, "movement_completions", completions)


@dataclass(frozen=True, slots=True)
class CowardlyFlightCastingCompletionResult:
    source: CowardlyFlightCastingCompletionRequest
    casting: CowardlyFlightCastingResult

    def __post_init__(self) -> None:
        if not isinstance(self.source, CowardlyFlightCastingCompletionRequest):
            raise TypeError("Curse completion result requires its typed source request")
        if not isinstance(self.casting, CowardlyFlightCastingResult):
            raise TypeError("Curse completion result requires a typed Casting result")
        previous, current = self.source.pending, self.casting
        if current.status is not CowardlyFlightCastingStatus.SPELL_RESOLVED:
            raise ValueError("completed Curse requires resolved Willpower")
        if any(getattr(previous, field) != getattr(current, field) for field in (
            "source", "execution", "post_test", "preflight", "spell", "zone",
        )):
            raise ValueError("Curse completion cannot replace its original Casting phases")
        if (current.willpower.completed_movements != self.source.movement_completions
                or current.spatial_state != self.source.spatial_state_after_movements):
            raise ValueError("Curse completion differs from its source movement chain")
