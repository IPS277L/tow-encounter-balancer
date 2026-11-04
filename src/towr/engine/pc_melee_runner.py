"""One bounded, continuous PLAYER/Minion melee through K1 (ADR-0065)."""
from __future__ import annotations

from dataclasses import replace

from towr.domain.pc_melee_models import PcWeaponHand
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcAttackerStaggerProof, PcEnduranceProof, PcFateDecline,
    PcHandDropProof, PcMeleeOutcome, PcMeleeScenarioResult, PcMeleeState, PcMeleeStep,
    PcProfileWoundProof, PcRecoverProof, PcTurnEndProof, PcWoundCompletionProof,
    PcBodyConsequenceProof, PcWoundChoiceProof, PcHandSwapProof, PcCriticalProof, PcIncapacitatedTurnEndProof, PcHelpProof,
    build_pc_melee_attack, build_pc_melee_recover, build_pc_wound_completion, initial_pc_melee_state, pc_after_test,
    pc_melee_action_id, pc_melee_next_actor, pc_melee_selected_action, pc_melee_unsupported,
    project_pc_melee_step, pc_melee_round_participants, validate_pc_melee_state_shape,
    validate_pc_melee_source_types, _pc_test,
)
from towr.domain.condition_models import StaggerChoice, Condition
from towr.domain.pc_heavy_wound_models import preferred_weapon_hand
from towr.domain.pc_fate_test_models import build_pc_glorious_spend
from towr.domain.pc_help_models import build_pc_help_action, pc_attack_help_applications
from towr.rules.help_resolution import _complete_help_action
from towr.domain._pc_heavy_wound_projection import consequence_sides, clutch_candidates
from towr.domain.critical_injury_models import CriticalInjuryTestRequest
from towr.rules.critical_injury_resolution import resolve_critical_injury_test
from towr.domain.injury_models import WoundConsequenceRequest, WoundEnduranceTestRequest, ProfileStateChangeRequest, WoundChoiceRequest, WoundChoice, WoundConsequence
from towr.domain.resolution_models import AttackerStaggerRequest
from towr.domain.test_models import Skill
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundAdvanceRequest, CombatTurnEndRequest, CombatTurnEndResult, CombatTurnParticipant, CombatTurnStartRequest, CombatSide,
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
        step = PcMeleeStep(state,proof)
        steps.append(step)
        state = step.state

    def finish_turn():
        combat = state.round_state
        actor = combat.active_turn.actor_id
        action_id = pc_melee_action_id(state,actor)
        is_pc = actor in scenario.pc_activation_order
        critical = None
        if is_pc and state.participant(actor).injury.conditions.has(Condition.CRITICALLY_INJURED):
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
            decline = _decline(state,actor,action_id+':end','action') if is_pc else None
            result = end_combat_turn(CombatTurnEndRequest(action_id+':end',combat,actor))
            consume(PcTurnEndProof(result,decline,critical))

    while True:
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
            if isinstance(pending,WoundEnduranceTestRequest):
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
                consume(PcAttackerStaggerProof(pending))
            elif isinstance(pending,ProfileStateChangeRequest):
                attack = next(p for p in reversed(state.history) if isinstance(p,PcAttackProof))
                decision = (scenario.participant(attack.request.actor_id).defeat_decision(attack.request.target_id)
                    if pending.defeated else None)
                consume(PcProfileWoundProof(pending,decision))
            else:
                raise ValueError('unexpected mandatory PC continuation')
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
            if actor in scenario.pc_activation_order:
                member = state.participant(actor)
                if member.injury.conditions.has(Condition.DEFENCELESS):
                    finish_turn()
                    continue
                hand = preferred_weapon_hand(member,scenario.participant(actor).initial_weapon_hand)
                if member.weapon_hand is not None and hand is not None and hand is not member.weapon_hand:
                    consume(PcHandSwapProof(member.weapon_hand,hand))
                    continue
            consume(reserve_combat_action_slot(CombatActionSlotRequest(action_id+':reserve',combat,actor,
                CombatActionDeclaration(pc_melee_selected_action(state)),ActionSlotGrant.STANDARD)))
            continue
        if not combat.active_turn.action_slots[0].executed:
            if pc_melee_selected_action(state) is CombatActionKind.RECOVER:
                request = build_pc_melee_recover(state)
                consume(PcRecoverProof(execute_recover_action(request,rng,decisions=decisions)))
            elif pc_melee_selected_action(state) is CombatActionKind.HELP:
                request = build_pc_help_action(state)
                test,decline,glorious,effective = _resolve_pc_test(state,actor,Skill.MELEE,
                    request.help_test,rng,decisions)
                execution = _complete_help_action(replace(request,help_test=effective),test)
                consume(PcHelpProof(request,execution,decline,glorious))
            else:
                request, protection_request = build_pc_melee_attack(state)
                protection = prepare_protection(protection_request)
                _validate_attack_action_slot(request)
                pc_actor = actor if actor in scenario.pc_activation_order else request.target_id
                pc_test = (request.kernel_request.attack.attacker_test if actor == pc_actor
                    else request.kernel_request.attack.defender_test)
                decline,glorious = None,None
                attack_request = request.kernel_request.attack
                if actor == pc_actor:
                    attacker,decline,glorious,effective = _resolve_pc_test(state,pc_actor,Skill.MELEE,
                        pc_test,rng,decisions)
                    defender = resolve_test(attack_request.defender_test,rng,decisions=decisions)
                    attack_request = replace(attack_request,attacker_test=effective)
                else:
                    attacker = resolve_test(attack_request.attacker_test,rng,decisions=decisions)
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
                consume(PcAttackProof(request,protection,execution,decline,glorious,
                    pc_attack_help_applications(state,request.kernel_request.attack)))
            continue
        finish_turn()
