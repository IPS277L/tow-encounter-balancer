"""One bounded, continuous PLAYER/Minion melee through K1 (ADR-0065)."""
from __future__ import annotations

from dataclasses import replace
from towr.domain.pc_magic_models import (complete_pc_casting,build_pc_casting_request,guarded_casting_test,
    expected_magic_interruption,pc_magic_unsupported,PcMiscastRollProof,PcMagicCleanupProof,build_magic_effect)
from towr.rules.miscast_resolution import resolve_miscast_roll
from towr.domain.pc_potion_models import selected_pc_potion, build_pc_potion_recover

from towr.domain.pc_melee_models import PcWeaponHand
from towr.domain.pc_mount_models import expected_pc_dismount
from towr.domain.pc_weighted_net_models import (PcNetReleaseProof,PcNetPickupProof,PcNetRecoverKind,
    complete_weighted_net_throw,complete_weighted_net_equipment_proof,
    expected_weighted_net_incidental_pickup,expected_weighted_net_approach,
    build_weighted_net_release,build_weighted_net_pickup,weighted_net_item,
    weighted_net_release_item,weighted_net_pickup_item)
from towr.domain.recover_models import _expected_recover_execution
from towr.rules.recover_resolution import _complete_condition_removal_after_test
from towr.domain.pc_net_models import expected_pc_npc_net_draw
from towr.domain.pc_shield_models import expected_pc_shield_release
from towr.domain.pc_weapon_inventory import expected_pc_weapon_swap
from towr.domain.pc_ranged_models import PcRangedReloadProof,build_pc_ranged_reload,complete_pc_ranged_shot
from towr.domain.pc_aim_models import (PcAimProof,PcAimSecondActionProof,build_pc_aim,
    expected_pc_aim_consumption,build_pc_aim_second_action)
from towr.domain.pc_npc_aim_models import (PcNpcAimProof,build_npc_aim,expected_npc_aim_consumption)
from towr.rules.aim_resolution import execute_aim_action
from towr.rules.fate_resolution import spend_fate_for_second_action
from towr.domain.pc_blunderbuss_models import PcBlunderbussNearbyProof, build_pc_blunderbuss_nearby, PcNearbyDecisions, pc_blunderbuss_snapshot
from towr.domain.pc_blunderbuss_models import (PcBlunderbussTargetProof,PcBlunderbussProfileProof,
    PcBlunderbussEndProof,current_pc_blunderbuss_wave,next_pc_blunderbuss_target,
    pc_blunderbuss_pending_npc_target,pc_blunderbuss_profile_decision)
from towr.domain.resolution_models import NearbyTargetsStaggerRequest
from towr.rules.secondary_target_resolution import resolve_nearby_targets_stagger
from towr.domain.pc_short_opening_models import expected_pc_npc_approach
from towr.domain.pc_battlefield_movement_models import (
    PcBattlefieldRecoverProof, expected_pc_battlefield_move,
    pc_battlefield_npc_recover_selected, build_pc_battlefield_npc_recover,
    battlefield_recovered_injury,
)
from towr.domain.pc_battlefield_manoeuvre_models import (
    PcBattlefieldChargeProof,PcBattlefieldRunProof,proposed_pc_battlefield_manoeuvre,
    current_pc_charge,build_pc_battlefield_charge,build_pc_battlefield_run,
    build_pc_battlefield_run_extension,battlefield_after_manoeuvre,
)
from towr.rules.charge_action_execution import _complete_charge_movement_after_test
from towr.rules.run_action_execution import execute_run_action,_complete_run_athletics_extension_after_test
from towr.domain.pc_npc_ranged_models import (
    PcNpcRangedReloadProof, build_pc_npc_ranged_reload, complete_pc_npc_ranged_shot, pc_npc_ranged_weapon,
)
from towr.domain.reload_models import _complete_reload_action_after_test
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcAttackerStaggerProof, PcEnduranceProof, PcFateDecline,
    PcHandDropProof, PcMeleeOutcome, PcMeleeScenarioResult, PcMeleeState, PcMeleeStep,
    PcProfileWoundProof, PcMinionStaggerDefeatProof, PcRecoverProof, PcTurnEndProof, PcWoundCompletionProof,
    PcBodyConsequenceProof, PcWoundChoiceProof, PcHandSwapProof, PcBackupWeaponDrawProof, PcCriticalProof, PcIncapacitatedTurnEndProof, PcHelpProof, PcNpcHelpProof,
    build_pc_melee_attack, build_pc_melee_recover, build_pc_wound_completion, initial_pc_melee_state, pc_after_test,pc_melee_action_declaration,pc_attack_skill,
    pc_melee_action_id, pc_melee_next_actor, pc_melee_selected_action, pc_melee_unsupported,pc_is_casting_action,
    project_pc_melee_step, pc_melee_round_participants, validate_pc_melee_state_shape,
    validate_pc_melee_source_types, _pc_test,
    pc_melee_net_recovery,
)
from towr.domain.condition_models import StaggerChoice, Condition
from towr.domain.pc_backup_weapon_models import pc_backup_draw_hand, pc_preferred_weapon_hand
from towr.domain.pc_npc_exit_models import PcNpcExitProof,build_pc_npc_exit
from towr.rules.free_movement_resolution import resolve_free_movement
from towr.domain.pc_fate_test_models import build_pc_glorious_spend
from towr.domain.pc_help_models import build_pc_help_action, pc_attack_help_applications
from towr.domain.pc_npc_help_models import build_pc_npc_help_action,pc_npc_attack_help_applications
from towr.rules.automatic_help_resolution import execute_automatic_help_action
from towr.rules.help_resolution import _complete_help_action
from towr.domain._pc_heavy_wound_projection import consequence_sides, clutch_candidates
from towr.domain.critical_injury_models import CriticalInjuryTestRequest
from towr.rules.critical_injury_resolution import resolve_critical_injury_test
from towr.domain.injury_models import WoundConsequenceRequest, WoundEnduranceTestRequest, ProfileStateChangeRequest, WoundChoiceRequest, WoundChoice, WoundConsequence
from towr.domain.injury_models import MinionStaggerDefeatCause
from towr.domain.resolution_models import AttackerStaggerRequest
from towr.domain.test_models import Skill
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundAdvanceRequest, CombatTurnEndRequest, CombatTurnEndResult, CombatTurnParticipant, CombatTurnStartRequest, CombatSide,
    ManoeuvreKind,
)
from towr.rules.attack_action_execution import _complete_attack_action, _validate_attack_action_slot
from towr.rules.attack_resolution import _resolve_attack_after_tests
from towr.rules.dice import RandomSource
from towr.rules.kernel import _resolve_kernel_attack_after_test
from towr.rules.protection_preparation import prepare_protection
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.test_resolution import KeepAllFailures, RerollAllFailures, resolve_test, roll_test_initial, complete_test
from towr.rules.fate_resolution import spend_fate_for_glorious
from towr.rules.turn_resolution import start_combat_turn, reserve_combat_action_slot, end_combat_turn, advance_combat_round
from towr.rules.wound_effect_resolution import resolve_wound_endurance_test, resolve_wound_choice
from towr.rules.wound_lifecycle_resolution import complete_character_wound_lifecycle
from towr.domain.pc_npc_extra_attack_models import build_pc_npc_extra_attack_slot
from towr.domain.pc_npc_distraction_models import expected_pc_npc_distraction_expiry
from towr.domain.pc_npc_grudge_models import expected_pc_npc_grudge_encounter
from towr.domain.pc_bestigor_models import expected_pc_npc_blood_rage, pc_bestigor_glorious_source
from towr.domain.pc_generated_talents import (expected_wild_attack,pending_wild_attack,
    expected_defensive_stance)
from towr.domain.pc_flagellant_models import (PcNpcRecoverProof, PcFlagellantMissWoundProof,
    build_pc_npc_recover, flagellant_recovered_injury, build_pc_flagellant_miss_wound)
from towr.domain.pc_warped_form_models import (
    PcWarpedFormActivationProof, PcWarpedFormTargetProof, PcWarpedFormProfileProof,
    PcWarpedFormMinionDefeatProof, PcWarpedFormEndProof, current_warped_form,
    expected_pc_warped_form_activation, next_warped_form_target, WarpedFormDecisions,
)
from towr.rules.stagger_impact_resolution import resolve_stagger_impact
from towr.rules.injury_resolution import resolve_profile_wound


class _Decisions(KeepAllFailures):
    def choose_repeated_stagger(self, *, request, allowed_choices):
        if StaggerChoice.SUFFER_WOUND not in allowed_choices:
            raise ValueError('selected Wound strategy is unavailable')
        return StaggerChoice.SUFFER_WOUND

    def choose_wound_negation(self, *, request, table_roll, options):
        if options:
            raise ValueError('additional Wound negation is outside this PC scenario')
        return None

    def choose_monstrosity_impact(self, **kwargs):
        raise ValueError('Monstrosities are outside this PC scenario')


def _decline(state, actor_id, source_id, window):
    return PcFateDecline(actor_id,source_id,window,state.source.participant(actor_id).fate_policy)


def _resolve_pc_test(state, actor_id, skill, request, rng, decisions):
    wild = pending_wild_attack(state)
    if skill is Skill.MELEE and wild is not None and wild.actor_id == actor_id:
        decisions = RerollAllFailures()
    initial = roll_test_initial(request,rng)
    selected = build_pc_glorious_spend(state,actor_id,skill,initial)
    if selected is None:
        return complete_test(initial,rng,decisions=decisions),_decline(state,actor_id,request.id,'test'),None,request
    spend = spend_fate_for_glorious(selected)
    return complete_test(initial,rng,request=spend.test,decisions=RerollAllFailures()),None,spend,spend.test


def apply_pc_melee_step(current: PcMeleeState, step: PcMeleeStep) -> PcMeleeState:
    """Apply only a fully source-bound, canonical journal step, once."""
    if not isinstance(current,PcMeleeState) or not isinstance(step,PcMeleeStep):
        raise TypeError('PC application requires typed current owner and step')
    validate_pc_melee_state_shape(current)
    validate_pc_melee_state_shape(step.source)
    validate_pc_melee_state_shape(step.state)
    # Reconstruct the actual prefix. Equal injury/clock snapshots alone do not
    # establish membership in this encounter's history.
    expected = initial_pc_melee_state(current.source)
    for proof in current.history:
        expected = project_pc_melee_step(expected,proof)
    if current != expected or step.source != current:
        raise ValueError('PC step is replayed, detached or belongs to a stale owner')
    validate_pc_melee_source_types(step.source,expected)
    projected = project_pc_melee_step(current,step.proof)
    if step.state != projected:
        raise ValueError('PC step state has been forged')
    validate_pc_melee_source_types(step.state,projected)
    return projected


def run_pc_melee_scenario(scenario, rng: RandomSource) -> PcMeleeScenarioResult:
    """Run the explicit policy until a real terminal outcome, budget or stop."""
    state = initial_pc_melee_state(scenario)
    steps = []
    decisions = _Decisions()

    def consume(proof):
        nonlocal state
        proof=complete_weighted_net_equipment_proof(state,proof)
        step = PcMeleeStep(state,proof)
        steps.append(step)
        state = step.state

    def finish_turn():
        activation = expected_pc_warped_form_activation(state)
        if activation is not None:
            consume(activation)
            return
        combat = state.round_state
        actor = combat.active_turn.actor_id
        action_id = pc_melee_action_id(state,actor)
        is_pc = actor in scenario.pc_activation_order
        critical = None
        dead = is_pc and state.participant(actor).injury.dead
        if is_pc and not dead and state.participant(actor).injury.conditions.has(Condition.CRITICALLY_INJURED):
            test_request = _pc_test(state,actor,action_id+':critical:endurance',Skill.ENDURANCE)
            test,decline,glorious,_ = _resolve_pc_test(state,actor,Skill.ENDURANCE,test_request,rng,decisions)
            request = CriticalInjuryTestRequest(action_id+':critical',actor,pc_after_test(state,actor),test_request.id)
            critical = PcCriticalProof(test_request,resolve_critical_injury_test(request,test),decline,glorious)
        if not combat.active_turn.action_slots:
            clock = replace(combat,active_turn=None,
                completed_turn_entity_ids=(*combat.completed_turn_entity_ids,actor))
            result = CombatTurnEndResult(action_id+':end',clock,combat.active_turn,clock.next_side,clock.round_complete,
                ('RULE-COMBAT-001:rounds-sides-turns','RULE-HEALTH-008:defenceless-turn'))
            consume(PcIncapacitatedTurnEndProof(result,critical))
        else:
            decline = _decline(state,actor,action_id+':end','action') if is_pc and not dead else None
            result = end_combat_turn(CombatTurnEndRequest(action_id+':end',combat,actor))
            consume(PcTurnEndProof(result,decline,critical))

    while True:
        consumption = expected_pc_aim_consumption(state)
        if consumption is None:
            consumption = expected_npc_aim_consumption(state)
        if consumption is not None:
            consume(consumption)
            continue
        dismount=expected_pc_dismount(state)
        if dismount is not None:
            consume(dismount)
            continue
        magic_stop = pc_magic_unsupported(state)
        if magic_stop is not None:
            return PcMeleeScenarioResult(scenario,tuple(steps),PcMeleeOutcome.UNSUPPORTED_PATH,magic_stop)
        interruption = expected_magic_interruption(state)
        if interruption is not None:
            consume(interruption)
            continue
        if state.magic_pending is not None and not state.pending and state.pending_wound is None:
            phase = state.magic_pending
            if phase.tasks:
                consume(build_magic_effect(state,rng))
            elif phase.miscast_request is not None:
                consume(PcMiscastRollProof(phase.miscast_request,
                    resolve_miscast_roll(phase.miscast_request,state.participant(phase.caster_id).magic,rng)))
            else:
                consume(PcMagicCleanupProof(phase.source_id))
            continue
        grudge_encounter=expected_pc_npc_grudge_encounter(state)
        if grudge_encounter is not None:
            consume(grudge_encounter)
            continue
        unsupported = pc_melee_unsupported(state)
        if unsupported is not None:
            return PcMeleeScenarioResult(scenario,tuple(steps),PcMeleeOutcome.UNSUPPORTED_PATH,unsupported)
        # The raw PLAYER injury can already have dead=True. Never decide defeat
        # while the actual Near Miss lifecycle window remains unresolved.
        if state.pending_wound is not None:
            pending = state.pending_wound
            pc_actor = state.pending_actor_id
            request = build_pc_wound_completion(state)
            decline = _decline(state,pc_actor,pending.request_id,'wound') if request.near_miss is None else None
            completion = complete_character_wound_lifecycle(request)
            consume(PcWoundCompletionProof(completion,decline))
            continue
        if state.pending:
            pending = state.pending[0]
            pc_actor = state.pending_actor_id
            blunderbuss=current_pc_blunderbuss_wave(state)
            nearby_target=pc_blunderbuss_pending_npc_target(state)
            if nearby_target is not None:
                if type(pending) is not ProfileStateChangeRequest:
                    raise ValueError('unexpected ordinary nearby Minion continuation')
                consume(PcBlunderbussProfileProof(blunderbuss.request.kernel_request.id,pc_actor,
                    pending,pc_blunderbuss_profile_decision(state,nearby_target)))
                continue
            wave = current_warped_form(state)
            if wave is not None and pc_actor in scenario.enemy_activation_order:
                if type(pending) is MinionStaggerDefeatCause:
                    consume(PcWarpedFormMinionDefeatProof(wave.activation_id, pc_actor))
                elif type(pending) is ProfileStateChangeRequest:
                    policy = next(p for p in scenario.npc_warped_form_policies if p.actor_id == wave.actor_id)
                    decision = (next(d for d in policy.npc_defeat_decisions if d.target_id == pc_actor)
                        if pending.defeated else None)
                    consume(PcWarpedFormProfileProof(wave.activation_id, pc_actor, pending, decision))
                else:
                    raise ValueError('unexpected wave NPC continuation')
                continue
            if type(pending) is NearbyTargetsStaggerRequest:
                if blunderbuss is not None:
                    target=next_pc_blunderbuss_target(state)
                    if target is None:
                        consume(PcBlunderbussEndProof(blunderbuss.request.kernel_request.id))
                    else:
                        consume(PcBlunderbussTargetProof(blunderbuss.request.kernel_request.id,
                            target,resolve_stagger_impact(target,rng,decisions=WarpedFormDecisions())))
                    continue
                request = build_pc_blunderbuss_nearby(state)
                result = resolve_nearby_targets_stagger(request,rng,decisions=PcNearbyDecisions())
                attack = next(p for p in reversed(state.history) if type(p) is PcAttackProof
                    and p.request.kernel_request.id == request.source.resolution_id)
                participant = scenario.participant(attack.request.actor_id)
                dispositions = tuple(participant.defeat_decision(target.target_id) for target in result.targets
                    if target.impact.profile_wound is not None and target.impact.profile_wound.state_change.defeated)
                consume(PcBlunderbussNearbyProof(request,result,dispositions))
            elif isinstance(pending,WoundEnduranceTestRequest):
                test_request = _pc_test(state,pc_actor,pending.test_id,Skill.ENDURANCE)
                test,decline,glorious,_ = _resolve_pc_test(state,pc_actor,Skill.ENDURANCE,test_request,rng,decisions)
                result = resolve_wound_endurance_test(pending,pc_after_test(state,pc_actor),test)
                consume(PcEnduranceProof(pending,test_request,test,result,decline,glorious))
            elif isinstance(pending,WoundChoiceRequest):
                choice = WoundChoice.DROP_AND_CLUTCH_STOMACH if clutch_candidates(state.participant(pc_actor)) else WoundChoice.BECOME_DEFENCELESS
                consume(PcWoundChoiceProof(resolve_wound_choice(pending,state.participant(pc_actor).injury,choice)))
            elif isinstance(pending,WoundConsequenceRequest):
                member = state.participant(pc_actor)
                if pending.consequence is WoundConsequence.LOSE_D10_TEETH:
                    die = rng.randint(1,10)
                    consume(PcBodyConsequenceProof(pending,die,None,die))
                elif pending.consequence is WoundConsequence.DROP_ONE_HAND_ITEM_AND_CLUTCH_STOMACH:
                    candidates = clutch_candidates(member)
                    hand = next((side for side in candidates if side is not member.weapon_hand),candidates[0])
                    consume(PcBodyConsequenceProof(pending,None,hand))
                else:
                    sides = consequence_sides(member,pending)
                    die = rng.randint(1,10) if len(sides) == 2 else None
                    hand = (PcWeaponHand.LEFT if die <= 5 else PcWeaponHand.RIGHT) if die is not None else (sides[0] if sides else None)
                    if pending.consequence is WoundConsequence.DROP_RANDOM_HAND_ITEM and die is not None:
                        consume(PcHandDropProof(pending,die,hand))
                    else:
                        consume(PcBodyConsequenceProof(pending,die,hand))
            elif isinstance(pending,AttackerStaggerRequest):
                stance = expected_defensive_stance(state)
                if stance is not None:
                    consume(stance)
                    continue
                replacement = build_pc_flagellant_miss_wound(state)
                if replacement is None:
                    consume(PcAttackerStaggerProof(pending))
                else:
                    actor = state.round_state.active_turn.actor_id
                    consume(PcFlagellantMissWoundProof(actor,pending,replacement.state,resolve_profile_wound(replacement)))
            elif type(pending) is MinionStaggerDefeatCause:
                consume(PcMinionStaggerDefeatProof(pending))
            elif isinstance(pending,ProfileStateChangeRequest):
                attack = next(p for p in reversed(state.history) if isinstance(p,PcAttackProof))
                decision = (scenario.participant(attack.request.actor_id).defeat_decision(attack.request.target_id)
                    if pending.defeated else None)
                consume(PcProfileWoundProof(pending,decision))
            else:
                raise ValueError('unexpected mandatory PC continuation')
            continue
        blunderbuss=current_pc_blunderbuss_wave(state)
        if blunderbuss is not None:
            target=next_pc_blunderbuss_target(state)
            if target is None:
                consume(PcBlunderbussEndProof(blunderbuss.request.kernel_request.id))
            else:
                consume(PcBlunderbussTargetProof(blunderbuss.request.kernel_request.id,
                    target,resolve_stagger_impact(target,rng,decisions=WarpedFormDecisions())))
            continue
        distraction_expiry=expected_pc_npc_distraction_expiry(state)
        if distraction_expiry is not None:
            consume(distraction_expiry)
            continue
        activation = expected_pc_warped_form_activation(state)
        if activation is not None:
            consume(activation)
            continue
        wave = current_warped_form(state)
        if wave is not None:
            target = next_warped_form_target(state)
            if target is None:
                consume(PcWarpedFormEndProof(wave.activation_id))
            else:
                consume(PcWarpedFormTargetProof(wave.activation_id, target,
                    resolve_stagger_impact(target, rng, decisions=WarpedFormDecisions())))
            continue
        turn = state.round_state.active_turn
        if (turn is not None and turn.actor_id in {p.actor_id for p in scenario.npc_warped_form_policies}
                and turn.action_slots and all(s.executed for s in turn.action_slots)):
            finish_turn()
            continue
        turn = state.round_state.active_turn
        if (turn is not None and turn.actor_id in scenario.enemy_activation_order
                and state.enemy(turn.actor_id).definition.id=='pc-book-npc:great_stag'
                and turn.action_slots and all(slot.executed for slot in turn.action_slots)):
            extra = build_pc_npc_extra_attack_slot(state)
            if extra is not None:
                consume(reserve_combat_action_slot(extra))
            else:
                finish_turn()
            continue
        turn = state.round_state.active_turn
        if (turn is not None and turn.actor_id in scenario.pc_activation_order
                and scenario.participant(turn.actor_id).wizard is not None
                and state.participant(turn.actor_id).injury.dead):
            finish_turn()
            continue
        if not state.live_party:
            return PcMeleeScenarioResult(scenario,tuple(steps),PcMeleeOutcome.PARTY_DEFEATED)
        if not state.live_enemies:
            turn = state.round_state.active_turn
            if (turn is not None and turn.actor_id in scenario.pc_activation_order
                    and state.participant(turn.actor_id).injury.conditions.has(Condition.CRITICALLY_INJURED)):
                finish_turn()
                continue
            return PcMeleeScenarioResult(scenario,tuple(steps),PcMeleeOutcome.OBJECTIVE_ACHIEVED)
        combat = state.round_state
        if combat.active_turn is None:
            if combat.round_complete:
                if combat.round_number == scenario.max_rounds:
                    return PcMeleeScenarioResult(scenario,tuple(steps),PcMeleeOutcome.ROUND_LIMIT)
                participants = pc_melee_round_participants(state)
                result = advance_combat_round(CombatRoundAdvanceRequest(
                    f'{scenario.id}:r{combat.round_number}:advance',combat,participants))
                consume(result)
            else:
                actor = pc_melee_next_actor(state)
                consume(start_combat_turn(CombatTurnStartRequest(pc_melee_action_id(state,actor)+':start',combat,actor)))
            continue
        actor = combat.active_turn.actor_id
        action_id = pc_melee_action_id(state,actor)
        if not combat.active_turn.action_slots:
            exit_request = build_pc_npc_exit(state,actor)
            if exit_request is not None:
                consume(PcNpcExitProof(exit_request,resolve_free_movement(exit_request)))
                continue
            approach = expected_pc_npc_approach(state)
            if approach is not None:
                consume(approach)
                continue
            if actor in scenario.pc_activation_order:
                member = state.participant(actor)
                if member.injury.conditions.has(Condition.DEFENCELESS) and selected_pc_potion(state) is None:
                    finish_turn()
                    continue
                shield_release = expected_pc_shield_release(state)
                if shield_release is not None:
                    consume(shield_release)
                    continue
                swap=expected_pc_weapon_swap(state)
                if swap is not None:
                    consume(swap)
                    continue
                casting = pc_is_casting_action(state)
                draw_hand = pc_backup_draw_hand(state,actor) if selected_pc_potion(state) is None and not casting else None
                if draw_hand is not None:
                    consume(PcBackupWeaponDrawProof(actor,member.weapon_hand,draw_hand))
                    continue
                hand = pc_preferred_weapon_hand(state,actor) if selected_pc_potion(state) is None and not casting else None
                if member.weapon_hand is not None and hand is not None and hand is not member.weapon_hand:
                    consume(PcHandSwapProof(member.weapon_hand,hand))
                    continue
            # Position from actual held equipment after its mandatory
            # draw/swap/regrip receipts, before reserving the ordinary action.
            incidental_net=expected_weighted_net_incidental_pickup(state)
            if incidental_net is not None:
                consume(incidental_net)
                continue
            recovery=pc_melee_net_recovery(state)
            if recovery is not None and recovery.requires_approach:
                approach=expected_weighted_net_approach(state,actor,recovery.item_id)
                if approach is not None:
                    consume(approach)
                    continue
            movement = expected_pc_battlefield_move(state) if recovery is None else None
            if movement is not None:
                consume(movement)
                continue
            consume(reserve_combat_action_slot(CombatActionSlotRequest(action_id+':reserve',combat,actor,
                pc_melee_action_declaration(state),ActionSlotGrant.STANDARD)))
            continue
        if not combat.active_turn.action_slots[-1].executed:
            wild=expected_wild_attack(state)
            if wild is not None:
                consume(wild)
                continue
            if (pc_melee_selected_action(state) is CombatActionKind.MANOEUVRE
                    and current_pc_charge(state,actor) is None):
                proposal=proposed_pc_battlefield_manoeuvre(state)
                if proposal is None:
                    raise ValueError('reserved Manoeuvre lost its actual positioning proposal')
                target=proposal.target_id
                previous=state.battlefield
                decline=glorious=None
                if proposal.kind is ManoeuvreKind.CHARGE:
                    request=build_pc_battlefield_charge(state,target)
                    effective=request.athletics_test
                    test=None
                    if effective is not None:
                        if actor in scenario.pc_activation_order:
                            test,decline,glorious,effective=_resolve_pc_test(state,actor,Skill.ATHLETICS,
                                request.athletics_test,rng,decisions)
                        else:
                            test=resolve_test(effective,rng,decisions=decisions)
                    result=_complete_charge_movement_after_test(replace(request,athletics_test=effective),test)
                    consume(PcBattlefieldChargeProof(request,result,previous,
                        battlefield_after_manoeuvre(state,result,target),decline,glorious))
                else:
                    request=build_pc_battlefield_run(state,target)
                    result=execute_run_action(request)
                    extension=build_pc_battlefield_run_extension(state,result,target)
                    completed=None
                    if extension is not None:
                        effective=extension.athletics_test
                        if actor in scenario.pc_activation_order:
                            test,decline,glorious,effective=_resolve_pc_test(state,actor,Skill.ATHLETICS,
                                extension.athletics_test,rng,decisions)
                        else:
                            test=resolve_test(effective,rng,decisions=decisions)
                        completed=_complete_run_athletics_extension_after_test(
                            replace(extension,athletics_test=effective),test)
                    consume(PcBattlefieldRunProof(request,result,previous,
                        battlefield_after_manoeuvre(state,result,target,extension_result=completed),
                        extension_request=extension,extension_result=completed,
                        fate_decline=decline,glorious=glorious,target_id=target))
                continue
            if pc_is_casting_action(state):
                request = build_pc_casting_request(state)
                test,decline,glorious,_ = _resolve_pc_test(state,actor,Skill.WILLPOWER,
                    guarded_casting_test(request.casting_request),rng,decisions)
                consume(complete_pc_casting(state,test,decline,glorious))
            elif pc_melee_selected_action(state) is CombatActionKind.AIM:
                if actor in scenario.enemy_activation_order:
                    request=build_npc_aim(state)
                    consume(PcNpcAimProof(request,execute_aim_action(request,rng,decisions=decisions)))
                else:
                    request = build_pc_aim(state)
                    consume(PcAimProof(request,execute_aim_action(request,rng,decisions=decisions),
                        _decline(state,actor,request.awareness_test.id,'test')))
            elif pc_melee_selected_action(state) is CombatActionKind.IMPROVISE:
                if actor in scenario.enemy_activation_order:
                    request = build_pc_npc_ranged_reload(state)
                    test = resolve_test(request.dexterity_test,rng,decisions=decisions)
                    consume(PcNpcRangedReloadProof(request,_complete_reload_action_after_test(request,test)))
                else:
                    request = build_pc_ranged_reload(state)
                    test,decline,glorious,effective = _resolve_pc_test(state,actor,Skill.DEXTERITY,
                        request.dexterity_test,rng,decisions)
                    result = _complete_reload_action_after_test(replace(request,dexterity_test=effective),test)
                    consume(PcRangedReloadProof(request,result,decline,glorious))
            elif pc_melee_selected_action(state) is CombatActionKind.RECOVER:
                recovery=pc_melee_net_recovery(state)
                if recovery is not None and not recovery.requires_approach:
                    item=weighted_net_item(state,recovery.item_id)
                    if recovery.kind is PcNetRecoverKind.RELEASE:
                        request=build_weighted_net_release(state,recovery.target_id,recovery.item_id)
                        decline=glorious=None
                        effective=request.choice.test
                        if actor in scenario.pc_activation_order:
                            test,decline,glorious,effective=_resolve_pc_test(state,actor,Skill.BRAWN,
                                request.choice.test,rng,decisions)
                        else:
                            test=resolve_test(effective,rng,decisions=decisions)
                        choice=replace(request.choice,test=effective)
                        result=_expected_recover_execution(replace(request,choice=choice),
                            _complete_condition_removal_after_test(choice,test))
                        after,battlefield=weighted_net_release_item(state,item.item_id,result)
                        consume(PcNetReleaseProof(request,result,item.item_id,item,after,
                            state.battlefield,battlefield,decline,glorious))
                    else:
                        request=build_weighted_net_pickup(state,recovery.item_id)
                        result=execute_recover_action(request,rng,decisions=decisions)
                        after,battlefield=weighted_net_pickup_item(state,item.item_id)
                        consume(PcNetPickupProof(request,result,item.item_id,item,after,
                            state.battlefield,battlefield))
                    continue
                if selected_pc_potion(state) is not None:
                    consume(build_pc_potion_recover(state))
                    continue
                if actor in scenario.enemy_activation_order:
                    if pc_battlefield_npc_recover_selected(state):
                        request = build_pc_battlefield_npc_recover(state)
                        before = state.enemy(actor).state.injury
                        actual = execute_recover_action(request,rng)
                        consume(PcBattlefieldRecoverProof(request,actual,before,
                            battlefield_recovered_injury(before,actual)))
                        continue
                    request = build_pc_npc_recover(state)
                    before = state.enemy(actor).state.injury
                    consume(PcNpcRecoverProof(request,execute_recover_action(request,rng),before,
                        flagellant_recovered_injury(before)))
                else:
                    request = build_pc_melee_recover(state)
                    consume(PcRecoverProof(execute_recover_action(request,rng,decisions=decisions)))
            elif pc_melee_selected_action(state) is CombatActionKind.HELP:
                if actor in scenario.enemy_activation_order:
                    request = build_pc_npc_help_action(state)
                    consume(PcNpcHelpProof(request,execute_automatic_help_action(request)))
                else:
                    request = build_pc_help_action(state)
                    test,decline,glorious,effective = _resolve_pc_test(state,actor,request.help_skill,
                        request.help_test,rng,decisions)
                    execution = _complete_help_action(replace(request,help_test=effective),test)
                    from towr.domain.pc_help_models import pc_help_beneficiary_weapon,pc_selected_help_policy
                    from towr.domain.pc_ranged_models import complete_pc_ranged_help
                    consume(PcHelpProof(request,execution,decline,glorious,
                        beneficiary_weapon_item_id=pc_help_beneficiary_weapon(state,pc_selected_help_policy(state)),
                        ranged_use=complete_pc_ranged_help(state,request,replace(request,help_test=effective),execution)))
            else:
                blood_rage = expected_pc_npc_blood_rage(state)
                if blood_rage is not None:
                    consume(blood_rage)
                    continue
                net_draw = expected_pc_npc_net_draw(state)
                if net_draw is not None:
                    consume(net_draw)
                    continue
                request, protection_request = build_pc_melee_attack(state)
                protection = prepare_protection(protection_request)
                _validate_attack_action_slot(request)
                pc_actor = actor if actor in scenario.pc_activation_order else request.target_id
                pc_test = (request.kernel_request.attack.attacker_test if actor == pc_actor
                    else request.kernel_request.attack.defender_test)
                decline,glorious = None,None
                attack_request = request.kernel_request.attack
                if actor == pc_actor:
                    attacker,decline,glorious,effective = _resolve_pc_test(state,pc_actor,pc_attack_skill(state,pc_actor),
                        pc_test,rng,decisions)
                    defender = resolve_test(attack_request.defender_test,rng,decisions=decisions)
                    attack_request = replace(attack_request,attacker_test=effective)
                else:
                    npc_glorious_source = pc_bestigor_glorious_source(state, actor)
                    attacker = resolve_test(attack_request.attacker_test,rng,
                        decisions=RerollAllFailures() if (npc_glorious_source is not None
                            or pending_wild_attack(state) is not None) else decisions)
                    if pc_test is None:
                        defender = None
                    else:
                        skill = protection.source_request.selected_skill
                        defender,decline,glorious,effective = _resolve_pc_test(state,pc_actor,skill,
                            pc_test,rng,decisions)
                        attack_request = replace(attack_request,defender_test=effective)
                # Initial pools are rolled once, and PC Fate precedes its rerolls.
                attack = _resolve_attack_after_tests(attack_request,attacker,defender)
                effective_kernel = replace(request.kernel_request,attack=attack_request)
                resolution = _resolve_kernel_attack_after_test(effective_kernel,attack,rng,decisions=decisions)
                execution = _complete_attack_action(replace(request,kernel_request=effective_kernel),resolution)
                ranged_shot = (complete_pc_ranged_shot(state,request,
                    replace(request,kernel_request=effective_kernel),execution)
                    if actor==pc_actor and pc_attack_skill(state,actor) is Skill.SHOOTING else None)
                npc_ranged_shot = (complete_pc_npc_ranged_shot(state,request,
                    replace(request,kernel_request=effective_kernel),execution)
                    if actor!=pc_actor and pc_npc_ranged_weapon(state,actor) is not None else None)
                proof = PcAttackProof(request,protection,execution,decline,glorious,
                    pc_attack_help_applications(state,request.kernel_request.attack),
                    pc_npc_attack_help_applications(state,request.kernel_request.attack),
                    npc_glorious_source=pc_bestigor_glorious_source(state, actor),ranged_shot=ranged_shot,
                    npc_ranged_shot=npc_ranged_shot)
                proof=replace(proof,weighted_net_landing=complete_weighted_net_throw(state,request,execution))
                consume(replace(proof,nearby_snapshot=pc_blunderbuss_snapshot(state,proof)))
            continue
        net_draw = expected_pc_npc_net_draw(state)
        if net_draw is not None:
            consume(net_draw)
            continue
        second_action = build_pc_aim_second_action(state)
        if second_action is not None:
            consume(PcAimSecondActionProof(spend_fate_for_second_action(second_action)))
            continue
        extra_slot = build_pc_npc_extra_attack_slot(state)
        if extra_slot is not None:
            consume(reserve_combat_action_slot(extra_slot))
            continue
        finish_turn()
