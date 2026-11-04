"""One bounded, continuous PLAYER/Minion melee through K1 (ADR-0065)."""
from __future__ import annotations

from towr.domain.pc_melee_models import PcWeaponHand
from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcAttackerStaggerProof, PcEnduranceProof, PcFateDecline,
    PcHandDropProof, PcMeleeOutcome, PcMeleeScenarioResult, PcMeleeState, PcMeleeStep,
    PcProfileWoundProof, PcRecoverProof, PcTurnEndProof, PcWoundCompletionProof,
    build_pc_melee_attack, build_pc_melee_recover, initial_pc_melee_state, pc_after_test,
    pc_melee_action_id, pc_melee_next_actor, pc_melee_selected_action, pc_melee_unsupported,
    project_pc_melee_step, pc_melee_round_participants, validate_pc_melee_state_shape,
    validate_pc_melee_source_types, _pc_test,
)
from towr.domain.condition_models import StaggerChoice
from towr.domain.injury_models import WoundConsequenceRequest, WoundEnduranceTestRequest, ProfileStateChangeRequest
from towr.domain.resolution_models import AttackerStaggerRequest
from towr.domain.test_models import Skill
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatActionSlotRequest,
    CombatRoundAdvanceRequest, CombatTurnEndRequest, CombatTurnParticipant, CombatTurnStartRequest, CombatSide,
)
from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleCompletionRequest
from towr.rules.attack_action_execution import _complete_attack_action, _validate_attack_action_slot
from towr.rules.attack_resolution import resolve_attack
from towr.rules.dice import RandomSource
from towr.rules.kernel import _resolve_kernel_attack_after_test
from towr.rules.protection_preparation import prepare_protection
from towr.rules.recover_resolution import execute_recover_action
from towr.rules.test_resolution import KeepAllFailures, resolve_test
from towr.rules.turn_resolution import start_combat_turn, reserve_combat_action_slot, end_combat_turn, advance_combat_round
from towr.rules.wound_effect_resolution import resolve_wound_endurance_test
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

    while True:
        unsupported = pc_melee_unsupported(state)
        if unsupported is not None:
            return PcMeleeScenarioResult(scenario,tuple(steps),PcMeleeOutcome.UNSUPPORTED_PATH,unsupported)
        # The raw PLAYER injury can already have dead=True. Never decide defeat
        # while the actual Near Miss lifecycle window remains unresolved.
        if state.pending_wound is not None:
            pending = state.pending_wound
            consumed = tuple(p.completion.source_request.roll.request_id for p in state.history
                if isinstance(p,PcWoundCompletionProof))
            pc_actor = state.pending_actor_id
            member = state.participant(pc_actor)
            request = CharacterWoundLifecycleCompletionRequest(pending.request_id+':complete',pending,
                member.injury,member.daily_wounds,daily_registration_id=pending.request_id+':daily',
                near_miss=None,consumed_roll_ids=consumed)
            decline = _decline(state,pc_actor,pending.request_id,'wound')
            completion = complete_character_wound_lifecycle(request)
            consume(PcWoundCompletionProof(completion,decline))
            continue
        if state.pending:
            pending = state.pending[0]
            pc_actor = state.pending_actor_id
            if isinstance(pending,WoundEnduranceTestRequest):
                test_request = _pc_test(state,pc_actor,pending.test_id,Skill.ENDURANCE)
                decline = _decline(state,pc_actor,test_request.id,'test')
                test = resolve_test(test_request,rng,decisions=decisions)
                result = resolve_wound_endurance_test(pending,pc_after_test(state,pc_actor),test)
                consume(PcEnduranceProof(pending,test_request,test,result,decline))
            elif isinstance(pending,WoundConsequenceRequest):
                die = rng.randint(1,10)
                hand = PcWeaponHand.LEFT if die <= 5 else PcWeaponHand.RIGHT
                consume(PcHandDropProof(pending,die,hand))
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
            consume(reserve_combat_action_slot(CombatActionSlotRequest(action_id+':reserve',combat,actor,
                CombatActionDeclaration(pc_melee_selected_action(state)),ActionSlotGrant.STANDARD)))
            continue
        if not combat.active_turn.action_slots[0].executed:
            if pc_melee_selected_action(state) is CombatActionKind.RECOVER:
                request = build_pc_melee_recover(state)
                consume(PcRecoverProof(execute_recover_action(request,rng,decisions=decisions)))
            else:
                request, protection_request = build_pc_melee_attack(state)
                protection = prepare_protection(protection_request)
                _validate_attack_action_slot(request)
                pc_actor = actor if actor in scenario.pc_activation_order else request.target_id
                pc_test = (request.kernel_request.attack.attacker_test if actor == pc_actor
                    else request.kernel_request.attack.defender_test)
                decline = _decline(state,pc_actor,pc_test.id,'test')
                # Test first, then consume the PC's next-Test restriction before
                # the kernel can produce a new Wound or mandatory Endurance.
                attack = resolve_attack(request.kernel_request.attack,rng,decisions=decisions)
                resolution = _resolve_kernel_attack_after_test(request.kernel_request,attack,rng,decisions=decisions)
                execution = _complete_attack_action(request,resolution)
                consume(PcAttackProof(request,protection,execution,decline))
            continue
        decline = _decline(state,actor,action_id+':end','action') if actor in scenario.pc_activation_order else None
        result = end_combat_turn(CombatTurnEndRequest(action_id+':end',combat,actor))
        consume(PcTurnEndProof(result,decline))
