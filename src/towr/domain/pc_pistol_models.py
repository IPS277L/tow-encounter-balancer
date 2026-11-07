"""One source-bound PC Pistol instance and its real Exacting reload cycle."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from towr.domain.action_execution_models import AttackActionExecutionRequest, AttackActionExecutionResult
from towr.domain.condition_models import Condition
from towr.domain.fate_models import FateGloriousSpendResult
from towr.domain.pc_heavy_wound_models import PcBodyFactKind, usable_hands, usable_weapon_hand
from towr.domain.pc_melee_models import PcMeleeWeapon, PcWeaponHand
from towr.domain.pc_shield_models import PcShieldLocation
from towr.domain.ranged_weapon_attack_models import (
    ReloadableRangedAttackExecutionRequest, ReloadableRangedAttackExecutionResult,
    _spent_weapon_state,
)
from towr.domain.ranged_weapon_attack_preparation_models import (
    RangedWeaponAttackPreparationRequest, RangedWeaponAttackPreparationResult,
    _applied_rule_ids, _execution_for, _profile_prepared_attack,
)
from towr.domain.ranged_weapon_profiles import (
    RangedWeaponId, RangedWeaponRange, ranged_weapon_combat_profile,
)
from towr.domain.reload_models import (
    ReloadableWeaponState, ReloadActionExecutionRequest, ReloadActionExecutionResult,
    create_initial_ranged_weapon_reload_state, reload_approach_id,
)
from towr.domain.test_models import Skill
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind, ImproviseKind

if TYPE_CHECKING:
    from towr.domain.pc_melee_models import PcMeleeParticipant
    from towr.domain.pc_melee_result_models import PcFateDecline, PcMeleeState, PcMeleeUnsupported


@dataclass(frozen=True, slots=True)
class PcPistolShotProof:
    preparation: RangedWeaponAttackPreparationResult
    execution: ReloadableRangedAttackExecutionResult


@dataclass(frozen=True, slots=True)
class PcPistolReloadProof:
    request: ReloadActionExecutionRequest
    result: ReloadActionExecutionResult
    fate_decline: PcFateDecline | None
    glorious: FateGloriousSpendResult | None = None


def initial_pc_pistol(source: PcMeleeParticipant) -> ReloadableWeaponState | None:
    if source.pc.weapon is not PcMeleeWeapon.PISTOL:
        return None
    result = create_initial_ranged_weapon_reload_state(source.actor_id+':weapon', RangedWeaponId.PISTOL)
    assert type(result) is ReloadableWeaponState
    return result


def _held_pc_pistol(state: PcMeleeState, actor: str, *, loaded: bool) -> ReloadableWeaponState:
    source = state.source.participant(actor)
    member = state.participant(actor)
    weapon = member.pistol
    if (source.pc.weapon is not PcMeleeWeapon.PISTOL or source.pc.pistol is None
            or type(weapon) is not ReloadableWeaponState
            or weapon.weapon_id is not RangedWeaponId.PISTOL
            or weapon.weapon_instance_id != actor+':weapon'
            or weapon.loaded is not loaded
            or type(usable_weapon_hand(member)) is not PcWeaponHand
            or member.injury.dead or member.injury.conditions.has(Condition.DEFENCELESS)):
        raise ValueError('PC Pistol action requires its actual held weapon and loaded state')
    return weapon


def prepare_pc_pistol_shot(
    state: PcMeleeState, request: AttackActionExecutionRequest,
) -> RangedWeaponAttackPreparationResult:
    from towr.domain.pc_melee_result_models import pc_melee_action_id
    actor = request.actor_id
    weapon = _held_pc_pistol(state, actor, loaded=True)
    source = state.source.participant(actor).pc
    preparation = RangedWeaponAttackPreparationRequest(
        id=pc_melee_action_id(state, actor)+':pistol:prepare',
        weapon_state=weapon,
        attack=request,
        target_range=RangedWeaponRange.CLOSE,
        attacker_strength=source.strength,
        has_blackpowder_lore=source.pistol.has_blackpowder_lore,
        has_enemy_in_close_range=True,
        next_reload_cycle_id=pc_melee_action_id(state, actor)+':pistol:cycle',
        uses_optional_reload_bonus=False,
        aim=None,
    )
    profile = ranged_weapon_combat_profile(weapon.weapon_id)
    attack = _profile_prepared_attack(preparation)
    return RangedWeaponAttackPreparationResult(
        request_id=preparation.id,
        rule_id=preparation.rule_id,
        source_request=preparation,
        profile=profile,
        profile_attack=attack,
        aim_follow_up=None,
        execution=_execution_for(preparation, attack),
        applied_rule_ids=_applied_rule_ids(preparation, profile, None),
    )


def complete_pc_pistol_shot(
    state: PcMeleeState,
    base_request: AttackActionExecutionRequest,
    effective_request: AttackActionExecutionRequest,
    execution: AttackActionExecutionResult,
) -> PcPistolShotProof:
    """Bind preparation before Fate and consumption to the effective Attack."""
    preparation = prepare_pc_pistol_shot(state, base_request)
    source = preparation.execution
    request = ReloadableRangedAttackExecutionRequest(
        id=source.id,
        attack_skill=source.attack_skill,
        attack=effective_request,
        weapon_state=source.weapon_state,
        next_reload_cycle_id=source.next_reload_cycle_id,
        uses_optional_reload_bonus=source.uses_optional_reload_bonus,
        rule_id=source.rule_id,
    )
    result = ReloadableRangedAttackExecutionResult(
        request_id=request.id,
        rule_id=request.rule_id,
        source_request=request,
        attack=execution,
        previous_weapon_state=request.weapon_state,
        weapon_state=_spent_weapon_state(request),
        applied_rule_ids=tuple(dict.fromkeys((request.rule_id, *execution.applied_rule_ids))),
    )
    return PcPistolShotProof(preparation, result)


def pistol_reload_declaration(state: PcMeleeState, actor: str) -> CombatActionDeclaration:
    _held_pc_pistol(state, actor, loaded=False)
    return CombatActionDeclaration(CombatActionKind.IMPROVISE,
        improvise_kind=ImproviseKind.SKILL,
        improvise_approach_id=reload_approach_id(actor+':weapon'))


def build_pc_pistol_reload(state: PcMeleeState) -> ReloadActionExecutionRequest:
    from towr.domain.pc_melee_result_models import _pc_test, pc_melee_action_id
    turn = state.round_state.active_turn
    if turn is None:
        raise ValueError('PC Pistol Reload requires its own active turn')
    actor = turn.actor_id
    weapon = _held_pc_pistol(state, actor, loaded=False)
    member = state.participant(actor)
    if len(usable_hands(member)) != 2 or (member.shield is not None
            and member.shield.location is PcShieldLocation.HELD):
        raise ValueError('PC Pistol Reload requires two available hands')
    action = pc_melee_action_id(state, actor)
    return ReloadActionExecutionRequest(
        id=action+':reload:execute',
        round_state=state.round_state,
        actor_id=actor,
        actor_conditions=member.injury.conditions,
        slot_index=1,
        weapon_state=weapon,
        dexterity_test=_pc_test(state, actor, action+':reload:dexterity', Skill.DEXTERITY),
    )


def pc_pistol_unsupported(state: PcMeleeState) -> PcMeleeUnsupported | None:
    """Stop only at the actual next Shoot/Reload boundary after continuations."""
    if (state.pending or state.pending_wound is not None
            or not state.live_party or not state.live_enemies):
        return None
    turn = state.round_state.active_turn
    if (turn is None or turn.action_slots
            or turn.actor_id not in state.source.pc_activation_order):
        return None
    actor = turn.actor_id
    member = state.participant(actor)
    weapon = member.pistol
    if (state.source.participant(actor).pc.weapon is not PcMeleeWeapon.PISTOL
            or weapon is None or member.injury.dead
            or member.injury.conditions.has(Condition.DEFENCELESS)):
        return None
    from towr.domain.pc_melee_result_models import PcMeleeUnsupported, _pc_recover_needed
    hands = usable_hands(member)
    if not hands:
        reason = 'pistol_grip_unavailable'
    elif (not weapon.loaded and len(hands) == 1
            and usable_weapon_hand(member) is not None and not _pc_recover_needed(member)):
        reason = 'pistol_reload_hands_unavailable'
    else:
        return None
    facts = tuple(f for f in member.body_facts if f.kind in (
        PcBodyFactKind.UNUSABLE_ARM, PcBodyFactKind.LOST_ARM, PcBodyFactKind.CLUTCH_STOMACH))
    fact = max(facts, key=lambda f: f.wound_sequence)
    wound = member.injury.wounds[fact.wound_sequence-1]
    source_id = (f'{weapon.rule_id}:{actor}:w{wound.sequence}:{fact.kind.value}:'
        f'{weapon.weapon_instance_id}:{weapon.reload_cycle_id or "initial-loaded"}:{reason}')
    return PcMeleeUnsupported(actor, source_id, reason, wound.sequence, wound.table_total)
