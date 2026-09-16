from __future__ import annotations

from dataclasses import dataclass

from towr.domain.hidden_attack_models import (
    HIDDEN_ATTACK_OPPORTUNITY_RULE_ID,
    MoveQuietlyHiddenAttackExecutionRequest,
)
from towr.domain.hidden_ranged_weapon_attack_models import (
    MoveQuietlyHiddenRangedAttackExecutionRequest,
    MoveQuietlyHiddenRangedAttackExecutionResult,
)
from towr.domain.prepared_ranged_weapon_attack_models import (
    PreparedRangedWeaponAttackExecutionRequest,
    PreparedRangedWeaponAttackExecutionResult,
)
from towr.domain.ranged_weapon_attack_models import (
    RangedWeaponAttackExecutionResult,
)


@dataclass(frozen=True, slots=True)
class PreparedHiddenRangedAttackExecutionRequest:
    id: str
    hidden_attack: MoveQuietlyHiddenAttackExecutionRequest
    prepared_attack: PreparedRangedWeaponAttackExecutionRequest
    rule_id: str = HIDDEN_ATTACK_OPPORTUNITY_RULE_ID

    def __post_init__(self) -> None:
        if not isinstance(
            self.prepared_attack, PreparedRangedWeaponAttackExecutionRequest
        ):
            raise TypeError("prepared_attack must be a prepared ranged Attack request")
        # Reuse the existing exact-Attack/hidden provenance preflight, not its executor.
        _hidden_request_for(self)
        identifiers = (
            self.id,
            self.hidden_attack.id,
            self.prepared_attack.id,
            self.prepared_attack.preparation.request_id,
            self.prepared_attack.preparation.execution.id,
            self.hidden_attack.attack.id,
        )
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("prepared hidden ranged request IDs must be distinct")


@dataclass(frozen=True, slots=True)
class PreparedHiddenRangedAttackExecutionResult:
    request_id: str
    rule_id: str
    source_request: PreparedHiddenRangedAttackExecutionRequest
    prepared_attack: PreparedRangedWeaponAttackExecutionResult
    revealed_hiding_position_id: str
    previous_consumed_opportunity_ids: tuple[str, ...]
    consumed_opportunity_ids: tuple[str, ...]
    applied_rule_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.source_request, PreparedHiddenRangedAttackExecutionRequest
        ):
            raise TypeError("source_request must be a prepared hidden ranged request")
        if not isinstance(
            self.prepared_attack, PreparedRangedWeaponAttackExecutionResult
        ):
            raise TypeError("prepared_attack must be a prepared ranged Attack result")
        if (
            self.prepared_attack.source_request
            != self.source_request.prepared_attack
        ):
            raise ValueError("hidden result belongs to another prepared Attack")
        # This validation-only view never executes an Attack or stores a second result.
        hidden = MoveQuietlyHiddenRangedAttackExecutionResult(
            request_id=self.request_id,
            rule_id=self.rule_id,
            source_request=_hidden_request_for(self.source_request),
            ranged_attack=self.prepared_attack.ranged_attack,
            revealed_hiding_position_id=self.revealed_hiding_position_id,
            previous_consumed_opportunity_ids=self.previous_consumed_opportunity_ids,
            consumed_opportunity_ids=self.consumed_opportunity_ids,
            applied_rule_ids=self.applied_rule_ids,
        )
        if hidden.applied_rule_ids != _applied_rule_ids(
            self.source_request, self.prepared_attack
        ):
            raise ValueError("prepared hidden ranged trace is inconsistent")
        object.__setattr__(
            self, "previous_consumed_opportunity_ids",
            hidden.previous_consumed_opportunity_ids,
        )
        object.__setattr__(
            self, "consumed_opportunity_ids", hidden.consumed_opportunity_ids
        )
        object.__setattr__(self, "applied_rule_ids", hidden.applied_rule_ids)

    @property
    def ranged_attack(self) -> RangedWeaponAttackExecutionResult:
        return self.prepared_attack.ranged_attack

    @property
    def previous_consumed_aim_follow_up_ids(self) -> tuple[str, ...]:
        return self.prepared_attack.previous_consumed_aim_follow_up_ids

    @property
    def consumed_aim_follow_up_ids(self) -> tuple[str, ...]:
        return self.prepared_attack.consumed_aim_follow_up_ids


def _hidden_request_for(
    request: PreparedHiddenRangedAttackExecutionRequest,
) -> MoveQuietlyHiddenRangedAttackExecutionRequest:
    return MoveQuietlyHiddenRangedAttackExecutionRequest(
        id=request.id,
        hidden_attack=request.hidden_attack,
        ranged_attack=request.prepared_attack.preparation.execution,
        rule_id=request.rule_id,
    )


def _applied_rule_ids(
    request: PreparedHiddenRangedAttackExecutionRequest,
    prepared_attack: PreparedRangedWeaponAttackExecutionResult,
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys((
            request.rule_id,
            request.hidden_attack.move_quietly.rule_id,
            *request.hidden_attack.move_quietly.applied_rule_ids,
            *prepared_attack.applied_rule_ids,
        ))
    )
