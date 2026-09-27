from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.action_execution_models import AttackActionExecutionRequest, AttackActionExecutionResult
from towr.domain.condition_models import Condition, ConditionState
from towr.domain.npc_attack_preparation_models import NpcProtectedAttackPreparationResult
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.resolution_models import (
    AttackerStaggerRequest, FollowUpRequest, KernelAttackRequest, NearbyTargetsStaggerRequest, TargetInjuryPolicy,
)


@dataclass(frozen=True, slots=True)
class NpcNearbyDefeatKey:
    source: NearbyTargetsStaggerRequest
    target_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.source, NearbyTargetsStaggerRequest):
            raise TypeError("nearby defeat key requires a typed effect source")
        if not isinstance(self.target_id, str) or not self.target_id.strip():
            raise ValueError("nearby defeat key requires a target ID")


@dataclass(frozen=True, slots=True)
class NpcNearbyGiveGroundKey:
    source: NearbyTargetsStaggerRequest
    target_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.source, NearbyTargetsStaggerRequest):
            raise TypeError("nearby Give Ground key requires a typed effect source")
        if not isinstance(self.target_id, str) or not self.target_id.strip():
            raise ValueError("nearby Give Ground key requires a target ID")


@dataclass(frozen=True, slots=True)
class NpcRosterAttackState:
    roster: NpcRoster
    consumed_execution_ids: tuple[str, ...] = ()
    acknowledged_defeat_execution_ids: tuple[str, ...] = ()
    consumed_give_ground_execution_ids: tuple[str, ...] = ()
    consumed_nearby_stagger_sources: tuple[NearbyTargetsStaggerRequest, ...] = ()
    acknowledged_nearby_defeats: tuple[NpcNearbyDefeatKey, ...] = ()
    consumed_nearby_give_ground: tuple[NpcNearbyGiveGroundKey, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.roster, NpcRoster):
            raise TypeError("roster must be an NpcRoster")
        consumed = tuple(self.consumed_execution_ids)
        if any(not isinstance(item, str) or not item.strip() for item in consumed):
            raise ValueError("consumed execution IDs must be non-empty strings")
        if len(set(consumed)) != len(consumed):
            raise ValueError("consumed execution IDs must be unique")
        object.__setattr__(self, "consumed_execution_ids", consumed)
        acknowledged = tuple(self.acknowledged_defeat_execution_ids)
        if any(not isinstance(item, str) or not item.strip() for item in acknowledged):
            raise ValueError("acknowledged defeat execution IDs must be non-empty strings")
        if len(set(acknowledged)) != len(acknowledged):
            raise ValueError("acknowledged defeat execution IDs must be unique")
        if not set(acknowledged) <= set(consumed):
            raise ValueError("acknowledged defeat requires a consumed execution")
        object.__setattr__(self, "acknowledged_defeat_execution_ids", acknowledged)
        movements = tuple(self.consumed_give_ground_execution_ids)
        if any(not isinstance(item, str) or not item.strip() for item in movements):
            raise ValueError("consumed Give Ground execution IDs must be non-empty strings")
        if len(set(movements)) != len(movements):
            raise ValueError("consumed Give Ground execution IDs must be unique")
        if not set(movements) <= set(consumed):
            raise ValueError("consumed Give Ground requires a consumed Attack execution")
        object.__setattr__(self, "consumed_give_ground_execution_ids", movements)
        nearby = tuple(self.consumed_nearby_stagger_sources)
        if not all(isinstance(item, NearbyTargetsStaggerRequest) for item in nearby):
            raise TypeError("consumed nearby Stagger sources must be typed")
        if len(set(nearby)) != len(nearby):
            raise ValueError("consumed nearby Stagger sources must be unique")
        object.__setattr__(self, "consumed_nearby_stagger_sources", nearby)
        defeats = tuple(self.acknowledged_nearby_defeats)
        if not all(isinstance(item, NpcNearbyDefeatKey) for item in defeats):
            raise TypeError("acknowledged nearby defeats require typed keys")
        if len(set(defeats)) != len(defeats):
            raise ValueError("acknowledged nearby defeats must be unique")
        if any(item.source not in nearby for item in defeats):
            raise ValueError("nearby defeat acknowledgement requires a consumed effect source")
        object.__setattr__(self, "acknowledged_nearby_defeats", defeats)
        nearby_movements = tuple(self.consumed_nearby_give_ground)
        if not all(isinstance(item, NpcNearbyGiveGroundKey) for item in nearby_movements):
            raise TypeError("consumed nearby Give Ground requires typed keys")
        if len(set(nearby_movements)) != len(nearby_movements):
            raise ValueError("consumed nearby Give Ground must be unique")
        if any(item.source not in nearby for item in nearby_movements):
            raise ValueError("nearby Give Ground requires a consumed effect source")
        object.__setattr__(self, "consumed_nearby_give_ground", nearby_movements)


@dataclass(frozen=True, slots=True)
class NpcRosterAttackExecutionRequest:
    state: NpcRosterAttackState
    preparation: NpcProtectedAttackPreparationResult
    execution: AttackActionExecutionRequest

    def __post_init__(self) -> None:
        if not isinstance(self.state, NpcRosterAttackState):
            raise TypeError("state must be an NpcRosterAttackState")
        if not isinstance(self.preparation, NpcProtectedAttackPreparationResult):
            raise TypeError("preparation must be an NpcProtectedAttackPreparationResult")
        if not isinstance(self.execution, AttackActionExecutionRequest):
            raise TypeError("execution must be an AttackActionExecutionRequest")
        validate_npc_roster_attack(self)


def npc_attack_blocking_condition(conditions: ConditionState) -> Condition | None:
    """PG 1.4 Conditions pp122–123; only the ordinary Minion Attack boundary."""
    if conditions.has(Condition.DEFENCELESS):
        return Condition.DEFENCELESS
    if conditions.has(Condition.BROKEN):
        return Condition.BROKEN
    return None


def validate_npc_roster_attack(request: NpcRosterAttackExecutionRequest) -> None:
    execution, prepared, roster = request.execution, request.preparation, request.state.roster
    if execution.id in request.state.consumed_execution_ids:
        raise ValueError("NPC roster attack execution was already consumed")
    actor, target = roster.participant(execution.actor_id), roster.participant(execution.target_id)
    if actor.state.actor_id == target.state.actor_id:
        raise ValueError("NPC roster attack requires distinct actor and target")
    for participant in (actor, target):
        if participant.definition.injury_policy is not TargetInjuryPolicy.MINION:
            raise ValueError("NPC roster attack currently supports Minion versus Minion only")
        if participant.state.injury.defeated:
            raise ValueError("NPC roster attack excludes defeated participants")
        if participant.turn_participant not in execution.state.participants:
            raise ValueError("roster actor/side does not match round participants")
    blocked = npc_attack_blocking_condition(actor.state.injury.conditions)
    if blocked is not None:
        raise ValueError(f"NPC actor cannot Attack while {blocked.value}")
    npc = prepared.npc_attack
    source = npc.source_request
    if (npc.snapshot != actor.attack_snapshot(npc.snapshot.id)
            or npc.target_id != target.state.actor_id
            or source.target_resilience != target.state.current_resilience
            or source.attacker_is_staggered != actor.state.injury.conditions.has(Condition.STAGGERED)):
        raise ValueError("NPC preparation has stale roster actor/target/context")
    if npc.attack.secondary_effects:
        raise ValueError("NPC roster attack excludes additional attack effects")
    protection = prepared.protection.source_request
    if (protection.defender_is_defenceless != target.state.injury.conditions.has(Condition.DEFENCELESS)
            or protection.defender_wields_weapon != target.state.wields_weapon
            or protection.defender_holds_shield != target.state.holds_shield):
        raise ValueError("Protection has stale roster conditions/equipment")
    profiles = {profile.skill: profile.test_profile for profile in target.definition.protection}
    if any(option.skill not in profiles or option.test.profile != profiles[option.skill]
           for option in protection.options):
        raise ValueError("Protection Test profile does not match roster definition")
    # All Test modifiers remain explicit caller inputs, not inferred from the roster.
    kernel = execution.kernel_request
    expected = KernelAttackRequest(
        id=kernel.id, target_id=target.state.actor_id, attack=prepared.attack,
        target_policy=TargetInjuryPolicy.MINION, target_state=target.state.injury,
        can_target_leave_zone=kernel.can_target_leave_zone,
        target_has_given_ground_this_round=kernel.target_has_given_ground_this_round,
    )
    if kernel != expected:
        raise ValueError("kernel request differs from prepared attack/current injury or adds unsupported effects")


@dataclass(frozen=True, slots=True)
class NpcRosterAttackExecutionResult:
    source_request: NpcRosterAttackExecutionRequest
    executed_request: AttackActionExecutionRequest
    execution: AttackActionExecutionResult

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcRosterAttackExecutionRequest):
            raise TypeError("source_request must be an NpcRosterAttackExecutionRequest")
        if not isinstance(self.executed_request, AttackActionExecutionRequest):
            raise TypeError("executed_request must be an AttackActionExecutionRequest")
        if not isinstance(self.execution, AttackActionExecutionResult):
            raise TypeError("execution must be an AttackActionExecutionResult")
        source, actual = self.source_request.execution, self.execution
        if self.executed_request != source:
            raise ValueError("executed request does not match preparation/source")
        if (actual.request_id != source.id or actual.actor_id != source.actor_id
                or actual.target_id != source.target_id or actual.slot_index != source.slot_index
                or actual.previous_state != source.state
                or actual.resolution.request_id != source.kernel_request.id):
            raise ValueError("execution does not belong to this roster request")
        attack, expected = actual.resolution.attack, source.kernel_request.attack
        if (attack.request_id != expected.id or attack.impact_spec != expected.impact_spec
                or attack.attacker_test.trace.request_id != expected.attacker_test.id
                or (attack.defender_test is None) != (expected.defender_test is None)):
            raise ValueError("execution attack does not match preparation")
        if (attack.defender_test is not None
                and attack.defender_test.trace.request_id != expected.defender_test.id):
            raise ValueError("execution Protection does not match preparation")
        for item in self.handled_follow_ups:
            if item != AttackerStaggerRequest(expected.id):
                raise ValueError("attacker Staggered follow-up belongs to another attack")

    @property
    def handled_follow_ups(self) -> tuple[AttackerStaggerRequest, ...]:
        return tuple(item for item in self.execution.resolution.follow_ups
                     if isinstance(item, AttackerStaggerRequest))

    @property
    def pending_follow_ups(self) -> tuple[FollowUpRequest, ...]:
        # ProfileStateChange remains visible: defeat disposition is a caller/GM decision.
        return tuple(item for item in self.execution.resolution.follow_ups
                     if not isinstance(item, AttackerStaggerRequest))

    @property
    def state(self) -> NpcRosterAttackState:
        request = self.source_request
        participants = []
        for participant in request.state.roster.participants:
            injury = participant.state.injury
            if participant.state.actor_id == self.execution.target_id:
                injury = self.execution.resolution.target_state
            elif participant.state.actor_id == self.execution.actor_id and self.handled_follow_ups:
                # PG 1.4 Rules / Failed Attacks p119: add Staggered once, no escalation.
                injury = replace(injury, conditions=injury.conditions.with_condition(Condition.STAGGERED))
            participants.append(participant if injury == participant.state.injury else
                                replace(participant, state=replace(participant.state, injury=injury)))
        return replace(
            request.state, roster=NpcRoster(tuple(participants)),
            consumed_execution_ids=(*request.state.consumed_execution_ids, self.execution.request_id),
        )

    @property
    def applied_rule_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((
            *self.source_request.preparation.applied_rule_ids,
            *self.execution.applied_rule_ids,
            *self.execution.resolution.attack.applied_rule_ids,
            *(item.rule_id for item in self.handled_follow_ups),
        )))
