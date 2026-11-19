"""Pure projections of the explicit M9 journal variants; no RNG or execution."""
from dataclasses import replace
from towr.domain.pc_weapon_inventory import replace_pc_member, pc_grip, pc_item_weapon
from towr.domain.pc_magic_models import (MAGIC_PROOFS,project_pc_magic_step,consume_magic_modifiers,
    expected_magic_interruption)
from towr.domain.pc_potion_models import PcPotionRecoverProof, build_pc_potion_recover, selected_pc_potion
from towr.domain.pc_melee_models import PcTwoHandedGrip

from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcAttackerStaggerProof, PcEnduranceProof, PcHandDropProof, PcMeleeState,
    PcProfileWoundProof, PcMinionStaggerDefeatProof, PcRecoverProof, PcTimedWound, PcTurnEndProof, PcWoundCompletionProof,
    PcBodyConsequenceProof, PcWoundChoiceProof, PcHandSwapProof, PcBackupWeaponDrawProof, PcCriticalProof, PcIncapacitatedTurnEndProof, PcHelpProof, PcNpcHelpProof,
    build_pc_melee_attack, build_pc_melee_recover, build_pc_wound_completion, pc_after_test, pc_melee_action_id,
    pc_melee_next_actor, pc_melee_selected_action, pc_melee_unsupported,pc_melee_action_declaration,pc_attack_skill,
    validate_pc_melee_combat_shape, validate_pc_melee_state_shape, validate_pc_melee_source_types,
    _decline, _enemy_update, _party_update, _pc_test, _ready, _test_result, pc_melee_round_participants,
)
from towr.domain.attack_models import AttackOutcome, DamageImpactSpec, ImpactOutcome, MissConsequence
from towr.domain.pc_ranged_models import (PcRangedReloadProof,build_pc_ranged_reload,complete_pc_ranged_shot)
from towr.domain.pc_aim_models import (PcAimProof, PcAimSecondActionProof, PcAimConsumptionProof,
    expected_pc_aim_consumption, project_pc_aim_step, build_pc_aim_second_action)
from towr.domain.pc_npc_aim_models import (PcNpcAimProof,PcNpcAimConsumptionProof,
    expected_npc_aim_consumption,project_npc_aim_step)
from towr.domain.pc_blunderbuss_models import PcBlunderbussNearbyProof, project_pc_blunderbuss_nearby, pc_blunderbuss_snapshot
from towr.domain.pc_blunderbuss_models import (BATTLEFIELD_NEARBY_PROOFS,
    current_pc_blunderbuss_wave,project_pc_battlefield_nearby)
from towr.domain.resolution_models import NearbyTargetsStaggerRequest
from towr.domain.attack_models import NearbyTargetsStaggerSpec
from towr.domain.pc_short_opening_models import PcNpcApproachProof, expected_pc_npc_approach
from towr.domain.pc_battlefield_movement_models import (
    PcBattlefieldMoveProof, PcBattlefieldRecoverProof, expected_pc_battlefield_move,
    build_pc_battlefield_npc_recover, battlefield_recovered_injury,
)
from towr.domain.pc_battlefield_manoeuvre_models import (BATTLEFIELD_MANOEUVRE_PROOFS,
    project_pc_battlefield_manoeuvre,current_pc_charge)
from towr.domain.pc_mount_models import PcDismountProof,expected_pc_dismount,updated_pc_mounts
from towr.domain.pc_demigryph_models import (PcDemigryphIntentProof,PcDemigryphStrikeProof,
    expected_pc_demigryph_intent,build_pc_demigryph_strike,latest_pc_kernel_attack,pc_kernel_resolution)
from towr.domain.pc_falling_models import (PcFallingProof,PcFallingAcknowledgementProof,
    expected_pc_falling_request,falling_acknowledgement_source,project_pc_falling_step)
from towr.domain.pc_briarroot_weapon_models import (PcBriarrootWeaponDropProof,
    PcBriarrootWeaponPickupProof,PcBriarrootWeaponApproachProof,
    expected_briarroot_weapon_loss,apply_briarroot_weapon_drop,
    expected_briarroot_weapon_approach,apply_briarroot_weapon_approach,
    apply_briarroot_weapon_pickup,briarroot_pc_pickup_updates)
from towr.domain.pc_weighted_net_models import (NET_PROOFS,PcNetReleaseProof,PcNetPickupProof,
    PcNetApproachProof,PcNetIncidentalPickupProof,PcNetRecoverKind,
    expected_weighted_net_approach,expected_weighted_net_incidental_pickup,
    project_weighted_net_step,weighted_net_updates_from_attack,weighted_nets_after_equipment)
from towr.domain.pc_npc_ranged_models import (
    PcNpcRangedReloadProof, build_pc_npc_ranged_reload, complete_pc_npc_ranged_shot,
    pc_npc_ranged_weapon, npc_ranged_inventory_update, npc_ranged_inventory_update_enemies,
)
from towr.domain.reload_models import _complete_reload_action_after_test
from towr.domain.pc_shield_models import (PcShieldReleaseProof, PcShieldState, PcShieldLocation,
    expected_pc_shield_release)
from towr.domain.pc_net_models import (PcNpcNetDrawProof, expected_pc_npc_net_draw, is_net_impact,
    expected_net_resolution, net_condition_sources_from_attack, spend_pc_npc_net)
from towr.domain.injury_models import (
    CharacterWoundRequest, CharacterWoundType, ProfileNpcType, ProfileStateChangeRequest, ProfileWoundResult,
    WoundConditionEffect, WoundConsequence, WoundConsequenceRequest, WoundEffectDuration,
    WoundEnduranceFailure, WoundEnduranceTestRequest, WoundEntryId,
    WoundRestriction, WoundRestrictionEffect,
    MinionStaggerDefeatCause,MinionStaggerDefeatResult,
)
from towr.domain.condition_models import Condition, ConditionState, StaggerChoice, StaggerOutcome, StaggerResult
from towr.domain.fate_models import _expected_fate_burn, FATE_SESSION_RULE_ID, FATE_BURN_RULE_ID
from towr.domain.fate_near_miss_models import FateNearMissApplicationRequest, _near_miss_applied_rule_ids
from towr.domain.pc_melee_models import PcWeaponHand
from towr.domain.pc_fate_test_models import validate_pc_test_fate
from towr.domain.pc_help_models import build_pc_help_action, pc_attack_help_applications
from towr.domain.pc_npc_help_models import build_pc_npc_help_action,pc_npc_attack_help_applications
from towr.domain.pc_npc_extra_attack_models import build_pc_npc_extra_attack_slot
from towr.domain.pc_npc_distraction_models import (PcNpcDistractionExpiredProof,
    expected_pc_npc_distraction_expiry,distraction_from_profile_wound,ordered_npc_distractions)
from towr.domain.pc_npc_grudge_models import (PcNpcGrudgeEncounterProof,
    expected_pc_npc_grudge_encounter,grudge_distraction_from_encounter)
from towr.domain.pc_bestigor_models import (PcNpcBloodRageProof,
    expected_pc_npc_blood_rage, pc_bestigor_glorious_source)
from towr.domain.pc_flagellant_models import (PcNpcRecoverProof, PcFlagellantMissWoundProof,
    build_pc_npc_recover, flagellant_recovered_injury, build_pc_flagellant_miss_wound,
    expected_flagellant_miss_wound)
from towr.domain.minion_defeat_models import MinionDefeatDecision
from towr.domain.resolution_models import AttackerStaggerRequest, condition_forces_wound
from towr.domain.pc_heavy_wound_models import (PcBodyFact, PcBodyFactKind, usable_hands, usable_weapon_hand, has_ongoing_condition, critical_for_action, critical_for_hand, critical_for_incidental_hand_use)
from towr.domain._pc_heavy_wound_projection import heavy_wound_effect, body_consequence, consequence_sides, clutch_candidates
from towr.domain.critical_injury_models import CriticalInjuryTestRequest
from towr.domain.test_models import Skill
from towr.domain.pc_backup_weapon_models import pc_backup_draw_hand, pc_preferred_weapon_hand
from towr.domain.pc_npc_wound_models import (official_profile_wound_state,elf_merchant_profile_wound_state,
    pc_npc_drained_profile_wound_state,pc_npc_prone_profile_wound_state)
from towr.domain.pc_hit_condition_models import (expected_pc_hit_target,hit_condition_sources_from_attack,
    pc_pre_stagger_target)
from towr.domain.pc_npc_exit_models import PcNpcExitProof,expected_pc_npc_exit
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlot,
    CombatActionSlotResult, CombatRoundAdvanceResult, CombatRoundState, CombatSide,
    CombatTurnParticipant, CombatTurnStartResult, CombatTurnState,
)
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleOutcome, CharacterWoundLifecycleRollRequest, _state_after_near_miss, _completion_rule_ids,
)


def _same(actual, expected, message):
    if actual != expected:
        raise ValueError(message)
    validate_pc_melee_source_types(actual,expected)


def _inventory_conditions(state,updates):
    from towr.domain.pc_inventory_conditions import reconcile_pc_inventory_burden,reconcile_npc_inventory_burden
    if 'party' in updates:
        updates['party']=tuple(reconcile_pc_inventory_burden(state,member) for member in updates['party'])
    if 'enemies' in updates:
        updates['enemies']=tuple(reconcile_npc_inventory_burden(state,enemy,
            weighted_nets=updates.get('weighted_nets')) for enemy in updates['enemies'])
    return updates


def _canonical_attack(request, attack):
    from towr.domain.brawn_impact_models import BrawnDisplacementImpactSpec
    from towr.domain.weapon_impact_preparation import is_stagger_weapon_impact,is_oil_impact,is_blast_impact
    if type(attack.request_id) is not str or not (isinstance(attack.impact_spec,DamageImpactSpec)
            or is_net_impact(attack.impact_spec) or is_stagger_weapon_impact(attack.impact_spec)
            or is_oil_impact(attack.impact_spec) or is_blast_impact(attack.impact_spec)
            or type(attack.impact_spec) is BrawnDisplacementImpactSpec):
        raise TypeError('PC Attack requires its exact ID and ordinary Damage spec')
    replace(attack.impact_spec)
    if isinstance(attack.impact_spec,DamageImpactSpec):
        replace(attack.impact_spec.damage)
        replace(attack.impact_spec.resilience)
    if (not isinstance(attack.outcome,AttackOutcome) or not isinstance(attack.miss_consequence,MissConsequence)
            or attack.impact is not None and not isinstance(attack.impact,ImpactOutcome)
            or type(attack.tie_break_applied) is not bool):
        raise TypeError('PC Attack outcomes must use their canonical enum/bool types')
    for value in (attack.success_margin,attack.damage,attack.effective_resilience):
        if value is not None and type(value) is not int:
            raise TypeError('PC Attack arithmetic must use exact integers')
    _test_result(request.attacker_test, attack.attacker_test)
    if request.defender_test is None:
        if attack.defender_test is not None:
            raise ValueError("unopposed Attack cannot invent a Protection Test")
    else:
        _test_result(request.defender_test, attack.defender_test)
    a, d = attack.attacker_test.successes, (attack.defender_test.successes if attack.defender_test is not None else 0)
    hit = a > 0 and a >= d
    margin = a-d if hit else 0
    numeric = isinstance(request.impact_spec,DamageImpactSpec)
    from towr.domain.attack_models import effective_damage_modifiers,effective_ignores_armour,armour_ward_cancels_effects
    from towr.domain.armour_models import METEORIC_PROTECTION_RULE_ID
    damage_modifiers=effective_damage_modifiers(request.impact_spec) if numeric else ()
    damage = (request.impact_spec.damage.base + margin * request.impact_spec.damage.success_multiplier
        + sum(m.amount for m in damage_modifiers)) if hit and numeric else None
    resilience = ((request.impact_spec.resilience.toughness if effective_ignores_armour(request.impact_spec)
        else request.impact_spec.resilience.total)+sum(m.amount for m in request.impact_spec.resilience_modifiers)) if hit and numeric else None
    impact = (ImpactOutcome.WOUND if damage > resilience else ImpactOutcome.STAGGERED) if hit and numeric else None
    miss = MissConsequence.NONE if hit or not request.is_close_range or request.attacker_is_staggered else MissConsequence.STAGGER_ATTACKER
    tie = hit and request.defender_test is not None and a == d
    rules = ((tuple(m.rule_id for m in (*damage_modifiers,*request.impact_spec.resilience_modifiers))
        + ((METEORIC_PROTECTION_RULE_ID,) if armour_ward_cancels_effects(request.impact_spec) else ()) if numeric
        else (request.impact_spec.rule_id,)) if hit else ())
    if tie:
        rules = (*rules, 'RULE-COMBAT-006:attack-tie')
    expected = (request.id,AttackOutcome.HIT if hit else AttackOutcome.MISS,margin,request.impact_spec,
        damage,resilience,impact,miss,tie,rules)
    actual = (attack.request_id,attack.outcome,attack.success_margin,attack.impact_spec,
        attack.damage,attack.effective_resilience,attack.impact,attack.miss_consequence,
        attack.tie_break_applied,attack.applied_rule_ids)
    _same(actual,expected,'PC Attack result is not canonical for its actual Tests/source')
    for value in (a,d,margin):
        if type(value) is not int:
            raise TypeError('Attack arithmetic must use exact integers')


class _SufferWoundDecision:
    def choose_repeated_stagger(self,*,request,allowed_choices):
        return StaggerChoice.SUFFER_WOUND


def _ordinary_resolution(kernel, result, *, state=None, action_request=None):
    from towr.domain.brawn_impact_models import BrawnDisplacementImpactSpec
    if type(kernel.attack.impact_spec) is BrawnDisplacementImpactSpec:
        _same(result,_expected_brawn_resolution(kernel,result.attack),'Brawn displacement changed its actual special impact')
        return
    from towr.domain.weapon_impact_preparation import is_oil_impact,is_blast_impact
    if is_oil_impact(kernel.attack.impact_spec) or is_blast_impact(kernel.attack.impact_spec):
        from towr.domain.pc_weapon_area_models import expected_area_primary_resolution
        _same(result,expected_area_primary_resolution(kernel,result.attack),'area primary changed its exact special impact')
        return
    if is_net_impact(kernel.attack.impact_spec):
        _same(result,expected_net_resolution(kernel,result.attack),'Net primary resolution changed its actual source')
        return
    effective_target,_ = pc_pre_stagger_target(kernel,result.attack.outcome)
    kernel = replace(kernel,target_state=effective_target)
    from towr.domain.weapon_impact_preparation import is_stagger_weapon_impact
    from towr.domain.resolution_models import ConditionImpactResult
    unarmed=is_stagger_weapon_impact(kernel.attack.impact_spec)
    application=_unarmed_application(kernel,result.attack) if unarmed else None
    expected_replacement=None if application is None else ConditionImpactResult(application)
    _same(result.replacement_impact,expected_replacement,'primary Staggered changed its actual Condition receipt')
    if (result.monstrosity_impact is not None
            or result.wound_effect is not None or result.character_wound_completion is not None
            or result.deferred_wound_conditions != () or result.deferred_wound_condition_immunities != ()):
        raise ValueError('ordinary PC Attack cannot carry foreign effect/secondary/completion branches')
    expected_stagger = None
    forced_minion = (kernel.minion_stagger_defeat is not None
        and kernel.target_state.conditions.has(Condition.STAGGERED))
    if (result.attack.outcome is AttackOutcome.HIT and (result.attack.impact is ImpactOutcome.STAGGERED or unarmed)
            and not forced_minion and (unarmed or not condition_forces_wound(kernel,result.attack))):
        conditions = kernel.target_state.conditions
        if kernel.first_stagger_wound is not None:
            expected_stagger = StaggerResult(kernel.id+':stagger',conditions,StaggerOutcome.WOUND_REQUESTED,
                (),None,True,False)
        elif conditions.has(Condition.STAGGERED):
            from towr.domain.condition_models import StaggerRequest
            from towr.rules.stagger_resolution import resolve_stagger
            decisions=_SufferWoundDecision()
            if state is not None:
                from towr.domain.pc_give_ground_models import pc_attack_decisions
                decisions=pc_attack_decisions(state,action_request,decisions)
            expected_stagger=resolve_stagger(StaggerRequest(kernel.id+':stagger',conditions,
                kernel.can_target_leave_zone,kernel.target_has_given_ground_this_round),decisions=decisions)
        else:
            expected_stagger = StaggerResult(kernel.id+':stagger',conditions.with_condition(Condition.STAGGERED),
                StaggerOutcome.CONDITION_ADDED,(),None,False,False)
    _same(result.stagger,expected_stagger,'ordinary PC Attack has a forged/missing Staggered decision')
    if result.stagger is not None:
        stagger = result.stagger
        ConditionState(stagger.state.conditions)
        if (not isinstance(stagger.outcome,StaggerOutcome)
                or stagger.selected_choice is not None and not isinstance(stagger.selected_choice,StaggerChoice)
                or any(not isinstance(choice,StaggerChoice) for choice in stagger.allowed_choices)
                or type(stagger.wound_requested) is not bool or type(stagger.gave_ground) is not bool):
            raise TypeError('Staggered proof requires canonical enum/bool fields')


def _unarmed_application(kernel,attack):
    if attack.outcome is not AttackOutcome.HIT:return None
    if kernel.target_effect_immunities:
        raise ValueError('Unarmed requires its actual ordinary Condition source without unmodelled immunities')
    from towr.domain.condition_models import ConditionApplicationResult
    rule=kernel.attack.impact_spec.rule_id
    conditions=kernel.target_state.conditions
    return ConditionApplicationResult(kernel.id+':condition-impact',conditions.with_condition(Condition.STAGGERED),
        Condition.STAGGERED,conditions.has(Condition.STAGGERED),False,rule,None,(rule,))


def _expected_brawn_resolution(kernel,attack):
    from towr.domain.brawn_impact_models import BrawnDisplacementRequest,BrawnDisplacementImpactResult
    from towr.domain.resolution_models import ResolutionResult
    if attack.outcome is AttackOutcome.MISS:
        return ResolutionResult(kernel.id,attack,None,kernel.target_state,None,None,None,None,None,
            (AttackerStaggerRequest(kernel.attack.id),) if attack.miss_consequence is MissConsequence.STAGGER_ATTACKER else ())
    before,_=pc_pre_stagger_target(kernel,attack.outcome)
    target,applications,rules=expected_pc_hit_target(kernel,attack.outcome,before)
    pending=BrawnDisplacementRequest(kernel.id,kernel.attack.id,kernel.attack.impact_spec,kernel.target_id)
    return ResolutionResult(kernel.id,attack,BrawnDisplacementImpactResult(pending),target,
        None,None,None,None,None,(pending,),condition_applications=applications,applied_secondary_rule_ids=rules)


def _canonical_wound_effect(completion):
    roll = completion.source_request.roll
    raw = roll.wound_result
    request = raw.effect_request
    wound = raw.state.wounds[-1]
    current = completion.source_request.current_state
    effects = list(current.active_wound_effects)
    conditions = current.conditions
    followups = ()
    total = wound.table_total
    if total in (4,5,7):
        failure = {4:WoundEnduranceFailure.DROP_RANDOM_HAND_ITEM,5:WoundEnduranceFailure.FALL_PRONE,
            7:WoundEnduranceFailure.BLINDED_UNTIL_END_OF_NEXT_TURN}[total]
        followups = (WoundEnduranceTestRequest(request.id+':endurance',wound.sequence,wound.entry_id,failure,request.rule_id),)
    elif total == 6:
        effects.append(WoundConditionEffect(wound.sequence,Condition.DRAINED,WoundEffectDuration.END_OF_NEXT_TURN))
        conditions = conditions.with_condition(Condition.DRAINED)
    elif total == 8:
        effects.append(WoundRestrictionEffect(wound.sequence,WoundRestriction.CANNOT_AIM,WoundEffectDuration.UNTIL_TREATED))
        followups = (WoundConsequenceRequest(wound.sequence,WoundConsequence.DROP_RANDOM_HAND_ITEM,request.rule_id),)
    elif total == 9:
        effects.extend((WoundConditionEffect(wound.sequence,Condition.PRONE,WoundEffectDuration.UNTIL_REMOVED),
            WoundRestrictionEffect(wound.sequence,WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN,WoundEffectDuration.UNTIL_TREATED)))
        conditions = conditions.with_condition(Condition.PRONE)
    elif total == 10:
        effects.extend((WoundConditionEffect(wound.sequence,Condition.DRAINED,WoundEffectDuration.UNTIL_TREATED),
            WoundRestrictionEffect(wound.sequence,WoundRestriction.NEXT_TEST_IS_GRIM,WoundEffectDuration.NEXT_TEST)))
        conditions = conditions.with_condition(Condition.DRAINED)
    elif 11 <= total <= 23:
        expected,followups = heavy_wound_effect(replace(raw,state=current),request)
        effect = completion.wound_effect
        replace(effect.request)
        for follow_up in effect.follow_ups:
            replace(follow_up)
        _same((effect.request,effect.state,effect.follow_ups),(request,expected,followups),
            'heavy PC Wound completion changed its exact effects/follow-ups')
        return
    wounds = (*raw.state.wounds[:-1],replace(wound,effect_resolved=True))
    expected = replace(current,wounds=wounds,conditions=conditions,active_wound_effects=tuple(effects))
    effect = completion.wound_effect
    replace(effect.request)
    for follow_up in effect.follow_ups:
        replace(follow_up)
    _same((effect.request,effect.state,effect.follow_ups),(request,expected,followups),
        'PC Wound completion has forged immediate effects/follow-ups')


def _kernel_impact_updates(state, request, result, pc_actor, pc_fate, pc_injury):
    """Validate and project one real K1 strike, independently of action receipts."""
    expected = request
    member = state.participant(pc_actor)
    before,_ = pc_pre_stagger_target(expected.kernel_request,result.attack.outcome)
    from towr.domain.brawn_impact_models import BrawnDisplacementImpactSpec
    if type(expected.kernel_request.attack.impact_spec) is BrawnDisplacementImpactSpec:
        enemies=state.enemies
        if expected.target_id==pc_actor:
            pc_injury=result.target_state
        else:
            enemies=_enemy_update(state,expected.target_id,result.target_state)
        return dict(party=_party_update(state,pc_actor,injury=pc_injury,fate=pc_fate),enemies=enemies,
            pending=result.follow_ups,pending_wound=None,
            pending_actor_id=(expected.target_id if result.attack.outcome is AttackOutcome.HIT else pc_actor)
                if result.follow_ups else None)
    from towr.domain.weapon_impact_preparation import is_stagger_weapon_impact,is_oil_impact,is_blast_impact
    if is_oil_impact(expected.kernel_request.attack.impact_spec) or is_blast_impact(expected.kernel_request.attack.impact_spec):
        enemies=state.enemies
        if expected.target_id==pc_actor:
            pc_injury=result.target_state
        else:
            enemies=_enemy_update(state,expected.target_id,result.target_state)
        return dict(party=_party_update(state,pc_actor,injury=pc_injury,fate=pc_fate),enemies=enemies,
            pending=result.follow_ups,pending_wound=None)
    unarmed=is_stagger_weapon_impact(expected.kernel_request.attack.impact_spec)
    staggered_impact=result.attack.impact is ImpactOutcome.STAGGERED or unarmed
    pending_wound = None
    forced_defeat = None
    spec = expected.kernel_request.minion_stagger_defeat
    if (spec is not None and result.attack.outcome is AttackOutcome.HIT
            and staggered_impact
            and before.conditions.has(Condition.STAGGERED)
            and (unarmed or not condition_forces_wound(expected.kernel_request,result.attack))):
        cause = MinionStaggerDefeatCause(expected.kernel_request.id+':minion-stagger-defeat',
            expected.target_id,spec.rule_id)
        forced_target = replace(before,defeated=True,defeat_cause=cause)
        forced_defeat = MinionStaggerDefeatResult(cause.source_id,forced_target,cause,(spec.rule_id,))
    _same(result.minion_stagger_defeat,forced_defeat,'Attack changed its actual non-Wound Minion defeat')
    if result.attack.outcome is AttackOutcome.MISS:
        base_target = before
        _same(result.target_state,before,'miss changed the target injury')
        followups = ((AttackerStaggerRequest(expected.kernel_request.attack.id),)
            if result.attack.miss_consequence is MissConsequence.STAGGER_ATTACKER else ())
        if result.character_wound is not None or result.profile_wound is not None or result.pending_character_wound is not None:
            raise ValueError('miss invented a Wound')
    elif is_net_impact(expected.kernel_request.attack.impact_spec):
        base_target = result.target_state
        followups = ()
    elif (staggered_impact and not before.conditions.has(Condition.STAGGERED)
            and expected.kernel_request.first_stagger_wound is None
            and (unarmed or not condition_forces_wound(expected.kernel_request,result.attack))):
        target = replace(before,conditions=before.conditions.with_condition(Condition.STAGGERED))
        base_target = target
        followups = ()
        if result.character_wound is not None or result.profile_wound is not None or result.pending_character_wound is not None:
            raise ValueError('first Staggered invented a Wound')
    elif forced_defeat is not None:
        if (result.character_wound is not None or result.profile_wound is not None
                or result.pending_character_wound is not None):
            raise ValueError('Dirty Coward cannot invent a Wound')
        base_target = forced_defeat.state
        followups = (forced_defeat.cause,)
    elif result.stagger is not None and not result.stagger.wound_requested:
        if any(value is not None for value in (result.character_wound,result.profile_wound,result.pending_character_wound)):
            raise ValueError('Give Ground or falling Prone cannot invent a Wound')
        base_target=replace(before,conditions=result.stagger.state)
        followups=()
        if result.stagger.gave_ground:
            from towr.domain.resolution_models import GiveGroundRequest,ConditionAfterGiveGroundRequest
            from towr.domain.attack_models import ConditionAfterGiveGroundSpec,ConditionOnGiveGroundOrWoundSpec
            followups=(GiveGroundRequest(expected.kernel_request.id),*(ConditionAfterGiveGroundRequest(
                resolution_id=expected.kernel_request.id,condition=effect.condition,rule_id=effect.rule_id,
                classification=effect.classification,target_effect_immunities=expected.kernel_request.target_effect_immunities)
                for effect in expected.kernel_request.attack.secondary_effects
                if type(effect) in (ConditionAfterGiveGroundSpec,ConditionOnGiveGroundOrWoundSpec)))
    elif expected.target_id == pc_actor:
        if result.profile_wound is not None:
            raise ValueError('PLAYER Wound cannot carry a profile-NPC Wound branch')
        pending_wound = result.pending_character_wound
        if pending_wound is None:
            raise ValueError('PLAYER Wound must preserve its pending Near Miss window')
        replace(pending_wound)
        wound_source = pending_wound.source_request
        kernel = expected.kernel_request
        actual_source = CharacterWoundLifecycleRollRequest(kernel.id+':wound-lifecycle',pc_actor,
            CharacterWoundRequest(kernel.id+':wound',before,CharacterWoundType.PLAYER,
                kernel.wound_dice_modifiers,kernel.wound_negation_options,
                fixed_entry=kernel.fixed_character_wound))
        replace(wound_source)
        replace(wound_source.wound)
        _same(wound_source,actual_source,'PC Wound pool/options/IDs differ from the actual ordinary Attack')
        base_target = pending_wound.wound_result.state
        _same((result.character_wound,result.wound_effect),
            (pending_wound.wound_result,None),'PC Wound effects preceded its Fate window')
        followups = ()
    else:
        if result.character_wound is not None or result.pending_character_wound is not None:
            raise ValueError('NPC profile Wound cannot carry a PLAYER lifecycle branch')
        wounds = min(before.wounds+1,before.wound_limit)
        from towr.domain.injury_models import ProfileDecapitationCause
        decapitation=(ProfileDecapitationCause(expected.kernel_request.id+':wound',expected.target_id)
            if expected.kernel_request.fixed_character_wound is not None else None)
        defeated = wounds == before.wound_limit or decapitation is not None
        target = replace(before,wounds=wounds,defeated=defeated,
            conditions=before.conditions.without_condition(Condition.STAGGERED),defeat_cause=decapitation)
        base_target = target
        _same(getattr(result.profile_wound,'state',None),target,'NPC profile Wound changed unrelated state')
        npc_type = ProfileNpcType(state.enemy(expected.target_id).definition.injury_policy.value)
        change = ProfileStateChangeRequest(npc_type,before.wounds,wounds,defeated)
        if type(result.profile_wound) is not ProfileWoundResult:
            raise TypeError('NPC profile Wound requires its typed K1 result')
        if result.profile_wound.state != target or result.profile_wound.state_change != change:
            raise ValueError('NPC Wound lacks its exact profile change')
        profile = result.profile_wound
        replace(profile.state)
        replace(result.target_state)
        ConditionState(profile.state.conditions.conditions)
        _same((profile.request_id,profile.wounds_requested,profile.wounds_inflicted,profile.applied_rule_ids),
            (expected.kernel_request.id+':wound',1,1,() if decapitation is None else (decapitation.rule_id,)),
            'NPC profile Wound has a foreign source or count')
        if (type(profile.wounds_requested) is not int or type(profile.wounds_inflicted) is not int
                or type(profile.state_change.previous_wounds) is not int
                or type(profile.state_change.current_wounds) is not int
                or type(profile.state_change.defeated) is not bool
                or not isinstance(profile.state_change.npc_type,ProfileNpcType)):
            raise TypeError('NPC profile Wound requires typed source/count fields')
        if type(profile.request_id) is not str:
            raise TypeError('NPC profile Wound ID must be a string')
        followups = (change,)
    target,applications,secondary_rules = expected_pc_hit_target(expected.kernel_request,result.attack.outcome,base_target)
    if unarmed and result.attack.outcome is AttackOutcome.HIT:
        application=_unarmed_application(replace(expected.kernel_request,target_state=before),result.attack)
        applications=(application,*applications)
    if is_net_impact(expected.kernel_request.attack.impact_spec):
        canonical_net = expected_net_resolution(expected.kernel_request,result.attack)
        target,applications,secondary_rules = (canonical_net.target_state,canonical_net.condition_applications,
            canonical_net.applied_secondary_rule_ids)
    if forced_defeat is not None:
        secondary_rules = (*forced_defeat.applied_rule_ids,*secondary_rules)
    if (expected.kernel_request.first_stagger_wound is not None and result.attack.outcome is AttackOutcome.HIT
            and staggered_impact
            and (unarmed or not condition_forces_wound(expected.kernel_request,result.attack))):
        secondary_rules = (expected.kernel_request.first_stagger_wound.rule_id,*secondary_rules)
    if result.attack.outcome is AttackOutcome.HIT:
        for effect in expected.kernel_request.attack.secondary_effects:
            if type(effect) is NearbyTargetsStaggerSpec:
                followups = (*followups,NearbyTargetsStaggerRequest(expected.kernel_request.id,effect.rule_id))
                secondary_rules = (*secondary_rules,effect.rule_id)
    if result.stagger is not None and result.stagger.gave_ground:
        from towr.domain.attack_models import ConditionAfterGiveGroundSpec,ConditionOnGiveGroundOrWoundSpec
        secondary_rules=tuple(effect.rule_id for effect in expected.kernel_request.attack.secondary_effects
            if type(effect) in (ConditionAfterGiveGroundSpec,ConditionOnGiveGroundOrWoundSpec))+secondary_rules
    _same((result.target_state,result.condition_applications,result.applied_secondary_rule_ids),
        (target,applications,secondary_rules),'PC Attack changed its canonical on-hit Condition application or target')
    _same(result.follow_ups,followups,'PC Attack altered mandatory follow-up order')
    enemies = state.enemies
    if expected.target_id == pc_actor:
        pc_injury = result.target_state
        hit_sources = (*member.hit_condition_sources,*hit_condition_sources_from_attack(expected,result))
    else:
        enemies = _enemy_update(state,expected.target_id,result.target_state)
        hit_sources = member.hit_condition_sources
    net_sources = (*member.net_condition_sources,*(net_condition_sources_from_attack(expected,result)
        if expected.target_id==pc_actor else ()))
    updates=dict(party=_party_update(state,pc_actor,injury=pc_injury,fate=pc_fate,
        hit_condition_sources=hit_sources,net_condition_sources=net_sources),enemies=enemies,
        pending=result.follow_ups,pending_wound=pending_wound)
    if result.stagger is not None and result.stagger.gave_ground:
        updates['pending_actor_id']=expected.target_id
    return updates


def project_pc_step(state, proof):
    if not isinstance(state,PcMeleeState):
        raise TypeError('PC transition requires complete typed owner')
    validate_pc_melee_state_shape(state)
    from towr.domain.pc_magic_weapon_models import expected_scarab_charge,project_scarab_charge,PcScarabChargeProof
    charge=expected_scarab_charge(state)
    if charge is not None or type(proof) is PcScarabChargeProof:
        return replace(state,history=(*state.history,proof),**project_scarab_charge(state,proof))
    from towr.domain.pc_terrain_models import expected_pc_terrain_traversal,PcTerrainTraversalProof,project_pc_terrain
    terrain=expected_pc_terrain_traversal(state)
    if terrain is not None or type(proof) is PcTerrainTraversalProof:
        updates=project_pc_terrain(state,proof)
        updates['magic_modifiers']=consume_magic_modifiers(state.magic_modifiers,proof)
        return replace(state,history=(*state.history,proof),**_inventory_conditions(state,updates))
    from towr.domain.pc_give_ground_models import expected_pc_give_ground,GIVE_GROUND_PROOFS,project_pc_give_ground
    ground=expected_pc_give_ground(state)
    if ground is not None or type(proof) in GIVE_GROUND_PROOFS:
        return replace(state,history=(*state.history,proof),**_inventory_conditions(state,project_pc_give_ground(state,proof)))
    from towr.domain.pc_brawn_displacement_models import expected_pc_brawn_shove,PcBrawnShoveProof,project_pc_brawn_shove
    shove=expected_pc_brawn_shove(state)
    if shove is not None or type(proof) is PcBrawnShoveProof:
        return replace(state,history=(*state.history,proof),**_inventory_conditions(state,project_pc_brawn_shove(state,proof)))
    from towr.domain.pc_broken_battlefield_models import (expected_pc_broken_battlefield_step,
        PC_BROKEN_BATTLEFIELD_PROOFS,project_pc_broken_battlefield)
    broken=expected_pc_broken_battlefield_step(state)
    if broken is not None or type(proof) in PC_BROKEN_BATTLEFIELD_PROOFS:
        return replace(state,history=(*state.history,proof),**_inventory_conditions(state,project_pc_broken_battlefield(state,proof)))
    from towr.domain.pc_shield_models import (expected_pc_shield_drop, pc_shield_drop_updates,
        PcShieldDropProof, PcShieldApproachProof, expected_pc_shield_approach,
        pc_shield_approach_updates, pc_shield_pickup_updates)
    shield_drop = expected_pc_shield_drop(state)
    if shield_drop is not None or type(proof) is PcShieldDropProof:
        _same(proof, shield_drop, 'actual Shield loss must retain its physical ground receipt')
        return replace(state, history=(*state.history, proof), **pc_shield_drop_updates(state, proof))
    lost_weapon=expected_briarroot_weapon_loss(state)
    if lost_weapon is not None:
        _same(proof,lost_weapon,'actual Wound weapon loss must retain its physical ground receipt')
        return replace(state,history=(*state.history,proof),**_inventory_conditions(state,apply_briarroot_weapon_drop(state,proof)))
    dismount=expected_pc_dismount(state)
    if (dismount is not None and expected_pc_aim_consumption(state) is None
            and expected_npc_aim_consumption(state) is None):
        if type(proof) is not PcDismountProof:
            raise ValueError('actual Prone must force a dismount before continuation')
        _same(proof,dismount,'dismount changed its actual Prone injury or source prefix')
        mounts=updated_pc_mounts(state,proof)
        enemies=state.enemies
        if proof.actor_id in state.source.enemy_activation_order:
            enemy=state.enemy(proof.actor_id)
            resilience=enemy.state.current_resilience
            from towr.domain.pc_mount_models import mount_resilience_bonus
            resilience=replace(resilience,bonus=resilience.bonus-mount_resilience_bonus(state,proof.actor_id))
            from towr.domain.armour_models import armour_is_worn
            resilience=replace(resilience,armoured=True if resilience.bonus==0
                and armour_is_worn(enemy.definition.generated_components.armour) else None)
            enemies=tuple(replace(item,state=replace(item.state,current_resilience=resilience))
                if item.state.actor_id==proof.actor_id else item for item in enemies)
        updates=dict(mounts=mounts,enemies=enemies)
        if proof.brawn_drag is not None:
            updates['pending']=state.pending[1:]
            updates['pending_actor_id']=state.pending_actor_id if updates['pending'] else None
        return replace(state,history=(*state.history,proof),**updates)
    if type(proof) is PcDismountProof:
        raise ValueError('no actual settled Prone injury permits this dismount')
    falling_ack=falling_acknowledgement_source(state)
    if falling_ack is not None or type(proof) is PcFallingAcknowledgementProof:
        if type(proof) is not PcFallingAcknowledgementProof:
            raise ValueError('falling must acknowledge its actual Wound completion before follow-ups')
        return replace(state,history=(*state.history,proof),**project_pc_falling_step(state,proof))
    falling=expected_pc_falling_request(state)
    if falling is not None or type(proof) is PcFallingProof:
        if type(proof) is not PcFallingProof:
            raise ValueError('a midair dismount must settle its actual fall before continuation')
        return replace(state,history=(*state.history,proof),**project_pc_falling_step(state,proof))
    from towr.domain.pc_weapon_area_models import (WEAPON_AREA_PROOFS,weapon_hazard_completion,
        expected_weapon_area_step,expected_ablaze_hazard,project_weapon_area_step)
    weapon_phase=weapon_hazard_completion(state) or expected_weapon_area_step(state) or expected_ablaze_hazard(state)
    if weapon_phase is not None or type(proof) in WEAPON_AREA_PROOFS:
        if type(proof) not in WEAPON_AREA_PROOFS:
            raise ValueError('actual weapon area/fire consequences must finish before continuation')
        updates=project_weapon_area_step(state,proof)
        if not updates.get('pending',state.pending) and updates.get('pending_wound',state.pending_wound) is None:
            updates['pending_actor_id']=None
        return replace(state,history=(*state.history,proof),**_inventory_conditions(state,updates))
    from towr.domain.pc_briarroot_models import PcBriarrootProof,expected_briarroot_update,apply_briarroot_update
    briarroot=expected_briarroot_update(state)
    if briarroot is not None or type(proof) is PcBriarrootProof:
        _same(proof,briarroot,'Briarroot transition must settle its actual source before continuation')
        return replace(state,history=(*state.history,proof),**apply_briarroot_update(state,proof))
    from towr.domain.pc_npc_shield_models import (PcNpcShieldDropProof,PcNpcShieldRecoverProof,
        expected_npc_shield_drop,npc_shield_drop_updates,npc_shield_pickup_updates)
    npc_shield_drop=expected_npc_shield_drop(state)
    if npc_shield_drop is not None or type(proof) is PcNpcShieldDropProof:
        _same(proof,npc_shield_drop,'NPC Shield drop must precede its actual needed Reload')
        return replace(state,history=(*state.history,proof),**npc_shield_drop_updates(state,proof))
    from towr.domain.pc_npc_weapon_inventory import PcNpcWeaponEquipProof,expected_npc_weapon_equip,apply_npc_weapon_equip
    npc_equip=expected_npc_weapon_equip(state)
    if npc_equip is not None or type(proof) is PcNpcWeaponEquipProof:
        _same(proof,npc_equip,'NPC equipment must retain the selected physical source and own turn')
        updates=weighted_nets_after_equipment(state,proof,dict(enemies=apply_npc_weapon_equip(state,proof)))
        return replace(state,history=(*state.history,proof),**updates)
    from towr.domain.pc_melee_result_models import (pc_melee_briarroot_weapon_drop,
        pc_melee_briarroot_weapon_recovery)
    weapon_drop=pc_melee_briarroot_weapon_drop(state)
    if weapon_drop is not None or type(proof) is PcBriarrootWeaponDropProof:
        _same(proof,weapon_drop,'Briarroot weapon abandonment changed its actual selected item')
        return replace(state,history=(*state.history,proof),**_inventory_conditions(state,apply_briarroot_weapon_drop(state,proof)))
    demigryph_intent=expected_pc_demigryph_intent(state)
    if demigryph_intent is not None or type(proof) is PcDemigryphIntentProof:
        _same(proof,demigryph_intent,'Demigryph must commit its actual Grim leg before the first Test')
        return replace(state,history=(*state.history,proof))
    from towr.domain.pc_generated_talents import (PcWildAttackProof,PcDefensiveStanceProof,
        expected_wild_attack,pending_wild_attack,expected_defensive_stance)
    wild = expected_wild_attack(state)
    stance = expected_defensive_stance(state)
    from towr.domain.pc_weapon_inventory import PcWeaponSwapProof,expected_pc_weapon_swap,apply_pc_weapon_swap
    swap=expected_pc_weapon_swap(state)
    if swap is not None and type(proof) is not PcWeaponSwapProof:
        raise ValueError('selected weapon swap must precede the committed action')
    if wild is not None and type(proof) is not PcWildAttackProof:
        raise ValueError('selected Wild Attack price must precede the Melee Test')
    paid=pending_wild_attack(state)
    if paid is not None:
        expected_type=(PcHelpProof if paid.intent is not None
            and paid.intent.action is CombatActionKind.HELP else PcAttackProof)
        if type(proof) is not expected_type:
            raise ValueError('paid Wild Attack must be consumed by its actual next Melee Test')
    if stance is not None and type(proof) is not PcDefensiveStanceProof:
        raise ValueError('selected Defensive Stance must replace this pending miss Staggered')
    if pc_melee_unsupported(state) is not None:
        raise ValueError('unsupported PC consequence cannot be silently continued')
    if type(proof) in MAGIC_PROOFS:
        return project_pc_magic_step(state,proof)
    if not state.pending and state.pending_wound is None and (
            state.magic_pending is not None or expected_magic_interruption(state) is not None):
        raise ValueError('mandatory magic or skipped Casting must precede ordinary continuation')
    if type(proof) is PcAimConsumptionProof:
        return project_pc_aim_step(state,proof)
    if expected_pc_aim_consumption(state) is not None:
        raise ValueError('actual Aim consumption must precede another transition')
    if type(proof) is PcNpcAimConsumptionProof:
        return project_npc_aim_step(state,proof)
    if expected_npc_aim_consumption(state) is not None:
        raise ValueError('actual NPC Aim consumption must precede another transition')
    if type(proof) in (PcAimProof,PcAimSecondActionProof):
        return project_pc_aim_step(state,proof)
    if build_pc_aim_second_action(state) is not None:
        raise ValueError('selected funded Aim Second Action must precede turn end or another transition')
    if type(proof) is PcBlunderbussNearbyProof:
        return project_pc_blunderbuss_nearby(state,proof)
    if type(proof) in BATTLEFIELD_NEARBY_PROOFS:
        return project_pc_battlefield_nearby(state,proof)
    if (current_pc_blunderbuss_wave(state) is not None and not state.pending
            and state.pending_wound is None):
        raise ValueError('nearby impacts and target lifecycles must complete before ordinary continuation')
    if (state.pending_wound is None and state.pending
            and type(state.pending[0]) is NearbyTargetsStaggerRequest):
        raise ValueError('nearby effects and acknowledgements must complete before another transition')
    demigryph_strike=build_pc_demigryph_strike(state)
    if demigryph_strike is not None and type(proof) is not PcDemigryphStrikeProof:
        raise ValueError('the committed same-action Demigryph strike must precede turn end')
    combat, scenario = state.round_state, state.source
    approach = expected_pc_npc_approach(state)
    if approach is not None and type(proof) is not PcNpcApproachProof:
        raise ValueError('NPC free approach must precede its ordinary action')
    shield_release = expected_pc_shield_release(state)
    if shield_release is not None and type(proof) is not PcShieldReleaseProof:
        raise ValueError('weapon-first shield release must precede ordinary continuation')
    net_draw = expected_pc_npc_net_draw(state)
    if net_draw is not None and type(proof) is not PcNpcNetDrawProof:
        raise ValueError('selected Net equipment draw must precede continuation')
    grudge_encounter=expected_pc_npc_grudge_encounter(state)
    if grudge_encounter is not None and type(proof) is not PcNpcGrudgeEncounterProof:
        raise ValueError('selected grudge encounters must precede combat turns')
    distraction_expiry=expected_pc_npc_distraction_expiry(state)
    if distraction_expiry is not None and type(proof) is not PcNpcDistractionExpiredProof:
        raise ValueError('confirmed focus death must expire NPC Distracted before continuing')
    blood_rage = expected_pc_npc_blood_rage(state)
    if blood_rage is not None and type(proof) is not PcNpcBloodRageProof:
        raise ValueError('selected Blood Rage must precede the reserved Attack')
    from towr.domain._pc_warped_form_projection import WARPED_PROOFS, project_warped_form_step
    from towr.domain.pc_warped_form_models import current_warped_form, expected_pc_warped_form_activation
    if type(proof) in WARPED_PROOFS:
        return project_warped_form_step(state, proof)
    if type(proof) is not PcNpcDistractionExpiredProof and not state.pending and state.pending_wound is None and (current_warped_form(state) is not None
            or expected_pc_warped_form_activation(state) is not None):
        raise ValueError('own end phase cannot skip the selected Warped Form wave')
    if state.pending_actor_id in scenario.enemy_activation_order:
        raise ValueError('wave NPC pending work requires its target-scoped acknowledgement')
    pc_actor = state.pending_actor_id
    if pc_actor is None and combat.active_turn is not None:
        actor = combat.active_turn.actor_id
        if actor in scenario.pc_activation_order:
            pc_actor = actor
        elif (combat.active_turn.action_slots
                and not combat.active_turn.action_slots[-1].executed
                and (combat.active_turn.action_slots[-1].enduring_strength is not None
                    or combat.active_turn.action_slots[-1].crown_of_antlers is not None
                    or combat.active_turn.action_slots[-1].duellist_blades is not None)):
            pc_actor = (combat.active_turn.action_slots[-1].enduring_strength
                or combat.active_turn.action_slots[-1].crown_of_antlers
                or combat.active_turn.action_slots[-1].duellist_blades).target_id
        elif (combat.active_turn.action_slots and combat.active_turn.action_slots[0].executed
                and combat.active_turn.action_slots[0].declaration.kind is CombatActionKind.ATTACK):
            # A lethal result can remove this target from live priority before
            # the attacker's turn is closed; retain the actual action target.
            pc_actor = (proof.request.target_id if type(proof) is PcDemigryphStrikeProof else
                next(p.request.target_id for p in reversed(state.history)
                    if type(p) in (PcAttackProof,PcDemigryphStrikeProof) and p.request.actor_id==actor))
        else:
            pc_actor = next((a for a in scenario.enemy_target_priority if not state.participant(a).injury.dead), None)
    member = state.participant(pc_actor) if pc_actor is not None else None
    participant = scenario.participant(pc_actor) if pc_actor is not None else None
    draw_hand = pc_backup_draw_hand(state,pc_actor) if pc_actor is not None else None
    if draw_hand is not None and not isinstance(proof,PcBackupWeaponDrawProof):
        raise ValueError('own standard turn cannot skip its required incidental backup draw')
    exit_actor = combat.active_turn.actor_id if combat.active_turn is not None else None
    exit_proof = expected_pc_npc_exit(state,exit_actor) if exit_actor is not None else None
    if exit_proof is not None and type(proof) is not PcNpcExitProof:
        raise ValueError('Broken NPC cannot skip its supported incidental exit')
    # Finish existing mandatory equipment/exit work before choosing actual
    # positioning from the resulting held weapon and hand state.
    from towr.domain.pc_melee_result_models import pc_melee_net_recovery
    recovery=pc_melee_net_recovery(state)
    incidental_net=expected_weighted_net_incidental_pickup(state) if all(item is None for item in
        (swap,shield_release,net_draw,draw_hand,exit_proof)) else None
    if incidental_net is not None and type(proof) is not PcNetIncidentalPickupProof:
        raise ValueError('selected legal incidental Net pickup must precede ordinary continuation')
    net_approach=(expected_weighted_net_approach(state,recovery.actor_id,recovery.item_id)
        if recovery is not None and recovery.requires_approach and incidental_net is None else None)
    if net_approach is not None and type(proof) is not PcNetApproachProof:
        raise ValueError('selected Net approach must precede the ordinary action')
    weapon_recovery=pc_melee_briarroot_weapon_recovery(state)
    weapon_approach=(expected_briarroot_weapon_approach(state,weapon_recovery.owner_id,weapon_recovery.weapon_id)
        if weapon_recovery is not None and all(item is None for item in
            (swap,shield_release,net_draw,draw_hand,exit_proof,recovery,incidental_net)) else None)
    if weapon_approach is not None and type(proof) is not PcBriarrootWeaponApproachProof:
        raise ValueError('owned ground weapon approach must precede the ordinary action')
    shield_approach = (expected_pc_shield_approach(state) if all(item is None for item in
        (swap,shield_release,net_draw,draw_hand,exit_proof,recovery,incidental_net,weapon_recovery)) else None)
    if shield_approach is not None and type(proof) is not PcShieldApproachProof:
        raise ValueError('owned ground Shield approach must precede the ordinary action')
    movement = (expected_pc_battlefield_move(state) if all(item is None for item in
        (swap,shield_release,net_draw,draw_hand,exit_proof,recovery,incidental_net,weapon_recovery,shield_approach)) else None)
    if movement is not None and type(proof) is not PcBattlefieldMoveProof:
        raise ValueError('selected battlefield positioning must precede the ordinary action')
    if type(proof) is PcNpcAimProof:
        return project_npc_aim_step(state,proof)

    def finish(**updates):
        updates=weighted_nets_after_equipment(state,proof,updates)
        updates=_inventory_conditions(state,updates)
        updates.setdefault('magic_modifiers',consume_magic_modifiers(state.magic_modifiers,proof))
        pending = updates.get('pending', state.pending)
        pending_wound = updates.get('pending_wound', state.pending_wound)
        if not pending and pending_wound is None:
            updates['pending_actor_id'] = None
        elif 'pending_actor_id' not in updates:
            updates['pending_actor_id'] = pc_actor
        return replace(state,history=(*state.history,proof),**updates)
    if type(proof) is PcShieldApproachProof:
        _same(proof, shield_approach, 'Shield approach changed its selected physical source')
        return finish(**pc_shield_approach_updates(state, proof))
    from towr.domain.pc_extinguish_models import PcExtinguishProof,pc_extinguish_selected,project_pc_extinguish
    if type(proof) is PcExtinguishProof:
        _ready(state)
        if not pc_extinguish_selected(state):
            raise ValueError('extinguishing changed the actual selected action')
        return finish(**project_pc_extinguish(state,proof))
    if type(proof) in NET_PROOFS:
        if type(proof) is PcNetApproachProof:
            _same(proof,net_approach,'Net approach changed its selected physical item')
        elif type(proof) is PcNetIncidentalPickupProof:
            _same(proof,incidental_net,'incidental Net pickup changed its selected physical item')
        else:
            kind=PcNetRecoverKind.RELEASE if type(proof) is PcNetReleaseProof else PcNetRecoverKind.PICKUP
            if (recovery is None or recovery.requires_approach or recovery.kind is not kind
                    or recovery.item_id!=proof.item_id):
                raise ValueError('Net Recover changed its actual selected physical item or action')
        return finish(**project_weighted_net_step(state,proof))
    if type(proof) is PcBriarrootWeaponApproachProof:
        _same(proof,weapon_approach,'weapon approach changed the actual selected owned item')
        return finish(**apply_briarroot_weapon_approach(state,proof))
    if type(proof) is PcBriarrootWeaponPickupProof:
        _ready(state)
        if (pc_melee_selected_action(state) is not CombatActionKind.RECOVER
                or weapon_recovery is None or weapon_recovery.weapon_id!=proof.pickup.weapon_id):
            raise ValueError('physical weapon pickup must retain the selected standard Recover')
        return finish(**apply_briarroot_weapon_pickup(state,proof))
    from towr.domain.pc_briarroot_models import PcBriarrootReleaseProof,apply_briarroot_release
    if type(proof) is PcBriarrootReleaseProof:
        from towr.domain.pc_melee_result_models import pc_melee_briarroot_recovery
        binding=pc_melee_briarroot_recovery(state)
        if binding is None or binding.id!=proof.binding_id:
            raise ValueError('Briarroot Recover must preserve its selected actual binding')
        return finish(**apply_briarroot_release(state,proof))
    if type(proof) is PcBattlefieldMoveProof:
        if movement is None:
            raise ValueError('no actual battlefield positioning is due')
        _same(proof,movement,'battlefield movement changed its actor, Conditions, route or spatial source')
        updates = dict(battlefield=proof.state)
        if proof.actor_id in scenario.pc_activation_order:
            moving = state.participant(proof.actor_id)
            updates['party'] = _party_update(state,proof.actor_id,
                injury=critical_for_action(moving,None))
        return finish(**updates)
    if type(proof) in BATTLEFIELD_MANOEUVRE_PROOFS:
        _ready(state)
        return finish(**project_pc_battlefield_manoeuvre(state,proof))
    if type(proof) is PcWeaponSwapProof:
        _ready(state)
        if swap is None:
            raise ValueError('no selected own-turn carried weapon swap is available')
        _same(proof,swap,'weapon swap changed its exact source or committed intent')
        updated=apply_pc_weapon_swap(state,proof)
        return finish(party=tuple(updated if member.actor_id==proof.actor_id else member for member in state.party))
    if type(proof) is PcWildAttackProof:
        replace(proof)
        if wild is None:
            raise ValueError('no Wild Attack price is available for this source/turn')
        _same(proof,wild,'Wild Attack changed its actual source actor or action')
        if proof.actor_id in scenario.pc_activation_order:
            old=state.participant(proof.actor_id).injury
            injury=replace(old,conditions=old.conditions.with_condition(Condition.STAGGERED))
            return finish(party=_party_update(state,proof.actor_id,injury=injury))
        enemy=state.enemy(proof.actor_id)
        injury=replace(enemy.state.injury,
            conditions=enemy.state.injury.conditions.with_condition(Condition.STAGGERED))
        return finish(enemies=_enemy_update(state,proof.actor_id,injury))
    if type(proof) is PcDefensiveStanceProof:
        replace(proof)
        if stance is None:
            raise ValueError('no actual new miss Staggered can be traded by Defensive Stance')
        _same(proof,stance,'Defensive Stance changed its source Attack/actors/pending effect')
        if proof.actor_id in scenario.pc_activation_order:
            old=state.participant(proof.actor_id).injury
            injury=replace(old,conditions=old.conditions.without_condition(Condition.STAGGERED))
            return finish(party=_party_update(state,proof.actor_id,injury=injury),pending=state.pending[1:])
        enemy=state.enemy(proof.actor_id)
        injury=replace(enemy.state.injury,
            conditions=enemy.state.injury.conditions.without_condition(Condition.STAGGERED))
        return finish(enemies=_enemy_update(state,proof.actor_id,injury),pending=state.pending[1:])
    if type(proof) is PcNpcApproachProof:
        replace(proof)
        if approach is None:
            raise ValueError('no NPC approach is due')
        _same(proof,approach,'approach changed its actual turn, opening or proximity source')
        return finish(approached_npc_ids=(*state.approached_npc_ids,proof.actor_id))
    if type(proof) is PcShieldReleaseProof:
        replace(proof)
        if shield_release is None:
            raise ValueError('no weapon-first shield release is due')
        _same(proof,shield_release,'shield release changed actual actor/action/hand')
        from towr.domain.pc_heavy_wound_models import add_critical,restriction_sources
        # W14 applies to an incidental drop; W15 explicitly permits dropping
        # held items, unlike the subsequent weapon swap or pickup.
        injury = add_critical(member.injury,
            restriction_sources(member.injury,WoundRestriction.NON_RECOVER_ACTION_CAUSES_CRITICAL))
        injury = critical_for_hand(replace(member,injury=injury),proof.hand)
        return finish(party=_party_update(state,proof.actor_id,injury=injury,
            shield=PcShieldState(PcShieldLocation.DROPPED,None)))
    if type(proof) is PcNpcShieldRecoverProof:
        return finish(**npc_shield_pickup_updates(state,proof))
    if type(proof) is PcNpcNetDrawProof:
        replace(proof)
        if net_draw is None:
            raise ValueError('no carried Net/Spear draw is due')
        _same(proof,net_draw,'Net draw changed its actual actor/action/profile')
        enemies = tuple(replace(e,state=replace(e.state,wields_weapon=True))
            if e.state.actor_id==proof.actor_id else e for e in state.enemies)
        return finish(enemies=enemies)
    if type(proof) is PcNpcBloodRageProof:
        replace(proof)
        if blood_rage is None:
            raise ValueError('no voluntary Blood Rage is available for this action')
        _same(proof, blood_rage, 'Blood Rage changed its actor, action or selected policy')
        enemy = state.enemy(proof.actor_id)
        injury = replace(enemy.state.injury,
            conditions=enemy.state.injury.conditions.with_condition(Condition.STAGGERED))
        return finish(enemies=_enemy_update(state, proof.actor_id, injury))
    if type(proof) is PcNpcGrudgeEncounterProof:
        replace(proof)
        _same(proof,grudge_encounter,'grudge encounter changed its complete source or source-roster order')
        if grudge_encounter is None:
            raise ValueError('no initial grudge encounter is available')
        cause=grudge_distraction_from_encounter(scenario,proof)
        enemy=state.enemy(cause.actor_id)
        injury=replace(enemy.state.injury,conditions=enemy.state.injury.conditions.with_condition(Condition.DISTRACTED))
        return finish(enemies=_enemy_update(state,cause.actor_id,injury),
            npc_distractions=ordered_npc_distractions(scenario,(*state.npc_distractions,cause)))
    if type(proof) is PcNpcDistractionExpiredProof:
        replace(proof)
        _same(proof,distraction_expiry,'NPC distraction expiry changed its actual cause or confirmed death')
        if distraction_expiry is None:
            raise ValueError('no completed focus death permits distraction expiry')
        enemy=state.enemy(proof.source.actor_id)
        injury=replace(enemy.state.injury,conditions=enemy.state.injury.conditions.without_condition(Condition.DISTRACTED))
        return finish(enemies=_enemy_update(state,enemy.state.actor_id,injury),
            npc_distractions=tuple(c for c in state.npc_distractions if c!=proof.source))
    if type(proof) is PcNpcExitProof:
        _ready(state)
        replace(proof)
        _same(proof,exit_proof,'NPC exit changed its actual own-turn movement source or result')
        if exit_proof is None:
            raise ValueError('no supported NPC exit exists at this source')
        clock = replace(combat,active_turn=None,
            excluded_turn_entity_ids=(*combat.excluded_turn_entity_ids,exit_actor))
        return finish(round_state=clock)
    if isinstance(proof,CombatTurnStartResult):
        validate_pc_melee_combat_shape(proof.state)
        replace(proof.turn)
        _same(proof.applied_rule_ids,('RULE-COMBAT-001:rounds-sides-turns',),'start-turn rule trace changed')
        _ready(state)
        if combat.active_turn is not None or combat.round_complete:
            raise ValueError('PC turn cannot start twice or after the round')
        actor = pc_melee_next_actor(state)
        expected = replace(combat,active_turn=CombatTurnState(actor,combat.participant_for(actor).side))
        _same((proof.request_id,proof.state,proof.turn),(pc_melee_action_id(state,actor)+':start',expected,expected.active_turn),
            'PC start-turn proof has another source, actor or order')
        return finish(round_state=expected)
    if isinstance(proof,CombatActionSlotResult):
        validate_pc_melee_combat_shape(proof.state)
        replace(proof.slot)
        _ready(state)
        turn = combat.active_turn
        if turn is not None and turn.action_slots:
            from towr.domain.pc_duellist_models import build_pc_duellist_second_action
            request = build_pc_npc_extra_attack_slot(state) or build_pc_duellist_second_action(state)
            if request is None:
                raise ValueError('no second Attack is granted by this source/policy')
            slot = CombatActionSlot(2,request.declaration,request.grant,request.grant_rule_id,
                enduring_strength=request.enduring_strength,crown_of_antlers=request.crown_of_antlers,
                duellist_blades=request.duellist_blades)
            expected = replace(combat,active_turn=replace(turn,action_slots=(*turn.action_slots,slot)))
            _same((proof.request_id,proof.state,proof.slot,proof.applied_rule_ids),
                (request.id,expected,slot,('RULE-COMBAT-002:action-budget',request.grant_rule_id)),
                'extra Attack reservation changed its actual typed source or target')
            return finish(round_state=expected)
        _same(proof.applied_rule_ids,('RULE-COMBAT-002:action-budget',),'reservation rule trace changed')
        if turn is None:
            raise ValueError('PC standard action must be the sole unreserved slot')
        declaration = pc_melee_action_declaration(state)
        slot = CombatActionSlot(1,declaration,ActionSlotGrant.STANDARD)
        expected = replace(combat,active_turn=replace(turn,action_slots=(slot,)))
        _same((proof.request_id,proof.state,proof.slot),(pc_melee_action_id(state,turn.actor_id)+':reserve',expected,slot),
            'PC reservation differs from the selected standard action')
        return finish(round_state=expected)
    if type(proof) is PcDemigryphStrikeProof:
        _ready(state)
        if demigryph_strike is None:
            raise ValueError('no actual unconsumed Demigryph strike is available')
        expected,protection=demigryph_strike
        from towr.domain.pc_weapon_intent_models import build_pc_explicit_attack_weapon_intent,weapon_use_hand
        _same(proof.weapon_intent,build_pc_explicit_attack_weapon_intent(state,expected.actor_id,
            expected.target_id,expected.id,mount_attack=True),'Demigryph changed its pre-roll weapon Protection intent')
        _same(proof.request,expected,'Demigryph strike changed its committed primary source or current target')
        replace(proof)
        _same(proof.protection.source_request,protection,'Demigryph Protection changed its actual equipment/Skill')
        _same(proof.protection.attack,expected.kernel_request.attack,'Demigryph Protection changed its prepared Attack')
        result=proof.resolution
        pc_test=(expected.kernel_request.attack.attacker_test if expected.actor_id==pc_actor
            else expected.kernel_request.attack.defender_test)
        effective_attack=expected.kernel_request.attack
        if pc_test is None:
            if proof.fate_decline is not None or proof.glorious is not None:
                raise ValueError('Defenceless Protection cannot invent a Demigryph Test/Fate window')
            pc_fate=member.fate
            pc_injury=member.injury
        else:
            actual=(result.attack.attacker_test if expected.actor_id==pc_actor else result.attack.defender_test)
            skill=Skill.MELEE if expected.actor_id==pc_actor else protection.selected_skill
            effective_test,pc_fate=validate_pc_test_fate(state,pc_actor,skill,pc_test,actual,
                proof.fate_decline,proof.glorious)
            effective_attack=replace(effective_attack,
                **({'attacker_test':effective_test} if expected.actor_id==pc_actor else {'defender_test':effective_test}))
            # The mount attacks without using the rider's hand. A PC defending
            # against it still incurs the real hand consequences of that Defence.
            caused=(member.injury if expected.actor_id==pc_actor else critical_for_hand(member,
                weapon_use_hand(proof.weapon_intent.protection_use)))
            pc_injury=pc_after_test(state,pc_actor,caused)
        _canonical_attack(effective_attack,result.attack)
        _ordinary_resolution(expected.kernel_request,result,state=state,action_request=expected)
        if result.request_id!=expected.kernel_request.id:
            raise ValueError('Demigryph result changed its actual K1 source')
        return finish(**_kernel_impact_updates(state,expected,result,pc_actor,pc_fate,pc_injury))
    if isinstance(proof,PcAttackProof):
        _ready(state)
        turn = combat.active_turn
        if turn is None or not turn.action_slots or turn.action_slots[-1].executed:
            raise ValueError('PC Attack must consume its unused reserved slot once')
        if (pc_melee_selected_action(state) is not CombatActionKind.ATTACK
                and current_pc_charge(state,combat.active_turn.actor_id) is None):
            raise ValueError('PC Attack cannot replace the selected Recover')
        from towr.domain.pc_weapon_intent_models import build_pc_attack_weapon_intent, weapon_use_hand
        weapon_intent = build_pc_attack_weapon_intent(state)
        _same(proof.weapon_intent,weapon_intent,'Attack changed its pre-price weapon/Protection intent')
        expected, protection = build_pc_melee_attack(state,weapon_intent=weapon_intent)
        from towr.domain.pc_mount_attack_models import pc_uses_mount_attack,build_pc_mounted_attack_intent
        mount_attack=(build_pc_mounted_attack_intent(state,expected.actor_id,expected.target_id)
            if pc_uses_mount_attack(state,expected.actor_id) else None)
        _same(proof.mount_attack,mount_attack,'mounted primary changed its actual pre-roll mount intent')
        _same(proof.npc_glorious_source, pc_bestigor_glorious_source(state, expected.actor_id),
            'Bestigor Glorious changed its actual first-Wound source or next Attack')
        _same(proof.help_applications,pc_attack_help_applications(state,expected.kernel_request.attack,
            mount_attack=mount_attack is not None),
            'Attack Help applications changed their exact intended-Test source/prefix')
        _same(proof.npc_help_applications,pc_npc_attack_help_applications(state,expected.kernel_request.attack),
            'NPC Help applications changed their exact intended-Test source/prefix')
        _same(proof.request,expected,'PC Attack request differs from the current complete source')
        replace(proof.protection)
        _same(proof.protection.source_request,protection,'PC Protection changed profile or equipment eligibility')
        _same(proof.protection.attack,expected.kernel_request.attack,'PC Protection Attack differs from execution')
        execution = proof.execution
        validate_pc_melee_combat_shape(execution.previous_state)
        validate_pc_melee_combat_shape(execution.state)
        replace(execution)
        _same((execution.request_id,execution.previous_state,execution.actor_id,execution.target_id,execution.slot_index),
            (expected.id,combat,expected.actor_id,expected.target_id,expected.slot_index),'PC Attack receipt is detached')
        result = execution.resolution
        _same(execution.applied_rule_ids,('RULE-COMBAT-004:attack-action-execution',),'Attack action rule trace changed')
        pc_test = (expected.kernel_request.attack.attacker_test if expected.actor_id == pc_actor
            else expected.kernel_request.attack.defender_test)
        if pc_test is None:
            if proof.fate_decline is not None or proof.glorious is not None:
                raise ValueError('Defenceless Protection cannot invent a Test/Fate window')
            pc_fate = member.fate
            effective_attack = expected.kernel_request.attack
        else:
            actual_test = result.attack.attacker_test if expected.actor_id == pc_actor else result.attack.defender_test
            skill = ((Skill.MELEE if mount_attack is not None else pc_attack_skill(state,pc_actor))
                if expected.actor_id == pc_actor else proof.protection.source_request.selected_skill)
            effective_test,pc_fate = validate_pc_test_fate(state,pc_actor,skill,
                pc_test,actual_test,proof.fate_decline,proof.glorious)
            effective_attack = replace(expected.kernel_request.attack,
                **({'attacker_test':effective_test} if expected.actor_id == pc_actor else {'defender_test':effective_test}))
        expected_shot = (complete_pc_ranged_shot(state,expected,
            replace(expected,kernel_request=replace(expected.kernel_request,attack=effective_attack)),execution)
            if mount_attack is None and expected.actor_id==pc_actor and pc_attack_skill(state,pc_actor) is Skill.SHOOTING else None)
        _same(proof.ranged_shot,expected_shot,'Ranged shot changed its full preparation/instance/cycle/source')
        _same(proof.nearby_snapshot,pc_blunderbuss_snapshot(state,proof),'HIT changed its committed nearby snapshot/source')
        expected_npc_shot = (complete_pc_npc_ranged_shot(state,expected,
            replace(expected,kernel_request=replace(expected.kernel_request,attack=effective_attack)),execution)
            if mount_attack is None and expected.actor_id!=pc_actor and weapon_intent.attack_skill is Skill.SHOOTING else None)
        _same(proof.npc_ranged_shot,expected_npc_shot,'NPC shot changed its full preparation/actor/instance/cycle')
        from towr.domain.pc_weapon_area_models import weapon_area_snapshot
        _same(proof.weapon_area,weapon_area_snapshot(state,expected,execution,weapon_intent.attack_use),
            'area Attack changed its frozen geometry/victims')
        _canonical_attack(effective_attack,result.attack)
        _ordinary_resolution(expected.kernel_request,result,state=state,action_request=expected)
        if result.request_id != expected.kernel_request.id:
            raise ValueError('PC Attack kernel result changed its source ID')
        if pc_test is None:
            pc_injury = member.injury
        else:
            attack_hand=weapon_use_hand(weapon_intent.attack_use)
            caused = (critical_for_action(member,CombatActionKind.ATTACK,
                used_hand=attack_hand)
                if expected.actor_id == pc_actor else critical_for_hand(member,
                    weapon_use_hand(weapon_intent.protection_use)))
            pc_injury = pc_after_test(state,pc_actor,caused)
        updates = _kernel_impact_updates(state,expected,result,pc_actor,pc_fate,pc_injury)
        updates["enemies"] = spend_pc_npc_net(state,updates["enemies"],expected)
        if expected_shot is not None:
            updates["party"] = tuple(replace_pc_member(item,ranged=expected_shot.execution.weapon_state)
                if item.actor_id==pc_actor else item for item in updates["party"])
        if expected_npc_shot is not None:
            updates['enemies']=npc_ranged_inventory_update_enemies(updates.get('enemies',state.enemies),
                expected.actor_id,expected_npc_shot.execution.weapon_state)
        net_updates=weighted_net_updates_from_attack(state,expected,execution,proof.weighted_net_landing)
        from towr.domain.pc_throwing_inventory_models import throwing_inventory_updates
        updates=throwing_inventory_updates(state,expected,execution,weapon_intent.attack_use,proof.throwing_inventory,updates)
        from towr.domain.pc_magic_weapon_models import magic_weapon_attack_updates
        updates=magic_weapon_attack_updates(state,expected,execution,weapon_intent,proof.magic_weapon,updates)
        return finish(round_state=execution.state,**updates,**net_updates)
    if isinstance(proof,PcNpcHelpProof):
        from towr.domain.automatic_help_models import expected_automatic_help_action
        _ready(state)
        turn = combat.active_turn
        if (turn is None or len(turn.action_slots)!=1 or turn.action_slots[0].executed
                or pc_melee_selected_action(state) is not CombatActionKind.HELP):
            raise ValueError('NPC Help must consume its selected unused standard slot once')
        expected = build_pc_npc_help_action(state)
        _same(proof.request,expected,'NPC Help changed its exact actor/recipient/Test/source')
        canonical = expected_automatic_help_action(expected)
        _same(proof.execution,canonical,'NPC Help changed its no-Test bonus/action receipt/clock')
        return finish(round_state=canonical.round_state)
    if isinstance(proof,PcHelpProof):
        from towr.domain.help_models import _expected_help_execution
        _ready(state)
        turn = combat.active_turn
        if (turn is None or len(turn.action_slots) != 1 or turn.action_slots[0].executed
                or pc_melee_selected_action(state) is not CombatActionKind.HELP):
            raise ValueError('Help must consume its selected unused standard slot once')
        expected = build_pc_help_action(state)
        from towr.domain.pc_help_models import pc_help_weapon_use
        from towr.domain.pc_weapon_intent_models import weapon_use_hand
        weapon_use = pc_help_weapon_use(state)
        _same(proof.weapon_use,weapon_use,'Help changed its pre-price actual weapon use')
        _same(proof.request,expected,'Help changed its current actor/ally/Test/action source')
        effective,fate = validate_pc_test_fate(state,pc_actor,expected.help_skill,
            expected.help_test,proof.execution.help_test_result,proof.fate_decline,proof.glorious)
        canonical = _expected_help_execution(replace(expected,help_test=effective),proof.execution.help_test_result)
        _same(proof.execution,canonical,'Help execution changed its exact bonus/receipt/clock/Test source')
        from towr.domain.pc_help_models import pc_help_beneficiary_weapon,pc_selected_help_policy
        _same(proof.beneficiary_weapon_item_id,pc_help_beneficiary_weapon(state,pc_selected_help_policy(state)),
            'Help changed the concrete item of its promised Test')
        from towr.domain.pc_ranged_models import complete_pc_ranged_help
        use=complete_pc_ranged_help(state,expected,replace(expected,help_test=effective),canonical)
        _same(proof.ranged_use,use,'Shooting Help changed its actual weapon/Test/bonus/Reload cycle')
        injury = pc_after_test(state,pc_actor,critical_for_action(member,CombatActionKind.HELP,
            used_hand=weapon_use_hand(weapon_use)))
        return finish(round_state=canonical.round_state,
            party=_party_update(state,pc_actor,injury=injury,fate=fate,
                **({} if use is None else {'ranged':use.weapon_state})))
    if isinstance(proof,PcWoundCompletionProof):
        pending = state.pending_wound
        if pending is None:
            raise ValueError('no pending PLAYER Wound can be completed')
        expected = build_pc_wound_completion(state)
        if expected.near_miss is None:
            _decline(state,proof.fate_decline,pc_actor,pending.request_id,'wound')
        elif proof.fate_decline is not None:
            raise ValueError('a selected Near Miss burn cannot also decline Fate')
        replace(proof.completion)
        if proof.completion.daily_registration is not None:
            replace(proof.completion.daily_registration.source_request)
            replace(proof.completion.daily_registration)
        _same(proof.completion.source_request,expected,'Near Miss completion differs from the current actual roll/history')
        if expected.near_miss is not None:
            if proof.completion.outcome is not CharacterWoundLifecycleOutcome.NEAR_MISS:
                raise ValueError('the selected strategy must negate this Wound with Near Miss')
            burn = proof.completion.fate_burn
            replace(burn)
            _same(burn.source_request,expected.near_miss,'Near Miss burn replaced its current Fate source')
            _same((burn.burn,burn.proof,burn.state,burn.effect_request),_expected_fate_burn(expected.near_miss),
                'Near Miss burn changed its canonical resource transition')
            _same((burn.request_id,burn.rule_id,burn.previous_state,burn.applied_rule_ids),
                (expected.near_miss.id,expected.near_miss.rule_id,expected.near_miss.state,
                    (FATE_SESSION_RULE_ID,FATE_BURN_RULE_ID,expected.near_miss.rule_id)),
                'Near Miss burn changed canonical provenance header types')
            application = proof.completion.near_miss_application
            replace(application.source_request)
            replace(application)
            application_source = FateNearMissApplicationRequest(expected.id+':near-miss-application',
                burn.state.session_id,pc_actor,burn,pending.source_request.wound,pending.wound_result,
                expected.consumed_near_miss_effect_ids)
            _same(application.source_request,application_source,'Near Miss application replaced its exact source')
            _same((application.request_id,application.rule_id,application.session_id,
                application.target_id,application.applied_rule_ids),
                (application_source.id,application_source.rule_id,application_source.session_id,
                application_source.target_id,_near_miss_applied_rule_ids(application_source)),
                'Near Miss application changed canonical provenance header types')
            _same((application.fate_state,application.previous_state,application.state,
                application.cancelled_wound,application.discarded_effect_request,
                application.previous_consumed_effect_ids,application.consumed_effect_ids,
                proof.completion.state,proof.completion.daily_wounds),
                (burn.state,pending.wound_result.state,pending.source_request.wound.state,
                pending.wound_result.state.wounds[-1],pending.wound_result.effect_request,
                expected.consumed_near_miss_effect_ids,(*expected.consumed_near_miss_effect_ids,burn.effect_request.id),
                _state_after_near_miss(expected),member.daily_wounds),
                'Near Miss application changed canonical cancelled Wound or retained state types')
            completed = proof.completion
            _same((completed.request_id,completed.rule_id,completed.outcome,completed.wound_result,
                completed.previous_state,completed.previous_daily_wounds,
                completed.previous_consumed_roll_ids,completed.consumed_roll_ids,
                completed.previous_consumed_near_miss_effect_ids,completed.consumed_near_miss_effect_ids,
                completed.applied_rule_ids,completed.daily_registration,completed.wound_effect),
                (expected.id,expected.rule_id,CharacterWoundLifecycleOutcome.NEAR_MISS,pending.wound_result,
                expected.current_state,expected.daily_wounds,expected.consumed_roll_ids,
                (*expected.consumed_roll_ids,pending.request_id),expected.consumed_near_miss_effect_ids,
                (*expected.consumed_near_miss_effect_ids,burn.effect_request.id),
                _completion_rule_ids(expected,burn,application,None,None),None,None),
                'Near Miss completion changed canonical provenance header/history types')
            return finish(party=_party_update(state,pc_actor,injury=proof.completion.state,
                fate=proof.completion.fate_burn.state),pending_wound=None)
        if proof.completion.outcome is not CharacterWoundLifecycleOutcome.ACCEPTED:
            raise ValueError('selected Fate refusal cannot silently negate or burn a Wound')
        _canonical_wound_effect(proof.completion)
        injury = proof.completion.state
        new_timed = tuple(PcTimedWound(e,proof.completion.request_id,
            combat.round_number+int(pc_actor in combat.completed_turn_entity_ids))
            for e in injury.active_wound_effects if isinstance(e,WoundConditionEffect)
            and e.duration is WoundEffectDuration.END_OF_NEXT_TURN and e not in member.injury.active_wound_effects)
        updated_combat = combat
        active_wizard = (combat.active_turn is not None and combat.active_turn.actor_id == pc_actor
            and scenario.participant(pc_actor).wizard is not None)
        if injury.dead and not active_wizard and pc_actor not in (*combat.completed_turn_entity_ids,*combat.excluded_turn_entity_ids):
            updated_combat = replace(combat,excluded_turn_entity_ids=(*combat.excluded_turn_entity_ids,pc_actor))
        return finish(round_state=updated_combat,
            party=_party_update(state,pc_actor,injury=injury,daily_wounds=proof.completion.daily_wounds,
                timed_wounds=(*member.timed_wounds,*new_timed)),pending_wound=None,
            pending=(*proof.completion.wound_effect.follow_ups,*state.pending))
    if isinstance(proof,PcEnduranceProof):
        if state.pending_wound is not None or not state.pending or state.pending[0] != proof.request:
            raise ValueError('Endurance is detached from the next mandatory Wound request')
        if not isinstance(proof.request,WoundEnduranceTestRequest):
            raise TypeError('Wound Endurance requires its actual request')
        expected_test = _pc_test(state,pc_actor,proof.request.test_id,Skill.ENDURANCE)
        if type(proof.result.succeeded) is not bool:
            raise TypeError('Endurance success must be a bool')
        _same(proof.test_request,expected_test,'Endurance changed the actual Toughness/Skill/modifiers')
        _,pc_fate = validate_pc_test_fate(state,pc_actor,Skill.ENDURANCE,expected_test,
            proof.test,proof.fate_decline,proof.glorious)
        injury = pc_after_test(state,pc_actor)
        more = ()
        timed = member.timed_wounds
        if not proof.test.succeeded:
            if proof.request.failure in (WoundEnduranceFailure.DROP_RANDOM_HAND_ITEM,WoundEnduranceFailure.LOSE_D10_TEETH,
                    WoundEnduranceFailure.LOSE_RANDOM_FINGER,WoundEnduranceFailure.LOSE_RANDOM_EYE):
                consequence = {WoundEnduranceFailure.DROP_RANDOM_HAND_ITEM:WoundConsequence.DROP_RANDOM_HAND_ITEM,
                    WoundEnduranceFailure.LOSE_D10_TEETH:WoundConsequence.LOSE_D10_TEETH,
                    WoundEnduranceFailure.LOSE_RANDOM_FINGER:WoundConsequence.LOSE_RANDOM_FINGER,
                    WoundEnduranceFailure.LOSE_RANDOM_EYE:WoundConsequence.LOSE_RANDOM_EYE}[proof.request.failure]
                more = (WoundConsequenceRequest(proof.request.wound_sequence,consequence,proof.request.rule_id),)
            else:
                condition = Condition.PRONE if proof.request.failure is WoundEnduranceFailure.FALL_PRONE else Condition.BLINDED
                duration = WoundEffectDuration.UNTIL_REMOVED if condition is Condition.PRONE else WoundEffectDuration.END_OF_NEXT_TURN
                effect = WoundConditionEffect(proof.request.wound_sequence,condition,duration)
                effects = injury.active_wound_effects if effect in injury.active_wound_effects else (*injury.active_wound_effects,effect)
                injury = replace(injury,active_wound_effects=effects,conditions=injury.conditions.with_condition(condition))
                if duration is WoundEffectDuration.END_OF_NEXT_TURN and not any(t.effect == effect for t in timed):
                    timed = (*timed,PcTimedWound(effect,proof.request.test_id,
                        combat.round_number+int(pc_actor in combat.completed_turn_entity_ids)))
        _same((proof.result.request,proof.result.state,proof.result.succeeded,proof.result.follow_ups),
            (proof.request,injury,proof.test.succeeded,more),'Endurance result has forged consequences')
        return finish(party=_party_update(state,pc_actor,injury=injury,timed_wounds=timed,fate=pc_fate),pending=(*more,*state.pending[1:]))
    if isinstance(proof,PcHandDropProof):
        if state.pending_wound is not None or not state.pending or state.pending[0] != proof.source:
            raise ValueError('random hand is detached from the next Wound consequence')
        if proof.source.consequence is not WoundConsequence.DROP_RANDOM_HAND_ITEM:
            raise ValueError('unsupported random-hand consequence')
        changed = body_consequence(member,PcBodyConsequenceProof(proof.source,proof.die,proof.hand))
        return finish(party=_party_update(state,pc_actor,weapon_inventory=changed.weapon_inventory,body_facts=changed.body_facts,shield=changed.shield),pending=state.pending[1:])
    if isinstance(proof,PcBodyConsequenceProof):
        if state.pending_wound is not None or not state.pending or state.pending[0] != proof.source:
            raise ValueError('anatomical consequence is detached from its actual mandatory source')
        replace(proof.source)
        changed = body_consequence(member,proof)
        return finish(party=_party_update(state,pc_actor,injury=changed.injury,weapon_inventory=changed.weapon_inventory,
            body_facts=changed.body_facts,shield=changed.shield),pending=state.pending[1:])
    if isinstance(proof,PcWoundChoiceProof):
        from towr.domain.injury_models import WoundChoice, WoundChoiceResult, WoundChoiceRequest
        request = state.pending[0] if state.pending else None
        if state.pending_wound is not None or not isinstance(request,WoundChoiceRequest):
            raise ValueError('clutch decision must follow its actual Wound choice request')
        replace(request)
        expected_choice = WoundChoice.DROP_AND_CLUTCH_STOMACH if clutch_candidates(member) else WoundChoice.BECOME_DEFENCELESS
        injury = member.injury
        more = ()
        if expected_choice is WoundChoice.DROP_AND_CLUTCH_STOMACH:
            more = (WoundConsequenceRequest(request.wound_sequence,WoundConsequence.DROP_ONE_HAND_ITEM_AND_CLUTCH_STOMACH,request.rule_id),)
        else:
            effect = WoundConditionEffect(request.wound_sequence,Condition.DEFENCELESS,WoundEffectDuration.UNTIL_REMOVED)
            injury = replace(injury,conditions=injury.conditions.with_condition(Condition.DEFENCELESS),
                active_wound_effects=(*injury.active_wound_effects,effect) if effect not in injury.active_wound_effects else injury.active_wound_effects)
        _same(proof.result,WoundChoiceResult(request,injury,expected_choice,more),'clutch choice changed its source, selected policy or consequence')
        return finish(party=_party_update(state,pc_actor,injury=injury),pending=(*more,*state.pending[1:]))
    if isinstance(proof,PcBackupWeaponDrawProof):
        _ready(state)
        replace(proof)
        if (draw_hand is None or proof.actor_id != pc_actor or proof.hand is not draw_hand
                or proof.previous_hand is not member.weapon_hand):
            raise ValueError('backup draw changed its actual own turn, policy, hand or primary source')
        from towr.domain.pc_weapon_inventory import _swapped_member
        from towr.domain.weapon_inventory_models import WeaponItemLocation
        selected=next(item for item in member.weapon_inventory.items
            if item.kind is state.source.participant(pc_actor).backup_weapon_policy.weapon
            and item.source.initial_location is WeaponItemLocation.CARRIED)
        drawn=_swapped_member(state,pc_actor,selected.id,forecast=False,stow_other_weapons=True)
        if drawn is None:
            raise ValueError('fixed backup draw has no actual carried item and legal hand')
        return finish(party=_party_update(state,pc_actor,weapon_inventory=drawn.weapon_inventory,
            injury=critical_for_incidental_hand_use(replace(member,
                injury=critical_for_incidental_hand_use(member,member.weapon_hand)),draw_hand)))
    if isinstance(proof,PcHandSwapProof):
        _ready(state)
        if combat.active_turn is None or combat.active_turn.actor_id != pc_actor or combat.active_turn.action_slots:
            raise ValueError('incidental weapon swap requires its own unreserved turn')
        if member.injury.conditions.has(Condition.DEFENCELESS):
            raise ValueError('Defenceless actor cannot perform an incidental weapon swap')
        hand = pc_preferred_weapon_hand(state,pc_actor)
        if member.weapon_hand is None or hand is None or hand is member.weapon_hand:
            raise ValueError('no supported beneficial held-weapon swap exists')
        if proof.previous_hand is not member.weapon_hand or proof.hand is not hand:
            raise ValueError('held-weapon swap changed its full current hand source')
        return finish(party=_party_update(state,pc_actor,weapon_hand=hand,
            injury=critical_for_incidental_hand_use(member,hand)))
    if type(proof) is PcFlagellantMissWoundProof:
        request = build_pc_flagellant_miss_wound(state)
        if request is None:
            raise ValueError('no pending miss permits Feel No Pain for this actor')
        replace(proof)
        actor = combat.active_turn.actor_id
        _same((proof.actor_id,proof.source,proof.previous_injury),
            (actor,state.pending[0],state.enemy(actor).state.injury),'miss Feel No Pain changed its actual actor/source')
        _same(proof.wound,expected_flagellant_miss_wound(request),
            'miss Feel No Pain detached from its complete profile Wound/ACK')
        return finish(enemies=_enemy_update(state,actor,proof.wound.state),pending=state.pending[1:])
    if isinstance(proof,PcAttackerStaggerProof):
        if build_pc_flagellant_miss_wound(state) is not None:
            raise ValueError('selected Feel No Pain must replace this miss Staggered')
        if state.pending_wound is not None or not state.pending or state.pending[0] != proof.source:
            raise ValueError('miss Staggered is detached from its pending Attack')
        actor = combat.active_turn.actor_id
        if actor == pc_actor:
            injury = replace(member.injury,conditions=member.injury.conditions.with_condition(Condition.STAGGERED))
            return finish(party=_party_update(state,pc_actor,injury=injury),pending=state.pending[1:])
        old = state.enemy(actor).state.injury
        return finish(enemies=_enemy_update(state,actor,replace(old,conditions=old.conditions.with_condition(Condition.STAGGERED))),pending=state.pending[1:])
    if isinstance(proof,PcMinionStaggerDefeatProof):
        if type(proof.source) is not MinionStaggerDefeatCause:
            raise TypeError('fleeing defeat requires its exact typed cause')
        replace(proof.source)
        if state.pending_wound is not None or not state.pending or state.pending[0] != proof.source:
            raise ValueError('fleeing defeat is detached from its pending Attack')
        attack = latest_pc_kernel_attack(state,
            kernel_request_id=proof.source.source_id.removesuffix(':minion-stagger-defeat'))
        defeat = pc_kernel_resolution(attack).minion_stagger_defeat
        if (defeat is None or defeat.cause != proof.source or attack.request.target_id != proof.source.target_id
                or state.enemy(proof.source.target_id).state.injury != defeat.state):
            raise ValueError('fleeing defeat lacks its actual Attack/target/cause')
        target = proof.source.target_id
        enemy = state.enemy(target)
        dropped = replace(enemy,state=replace(enemy.state,wields_weapon=False,available_attack_ids=()))
        updated = combat
        if target not in (*combat.completed_turn_entity_ids,*combat.excluded_turn_entity_ids):
            updated = replace(combat,excluded_turn_entity_ids=(*combat.excluded_turn_entity_ids,target))
        return finish(enemies=tuple(dropped if e.state.actor_id==target else e for e in state.enemies),
            round_state=updated,pending=state.pending[1:])
    if isinstance(proof,PcProfileWoundProof):
        if (type(proof.source) is not ProfileStateChangeRequest
                or not isinstance(proof.source.npc_type,ProfileNpcType)
                or type(proof.source.previous_wounds) is not int
                or type(proof.source.current_wounds) is not int
                or type(proof.source.defeated) is not bool):
            raise TypeError('profile Wound acknowledgement requires canonical change fields')
        if state.pending_wound is not None or not state.pending or state.pending[0] != proof.source:
            raise ValueError('defeat disposition is detached from its pending profile change')
        attack = latest_pc_kernel_attack(state)
        target = attack.request.target_id
        profile_wound=pc_kernel_resolution(attack).profile_wound
        if target == pc_actor or profile_wound is None or proof.source != profile_wound.state_change:
            raise ValueError('profile Wound acknowledgement requires its actual NPC Attack')
        if not proof.source.defeated:
            if proof.decision is not None:
                raise ValueError('a living NPC cannot receive a defeat disposition')
            enemy = state.enemy(target)
            injury = official_profile_wound_state(enemy.definition,enemy.state.injury,proof.source)
            injury = elf_merchant_profile_wound_state(enemy.definition,injury,proof.source)
            injury = pc_npc_drained_profile_wound_state(enemy.definition,injury,proof.source)
            injury = pc_npc_prone_profile_wound_state(enemy.definition,injury,proof.source)
            cause=distraction_from_profile_wound(scenario,attack,proof.source)
            distractions=state.npc_distractions
            if cause is not None:
                injury=replace(injury,conditions=injury.conditions.with_condition(Condition.DISTRACTED))
                distractions=ordered_npc_distractions(scenario,(*distractions,cause))
            return finish(enemies=_enemy_update(state,target,injury),pending=state.pending[1:],
                npc_distractions=distractions)
        if not isinstance(proof.decision,MinionDefeatDecision):
            raise TypeError('defeated NPC requires the typed caller/GM decision')
        replace(proof.decision)
        from towr.domain.pc_magic_weapon_models import pc_profile_wound_decision
        _same(proof.decision,pc_profile_wound_decision(state,attack),
            'NPC disposition differs from actual mandatory death or caller/GM decision')
        updated = combat
        if target not in (*combat.completed_turn_entity_ids,*combat.excluded_turn_entity_ids):
            updated = replace(combat,excluded_turn_entity_ids=(*combat.excluded_turn_entity_ids,target))
        return finish(round_state=updated,pending=state.pending[1:])
    if type(proof) is PcNpcRecoverProof:
        _ready(state)
        if pc_melee_selected_action(state) is not CombatActionKind.RECOVER:
            raise ValueError('NPC Recover must be selected by this source policy')
        request = build_pc_npc_recover(state)
        from towr.domain.pc_ally_recover_models import expected_pc_standard_recover
        canonical = expected_pc_standard_recover(request)
        actor = combat.active_turn.actor_id
        before = state.enemy(actor).state.injury
        expected = PcNpcRecoverProof(request,canonical,before,flagellant_recovered_injury(before))
        _same(proof,expected,'NPC Recover changed its actor, receipt, heal or source')
        return finish(round_state=canonical.round_state,enemies=_enemy_update(state,actor,expected.injury))
    if type(proof) is PcBattlefieldRecoverProof:
        _ready(state)
        if pc_melee_selected_action(state) is not CombatActionKind.RECOVER:
            raise ValueError('battlefield NPC Recover must be its actual selected action')
        request = build_pc_battlefield_npc_recover(state)
        from towr.domain.pc_ally_recover_models import expected_pc_standard_recover
        canonical = expected_pc_standard_recover(request)
        before = state.enemy(request.actor_id).state.injury
        expected = PcBattlefieldRecoverProof(request,canonical,before,
            battlefield_recovered_injury(before,canonical))
        _same(proof,expected,'battlefield NPC Recover changed its full source or standard benefits')
        return finish(round_state=canonical.round_state,
            enemies=_enemy_update(state,request.actor_id,expected.injury))
    if type(proof) is PcNpcRangedReloadProof:
        _ready(state)
        actor = combat.active_turn.actor_id
        if actor not in scenario.enemy_activation_order or pc_melee_selected_action(state) is not CombatActionKind.IMPROVISE:
            raise ValueError('NPC Reload cannot replace another actor or selected action')
        request = build_pc_npc_ranged_reload(state)
        _same(proof.request,request,'NPC Reload changed its current actor/weapon/slot/Test')
        actual = proof.result.exacting.test_result
        _test_result(request.dexterity_test,actual)
        canonical = _complete_reload_action_after_test(request,actual)
        _same(proof.result,canonical,'NPC Reload changed its actual Test/progress/receipt')
        return finish(round_state=canonical.round_state,
            enemies=npc_ranged_inventory_update(state,actor,canonical.state))
    if type(proof) is PcRangedReloadProof:
        _ready(state)
        if pc_melee_selected_action(state) is not CombatActionKind.IMPROVISE:
            raise ValueError('Reload cannot replace another selected action')
        request = build_pc_ranged_reload(state)
        _same(proof.request,request,'Reload changed its current weapon/slot/profile/source')
        actual = proof.result.exacting.test_result
        effective,fate = validate_pc_test_fate(state,pc_actor,Skill.DEXTERITY,
            request.dexterity_test,actual,proof.fate_decline,proof.glorious)
        canonical = _complete_reload_action_after_test(replace(request,dexterity_test=effective),actual)
        _same(proof.result,canonical,'Reload changed its actual Test/progress/receipt')
        injury = pc_after_test(state,pc_actor,critical_for_action(member,CombatActionKind.IMPROVISE,
            used_hand=PcTwoHandedGrip.BOTH))
        return finish(round_state=canonical.round_state,party=_party_update(state,pc_actor,
            injury=injury,fate=fate,ranged=canonical.state))
    from towr.domain.pc_scarab_recover_models import PcScarabHealingProof,project_scarab_healing
    from towr.domain.pc_hammer_recover_models import PcHammerRetrievalProof,project_pc_hammer_retrieval
    if type(proof) is PcHammerRetrievalProof:
        _ready(state)
        from towr.domain.pc_magic_weapon_models import pc_hammer_retrieval_selected
        if not pc_hammer_retrieval_selected(state):
            raise ValueError('Hammer extraction is not the selected actual Recover')
        return finish(**project_pc_hammer_retrieval(state,proof))
    if type(proof) is PcScarabHealingProof:
        _ready(state)
        if pc_melee_selected_action(state) is not CombatActionKind.RECOVER:
            raise ValueError('Scarab healing must consume its actually selected Recover')
        return finish(**project_scarab_healing(state,proof))
    if type(proof) is PcPotionRecoverProof:
        _ready(state)
        if pc_melee_selected_action(state) is not CombatActionKind.RECOVER:
            raise ValueError('potion use cannot replace the selected action')
        canonical = build_pc_potion_recover(state)
        _same(proof,canonical,'potion Recover changed its supply, source, hand, heal, enhancement or slot')
        return finish(round_state=canonical.result.round_state,
            party=tuple(canonical.after if member.actor_id == canonical.actor_id else member for member in state.party))
    if isinstance(proof,PcRecoverProof):
        _ready(state)
        if selected_pc_potion(state) is not None:
            raise ValueError('potion Recover must retain its full use and supply proof')
        if pc_melee_selected_action(state) is not CombatActionKind.RECOVER:
            raise ValueError('Recover must be the selected PC action')
        expected = build_pc_melee_recover(state)
        from towr.domain.pc_ally_recover_models import expected_pc_standard_recover,pc_after_standard_recover
        canonical = expected_pc_standard_recover(expected)
        _same(proof.result,canonical,'Recover differs from its full current choices/recipients/slot/clock')
        return finish(round_state=canonical.round_state,
            party=pc_after_standard_recover(state,expected,canonical),
            **briarroot_pc_pickup_updates(state,canonical,proof.briarroot_weapon_pickup),
            **pc_shield_pickup_updates(state,canonical,proof.pc_shield_pickup))
    if isinstance(proof,(PcTurnEndProof,PcIncapacitatedTurnEndProof)):
        from towr.domain.pc_duellist_models import build_pc_duellist_second_action
        if build_pc_npc_extra_attack_slot(state) is not None or build_pc_duellist_second_action(state) is not None:
            raise ValueError('selected NPC policy must execute its available second Attack before TurnEnd')
        from towr.domain.pc_heavy_turn_projection import project_heavy_turn_end
        return project_heavy_turn_end(state,proof,finish)
    if isinstance(proof,CombatRoundAdvanceResult):
        validate_pc_melee_combat_shape(proof.state)
        _same(proof.applied_rule_ids,('RULE-COMBAT-001:rounds-sides-turns',),'round-advance rule trace changed')
        _ready(state)
        if not combat.round_complete or combat.round_number >= scenario.max_rounds:
            raise ValueError('PC round cannot advance before completion or beyond its budget')
        participants = pc_melee_round_participants(state)
        expected = CombatRoundState(combat.round_number+1,participants)
        _same((proof.request_id,proof.state),(f'{scenario.id}:r{combat.round_number}:advance',expected),
            'PC round advance changed its live participants, order or clock')
        from towr.rules.spatial_resolution import start_next_spatial_round
        battlefield = (None if state.battlefield is None else
            replace(state.battlefield,spatial=start_next_spatial_round(state.battlefield.spatial)))
        return finish(round_state=expected,battlefield=battlefield)
    raise TypeError('unsupported PC journal proof type')
