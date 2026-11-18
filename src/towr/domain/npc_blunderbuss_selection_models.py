from __future__ import annotations

from typing import TYPE_CHECKING

from towr.domain.action_execution_models import AttackActionExecutionRequest
from towr.domain.attack_models import AttackRequest, DamageImpactSpec
from towr.domain.condition_models import Condition
from towr.domain.protection_models import ProtectionPreparationRequest, ProtectionPreparationResult
from towr.domain.ranged_weapon_attack_preparation_models import RangedWeaponAttackPreparationRequest
from towr.domain.reload_models import ReloadableWeaponState
from towr.domain.resolution_models import KernelAttackRequest
from towr.domain.test_models import Skill, TestRequest

if TYPE_CHECKING:
    from towr.domain.npc_attack_selection_models import NpcAttackCandidate, NpcAttackSelectionRequest


def candidate_weapon(source: NpcAttackSelectionRequest, candidate: NpcAttackCandidate) -> ReloadableWeaponState:
    if source.round_context is None or candidate.blunderbuss is None:
        raise ValueError("Blunderbuss selection requires current round and explicit weapon context")
    matches = tuple(item.weapon_state for item in source.round_context.weapons
                    if item.actor_id == source.actor_id and item.attack_profile_id == candidate.attack_profile_id
                    and item.weapon_state.weapon_instance_id == candidate.blunderbuss.weapon_instance_id)
    if len(matches) != 1:
        raise ValueError("Blunderbuss candidate differs from current weapon binding")
    if not matches[0].loaded:
        raise ValueError("Blunderbuss candidate weapon is unloaded")
    return matches[0]


def candidate_protection(source: NpcAttackSelectionRequest, candidate: NpcAttackCandidate) -> ProtectionPreparationRequest:
    actor = source.state.roster.participant(source.actor_id)
    target = source.state.roster.participant(candidate.target_id)
    profile = next(p for p in actor.definition.attacks if p.id == candidate.attack_profile_id)
    # The weapon preparation owns range and nearby effects; the NPC profile is checked by its executor contract.
    baseline = AttackRequest(source.id + ":attack", TestRequest(source.id + ":attack-test", profile.test_profile,
        candidate.dice_modifiers), None, DamageImpactSpec(profile.damage, target.state.current_resilience), False,
        actor.state.injury.conditions.has(Condition.STAGGERED))
    return ProtectionPreparationRequest(source.id + ":protect", target.state.actor_id, baseline, Skill.SHOOTING,
        candidate.defender_is_aware, target.state.injury.conditions.has(Condition.DEFENCELESS),
        target.state.wields_weapon, target.state.holds_shield, candidate.protection_skill, candidate.protection_options)


def candidate_preparation(
    source: NpcAttackSelectionRequest, candidate: NpcAttackCandidate, protection: ProtectionPreparationResult,
) -> RangedWeaponAttackPreparationRequest:
    target = source.state.roster.participant(candidate.target_id)
    weapon = candidate_weapon(source, candidate)
    context = candidate.blunderbuss
    kernel = KernelAttackRequest(source.id + ":kernel", candidate.target_id, protection.attack,
        target.definition.injury_policy, target.state.injury, candidate.can_target_leave_zone,
        candidate.target_has_given_ground_this_round)
    attack = AttackActionExecutionRequest(source.execution_id, source.round_state, source.actor_id,
        candidate.target_id, source.slot_index, kernel)
    return RangedWeaponAttackPreparationRequest(source.id + ":weapon", weapon, attack, candidate.target_range,
        context.attacker_strength, context.has_blackpowder_lore, candidate.has_enemy_in_close_range,
        context.next_reload_cycle_id, range_approved_by_gm=candidate.range_approved_by_gm)
