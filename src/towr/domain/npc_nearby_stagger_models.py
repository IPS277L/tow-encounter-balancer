from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.attack_models import AttackOutcome, NearbyTargetsStaggerSpec
from towr.domain.injury_models import ProfileInjuryState, ProfileStateChangeRequest
from towr.domain.npc_roster_attack_models import NpcRosterAttackState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.ranged_weapon_attack_preparation_models import BLUNDERBUSS_NEARBY_STAGGER_RULE_ID
from towr.domain.ranged_weapon_attack_models import RangedWeaponAttackExecutionResult
from towr.domain.ranged_weapon_profiles import RangedWeaponId
from towr.domain.resolution_models import (
    GiveGroundRequest, NearbyTargetStaggerResult, NearbyTargetsStaggerResolutionRequest,
    NearbyTargetsStaggerResolutionResult, TargetInjuryPolicy,
)


@dataclass(frozen=True, slots=True)
class NpcNearbyStaggerExecutionRequest:
    state: NpcRosterAttackState
    resolution: NearbyTargetsStaggerResolutionRequest
    primary_attack: RangedWeaponAttackExecutionResult | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, NpcRosterAttackState) or not isinstance(self.resolution, NearbyTargetsStaggerResolutionRequest):
            raise TypeError("NPC nearby Stagger requires typed roster/history and resolution request")
        source = self.resolution
        if source.source in self.state.consumed_nearby_stagger_sources:
            raise ValueError("NPC nearby Stagger source was already consumed")
        if source.source.rule_id != BLUNDERBUSS_NEARBY_STAGGER_RULE_ID:
            raise ValueError("NPC nearby Stagger currently supports the Blunderbuss effect only")
        self.state.roster.participant(source.primary_target_id)
        if self.primary_attack is not None:
            _validate_primary_attack(self)
        for target in source.targets:
            participant = self.state.roster.participant(target.target_id)
            impact = target.impact
            if participant.definition.injury_policy is not TargetInjuryPolicy.MINION or impact.target_policy is not TargetInjuryPolicy.MINION:
                raise ValueError("NPC nearby Stagger currently supports Minion secondary targets only")
            if participant.state.injury.defeated:
                raise ValueError("NPC nearby Stagger excludes already defeated secondary targets")
            if impact.target_state != participant.state.injury:
                raise ValueError("NPC nearby Stagger has a stale secondary target state")
            if (impact.wound_dice_modifiers or impact.wound_negation_options or impact.additional_profile_wounds
                    or impact.after_give_ground_effects or impact.give_ground_or_wound_effects or impact.target_effect_immunities):
                raise ValueError("NPC nearby Stagger does not support additional injury/effect options")


def _validate_primary_attack(request: NpcNearbyStaggerExecutionRequest) -> None:
    primary = request.primary_attack
    if not isinstance(primary, RangedWeaponAttackExecutionResult):
        raise TypeError("nearby Stagger primary source must be a full ranged Attack result")
    attack = primary.attack
    kernel = primary.source_request.attack.kernel_request
    source = request.resolution
    resolved, expected = attack.resolution.attack, kernel.attack
    if (resolved.request_id != expected.id or resolved.impact_spec != expected.impact_spec
            or resolved.attacker_test.trace.request_id != expected.attacker_test.id
            or (resolved.defender_test is None) != (expected.defender_test is None)):
        raise ValueError("nearby Stagger primary Attack source differs from its resolved Attack")
    if resolved.defender_test is not None and resolved.defender_test.trace.request_id != expected.defender_test.id:
        raise ValueError("nearby Stagger primary Attack source differs from its Protection")
    if (primary.previous_weapon_state.weapon_id is not RangedWeaponId.BLUNDERBUSS
            or attack.resolution.attack.outcome is not AttackOutcome.HIT
            or NearbyTargetsStaggerSpec(source.source.rule_id) not in kernel.attack.secondary_effects
            or kernel.id != source.source.resolution_id
            or attack.resolution.follow_ups.count(source.source) != 1
            or attack.target_id != source.primary_target_id):
        raise ValueError("nearby Stagger source differs from primary Blunderbuss hit/trigger/target")
    if attack.request_id not in request.state.consumed_execution_ids:
        raise ValueError("nearby Stagger requires the registered primary Attack")
    for actor_id in (attack.actor_id, attack.target_id):
        participant = request.state.roster.participant(actor_id)
        if participant.turn_participant != attack.previous_state.participant_for(actor_id):
            raise ValueError("nearby Stagger primary actor/target differs from roster")
    if request.state.roster.participant(attack.target_id).state.injury != attack.resolution.target_state:
        raise ValueError("nearby Stagger requires the exact post-primary target injury")


@dataclass(frozen=True, slots=True)
class NpcNearbyStaggerExecutionResult:
    source_request: NpcNearbyStaggerExecutionRequest
    resolution: NearbyTargetsStaggerResolutionResult

    def __post_init__(self) -> None:
        if not isinstance(self.source_request, NpcNearbyStaggerExecutionRequest) or not isinstance(self.resolution, NearbyTargetsStaggerResolutionResult):
            raise TypeError("NPC nearby Stagger result requires typed source and completed resolution")
        if self.resolution.source_request != self.source_request.resolution:
            raise ValueError("NPC nearby Stagger result differs from the full executed source")
        for target in self.resolution.targets:
            impact = target.impact
            if not isinstance(impact.state, ProfileInjuryState) or impact.state.wound_limit != 1:
                raise ValueError("NPC nearby Stagger result requires Minion injury states")
            if (impact.character_wound is not None or impact.wound_effect is not None
                    or impact.pending_character_wound is not None or impact.character_wound_completion is not None
                    or impact.condition_applications or impact.deferred_wound_conditions
                    or impact.deferred_wound_condition_immunities or impact.applied_rule_ids):
                raise ValueError("NPC nearby Stagger result contains unsupported effects")
            if not all(isinstance(item, (GiveGroundRequest, ProfileStateChangeRequest)) for item in impact.follow_ups):
                raise ValueError("NPC nearby Stagger result contains unsupported follow-ups")

    @property
    def state(self) -> NpcRosterAttackState:
        source = self.source_request
        injuries = {target.target_id: target.impact.state for target in self.resolution.targets}
        participants = tuple(
            replace(p, state=replace(p.state, injury=injuries[p.state.actor_id])) if p.state.actor_id in injuries else p
            for p in source.state.roster.participants
        )
        return replace(source.state, roster=NpcRoster(participants), consumed_nearby_stagger_sources=(
            *source.state.consumed_nearby_stagger_sources, source.resolution.source,
        ))

    @property
    def pending_targets(self) -> tuple[NearbyTargetStaggerResult, ...]:
        """Keep target IDs and full impacts; equal defeat follow-ups must not be merged."""
        return tuple(target for target in self.resolution.targets if target.impact.follow_ups)

    @property
    def applied_rule_ids(self) -> tuple[str, ...]:
        return self.resolution.applied_rule_ids
