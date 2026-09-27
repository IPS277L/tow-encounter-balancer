from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.attack_models import AttackRequest, DamageImpactSpec, DamageProfile, NearbyTargetsStaggerSpec
from towr.domain.condition_models import Condition
from towr.domain.npc_attack_preparation_models import NPC_OUTSIDE_OPTIMUM_RULE_ID
from towr.domain.npc_roster_attack_models import npc_attack_blocking_condition
from towr.domain.npc_round_models import NpcRoundRequest
from towr.domain.prepared_ranged_weapon_attack_models import (
    PreparedRangedWeaponAttackExecutionRequest, PreparedRangedWeaponAttackExecutionResult,
)
from towr.domain.protection_models import ProtectionPreparationResult
from towr.domain.ranged_weapon_attack_models import RangedWeaponAttackExecutionResult
from towr.domain.ranged_weapon_attack_preparation_models import (
    BLUNDERBUSS_NEARBY_STAGGER_RULE_ID, RangedWeaponAttackPreparationResult,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponHands, RangedWeaponId, RangedWeaponRange
from towr.domain.reload_models import ReloadableWeaponState
from towr.domain.resolution_models import KernelAttackRequest, TargetInjuryPolicy
from towr.domain.test_models import Skill


@dataclass(frozen=True, slots=True)
class NpcBlunderbussAttackExecutionRequest:
    id: str
    current: NpcRoundRequest
    weapon_state: ReloadableWeaponState
    attack_profile_id: str
    protection: ProtectionPreparationResult
    preparation: RangedWeaponAttackPreparationResult

    def __post_init__(self) -> None:
        validate_npc_blunderbuss_attack(self)

    @property
    def prepared_request(self) -> PreparedRangedWeaponAttackExecutionRequest:
        return PreparedRangedWeaponAttackExecutionRequest(self.id + ":prepared", self.preparation)


def validate_npc_blunderbuss_attack(request: NpcBlunderbussAttackExecutionRequest) -> None:
    if not isinstance(request.id, str) or not request.id.strip():
        raise ValueError("NPC Blunderbuss execution requires an ID")
    if not isinstance(request.attack_profile_id, str) or not request.attack_profile_id.strip():
        raise ValueError("NPC Blunderbuss requires an explicit attack profile ID")
    if not isinstance(request.current, NpcRoundRequest) or not isinstance(request.weapon_state, ReloadableWeaponState):
        raise TypeError("NPC Blunderbuss requires typed current round and weapon state")
    if (not isinstance(request.preparation, RangedWeaponAttackPreparationResult)
            or not isinstance(request.protection, ProtectionPreparationResult)):
        raise TypeError("NPC Blunderbuss requires full weapon and Protection preparations")
    current, prepared = request.current, request.preparation
    source = prepared.source_request
    execution = source.attack
    if execution.id in current.state.consumed_execution_ids:
        raise ValueError("NPC Blunderbuss Attack was already consumed")
    if current.pending_follow_ups:
        raise ValueError("NPC Blunderbuss cannot execute while follow-ups are pending")
    if execution.state != current.round_state:
        raise ValueError("NPC Blunderbuss uses a stale reserved round/slot")
    turn = current.round_state.active_turn
    if (turn is None or turn.actor_id != execution.actor_id or execution.slot_index != 1
            or len(turn.action_slots) != 1 or turn.action_slots[0].executed):
        raise ValueError("NPC Blunderbuss requires its actor's reserved unexecuted Attack slot")
    if request.weapon_state != source.weapon_state or request.weapon_state.weapon_id is not RangedWeaponId.BLUNDERBUSS:
        raise ValueError("NPC Blunderbuss preparation differs from current weapon/profile")
    if source.aim is not None or prepared.aim_follow_up is not None:
        raise ValueError("NPC Blunderbuss currently excludes Aim composition")
    actor = current.state.roster.participant(execution.actor_id)
    target = current.state.roster.participant(execution.target_id)
    if actor.state.actor_id == target.state.actor_id:
        raise ValueError("NPC Blunderbuss requires distinct actor and target")
    for participant in (actor, target):
        if participant.definition.injury_policy is not TargetInjuryPolicy.MINION or participant.state.injury.defeated:
            raise ValueError("NPC Blunderbuss requires undefeated Minion actor and target")
        if participant.turn_participant not in current.round_state.participants:
            raise ValueError("NPC Blunderbuss actor/target differs from round participants")
    blocked = npc_attack_blocking_condition(actor.state.injury.conditions)
    if blocked is not None:
        raise ValueError(f"NPC actor cannot Attack while {blocked.value}")
    if request.attack_profile_id not in actor.state.available_attack_ids:
        raise ValueError("NPC Blunderbuss attack profile is unavailable")
    profile = next(p for p in actor.definition.attacks if p.id == request.attack_profile_id)
    if (profile.skill is not Skill.SHOOTING or profile.damage != DamageProfile(4)
            or profile.range_min is not RangedWeaponRange.SHORT or profile.range_max is not RangedWeaponRange.SHORT
            or profile.hands is not RangedWeaponHands.TWO_HANDED or profile.ignores_armour
            or profile.secondary_effects != (NearbyTargetsStaggerSpec(BLUNDERBUSS_NEARBY_STAGGER_RULE_ID),)):
        raise ValueError("NPC profile must explicitly declare the supported Blunderbuss damage/range/hands/effect")
    protection = request.protection.source_request
    if (protection.defender_id != execution.target_id or protection.attack_skill is not Skill.SHOOTING
            or protection.defender_is_defenceless != target.state.injury.conditions.has(Condition.DEFENCELESS)
            or protection.defender_wields_weapon != target.state.wields_weapon
            or protection.defender_holds_shield != target.state.holds_shield):
        raise ValueError("NPC Blunderbuss Protection has stale target/Conditions/equipment")
    profiles = {p.skill: p.test_profile for p in target.definition.protection}
    if any(option.skill not in profiles or option.test.profile != profiles[option.skill] for option in protection.options):
        raise ValueError("NPC Blunderbuss Protection Test differs from roster")
    attack = request.protection.attack
    if attack.attacker_test.profile != profile.test_profile:
        raise ValueError("NPC Blunderbuss Shooting Test differs from roster")
    if any(mod.rule_id == NPC_OUTSIDE_OPTIMUM_RULE_ID for mod in attack.attacker_test.dice_modifiers):
        raise ValueError("NPC Blunderbuss range modifiers belong to weapon preparation only")
    expected_attack = AttackRequest(attack.id, attack.attacker_test, attack.defender_test,
        DamageImpactSpec(profile.damage, target.state.current_resilience), False,
        actor.state.injury.conditions.has(Condition.STAGGERED))
    if attack != expected_attack:
        raise ValueError("NPC Blunderbuss baseline Attack has stale Conditions/injury or unsupported effects")
    kernel = execution.kernel_request
    expected_kernel = KernelAttackRequest(kernel.id, target.state.actor_id, attack, TargetInjuryPolicy.MINION,
        target.state.injury, kernel.can_target_leave_zone, kernel.target_has_given_ground_this_round)
    if kernel != expected_kernel:
        raise ValueError("NPC Blunderbuss kernel differs from Protection/current injury or adds unsupported effects")
    # Constructs the existing prepared executor contract now, before RNG.
    _ = request.prepared_request


@dataclass(frozen=True, slots=True)
class NpcBlunderbussAttackExecutionResult:
    source_request: NpcBlunderbussAttackExecutionRequest
    execution: PreparedRangedWeaponAttackExecutionResult

    def __post_init__(self) -> None:
        if (not isinstance(self.source_request, NpcBlunderbussAttackExecutionRequest)
                or not isinstance(self.execution, PreparedRangedWeaponAttackExecutionResult)):
            raise TypeError("NPC Blunderbuss result requires typed source and completed prepared execution")
        if self.execution.source_request != self.source_request.prepared_request:
            raise ValueError("NPC Blunderbuss result belongs to another prepared execution")
        if not isinstance(self.execution.execution, RangedWeaponAttackExecutionResult):
            raise ValueError("NPC Blunderbuss requires the direct ranged execution branch")
        resolved = self.primary_attack.attack.resolution.attack
        expected = self.source_request.preparation.execution.attack.kernel_request.attack
        if (resolved.request_id != expected.id or resolved.impact_spec != expected.impact_spec
                or resolved.attacker_test.trace.request_id != expected.attacker_test.id
                or (resolved.defender_test is None) != (expected.defender_test is None)):
            raise ValueError("NPC Blunderbuss resolved Attack differs from preparation")
        if resolved.defender_test is not None and resolved.defender_test.trace.request_id != expected.defender_test.id:
            raise ValueError("NPC Blunderbuss resolved Protection differs from preparation")

    @property
    def primary_attack(self) -> RangedWeaponAttackExecutionResult:
        executed = self.execution.execution
        assert isinstance(executed, RangedWeaponAttackExecutionResult)
        return executed

    @property
    def continuation(self) -> NpcRoundRequest:
        source, attack = self.source_request, self.primary_attack.attack
        participants = tuple(replace(p, state=replace(p.state, injury=attack.resolution.target_state))
            if p.state.actor_id == attack.target_id else p for p in source.current.state.roster.participants)
        state = replace(source.current.state, roster=replace(source.current.state.roster, participants=participants),
                        consumed_execution_ids=(*source.current.state.consumed_execution_ids, attack.request_id))
        return replace(source.current, state=state, round_state=attack.state, pending_follow_ups=attack.resolution.follow_ups)

    @property
    def weapon_state(self) -> ReloadableWeaponState:
        state = self.primary_attack.weapon_state
        assert isinstance(state, ReloadableWeaponState)
        return state

    @property
    def applied_rule_ids(self) -> tuple[str, ...]:
        actor = self.source_request.current.state.roster.participant(self.primary_attack.attack.actor_id)
        profile = next(p for p in actor.definition.attacks if p.id == self.source_request.attack_profile_id)
        return tuple(dict.fromkeys((profile.source_rule_id, *self.source_request.protection.applied_rule_ids,
                                   *self.execution.applied_rule_ids)))
