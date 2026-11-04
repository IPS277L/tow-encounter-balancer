"""Pure projections of the explicit M9 journal variants; no RNG or execution."""
from dataclasses import replace

from towr.domain.pc_melee_result_models import (
    PcAttackProof, PcAttackerStaggerProof, PcEnduranceProof, PcHandDropProof, PcMeleeState,
    PcProfileWoundProof, PcRecoverProof, PcTimedWound, PcTurnEndProof, PcWoundCompletionProof,
    PcBodyConsequenceProof, PcWoundChoiceProof, PcHandSwapProof, PcCriticalProof, PcIncapacitatedTurnEndProof,
    build_pc_melee_attack, build_pc_melee_recover, build_pc_wound_completion, pc_after_test, pc_melee_action_id,
    pc_melee_next_actor, pc_melee_selected_action, pc_melee_unsupported,
    validate_pc_melee_combat_shape, validate_pc_melee_state_shape, validate_pc_melee_source_types,
    _decline, _enemy_update, _party_update, _pc_test, _ready, _test_result, pc_melee_round_participants,
)
from towr.domain.attack_models import AttackOutcome, DamageImpactSpec, ImpactOutcome, MissConsequence
from towr.domain.injury_models import (
    CharacterWoundRequest, CharacterWoundType, ProfileNpcType, ProfileStateChangeRequest, ProfileWoundResult,
    WoundConditionEffect, WoundConsequence, WoundConsequenceRequest, WoundEffectDuration,
    WoundEnduranceFailure, WoundEnduranceTestRequest, WoundEntryId,
    WoundRestriction, WoundRestrictionEffect,
)
from towr.domain.condition_models import Condition, ConditionState, StaggerChoice, StaggerOutcome, StaggerResult
from towr.domain.fate_models import _expected_fate_burn, FATE_SESSION_RULE_ID, FATE_BURN_RULE_ID
from towr.domain.fate_near_miss_models import FateNearMissApplicationRequest, _near_miss_applied_rule_ids
from towr.domain.pc_melee_models import PcWeaponHand
from towr.domain.minion_defeat_models import MinionDefeatDecision
from towr.domain.resolution_models import AttackerStaggerRequest, condition_forces_wound
from towr.domain.pc_heavy_wound_models import (PcBodyFact, PcBodyFactKind, usable_hands, usable_weapon_hand, preferred_weapon_hand, has_ongoing_condition, critical_for_action, critical_for_hand, critical_for_incidental_hand_use)
from towr.domain._pc_heavy_wound_projection import heavy_wound_effect, body_consequence, consequence_sides, clutch_candidates
from towr.domain.critical_injury_models import CriticalInjuryTestRequest
from towr.domain.test_models import Skill
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


def _canonical_attack(request, attack):
    if type(attack.request_id) is not str or not isinstance(attack.impact_spec,DamageImpactSpec):
        raise TypeError('PC Attack requires its exact ID and ordinary Damage spec')
    replace(attack.impact_spec)
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
    damage = request.impact_spec.damage.base + margin if hit else None
    resilience = request.impact_spec.resilience.total if hit else None
    impact = (ImpactOutcome.WOUND if damage > resilience else ImpactOutcome.STAGGERED) if hit else None
    miss = MissConsequence.NONE if hit or request.attacker_is_staggered else MissConsequence.STAGGER_ATTACKER
    tie = hit and request.defender_test is not None and a == d
    rules = ('RULE-COMBAT-006:attack-tie',) if tie else ()
    expected = (request.id,AttackOutcome.HIT if hit else AttackOutcome.MISS,margin,request.impact_spec,
        damage,resilience,impact,miss,tie,rules)
    actual = (attack.request_id,attack.outcome,attack.success_margin,attack.impact_spec,
        attack.damage,attack.effective_resilience,attack.impact,attack.miss_consequence,
        attack.tie_break_applied,attack.applied_rule_ids)
    _same(actual,expected,'PC Attack result is not canonical for its actual Tests/source')
    for value in (a,d,margin):
        if type(value) is not int:
            raise TypeError('Attack arithmetic must use exact integers')


def _ordinary_resolution(kernel, result):
    if (result.replacement_impact is not None or result.monstrosity_impact is not None
            or result.wound_effect is not None or result.character_wound_completion is not None
            or result.applied_secondary_rule_ids != () or result.condition_applications != ()
            or result.deferred_wound_conditions != () or result.deferred_wound_condition_immunities != ()):
        raise ValueError('ordinary PC Attack cannot carry foreign effect/secondary/completion branches')
    expected_stagger = None
    if result.attack.outcome is AttackOutcome.HIT and result.attack.impact is ImpactOutcome.STAGGERED and not condition_forces_wound(kernel,result.attack):
        conditions = kernel.target_state.conditions
        if conditions.has(Condition.STAGGERED):
            choices = []
            if kernel.can_target_leave_zone and not conditions.has(Condition.PRONE):
                choices.append(StaggerChoice.GIVE_GROUND)
            if not conditions.has(Condition.PRONE):
                choices.append(StaggerChoice.FALL_PRONE)
            choices.append(StaggerChoice.SUFFER_WOUND)
            expected_stagger = StaggerResult(kernel.id+':stagger',conditions,StaggerOutcome.WOUND_REQUESTED,
                tuple(choices),StaggerChoice.SUFFER_WOUND,True,False)
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


def _canonical_wound_effect(completion):
    roll = completion.source_request.roll
    raw = roll.wound_result
    request = raw.effect_request
    wound = raw.state.wounds[-1]
    effects = list(raw.state.active_wound_effects)
    conditions = raw.state.conditions
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
        expected,followups = heavy_wound_effect(raw,request)
        effect = completion.wound_effect
        replace(effect.request)
        for follow_up in effect.follow_ups:
            replace(follow_up)
        _same((effect.request,effect.state,effect.follow_ups),(request,expected,followups),
            'heavy PC Wound completion changed its exact effects/follow-ups')
        return
    wounds = (*raw.state.wounds[:-1],replace(wound,effect_resolved=True))
    expected = replace(raw.state,wounds=wounds,conditions=conditions,active_wound_effects=tuple(effects))
    effect = completion.wound_effect
    replace(effect.request)
    for follow_up in effect.follow_ups:
        replace(follow_up)
    _same((effect.request,effect.state,effect.follow_ups),(request,expected,followups),
        'PC Wound completion has forged immediate effects/follow-ups')


def project_pc_step(state, proof):
    if not isinstance(state,PcMeleeState):
        raise TypeError('PC transition requires complete typed owner')
    validate_pc_melee_state_shape(state)
    if pc_melee_unsupported(state) is not None:
        raise ValueError('unsupported PC consequence cannot be silently continued')
    combat, scenario = state.round_state, state.source
    pc_actor = state.pending_actor_id
    if pc_actor is None and combat.active_turn is not None:
        actor = combat.active_turn.actor_id
        if actor in scenario.pc_activation_order:
            pc_actor = actor
        elif combat.active_turn.action_slots and combat.active_turn.action_slots[0].executed:
            # A lethal result can remove this target from live priority before
            # the attacker's turn is closed; retain the actual action target.
            pc_actor = next(p.request.target_id for p in reversed(state.history) if isinstance(p, PcAttackProof))
        else:
            pc_actor = next(a for a in scenario.enemy_target_priority if not state.participant(a).injury.dead)
    member = state.participant(pc_actor) if pc_actor is not None else None
    participant = scenario.participant(pc_actor) if pc_actor is not None else None

    def finish(**updates):
        pending = updates.get('pending', state.pending)
        pending_wound = updates.get('pending_wound', state.pending_wound)
        if not pending and pending_wound is None:
            updates['pending_actor_id'] = None
        elif 'pending_actor_id' not in updates:
            updates['pending_actor_id'] = pc_actor
        return replace(state,history=(*state.history,proof),**updates)
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
        _same(proof.applied_rule_ids,('RULE-COMBAT-002:action-budget',),'reservation rule trace changed')
        _ready(state)
        turn = combat.active_turn
        if turn is None or turn.action_slots:
            raise ValueError('PC standard action must be the sole unreserved slot')
        declaration = CombatActionDeclaration(pc_melee_selected_action(state))
        slot = CombatActionSlot(1,declaration,ActionSlotGrant.STANDARD)
        expected = replace(combat,active_turn=replace(turn,action_slots=(slot,)))
        _same((proof.request_id,proof.state,proof.slot),(pc_melee_action_id(state,turn.actor_id)+':reserve',expected,slot),
            'PC reservation differs from the selected standard action')
        return finish(round_state=expected)
    if isinstance(proof,PcAttackProof):
        _ready(state)
        turn = combat.active_turn
        if turn is None or len(turn.action_slots) != 1 or turn.action_slots[0].executed:
            raise ValueError('PC Attack must consume its unused standard slot once')
        if pc_melee_selected_action(state) is not CombatActionKind.ATTACK:
            raise ValueError('PC Attack cannot replace the selected Recover')
        expected, protection = build_pc_melee_attack(state)
        _same(proof.request,expected,'PC Attack request differs from the current complete source')
        replace(proof.protection)
        _same(proof.protection.source_request,protection,'PC Protection changed profile or equipment eligibility')
        _same(proof.protection.attack,expected.kernel_request.attack,'PC Protection Attack differs from execution')
        execution = proof.execution
        validate_pc_melee_combat_shape(execution.previous_state)
        validate_pc_melee_combat_shape(execution.state)
        replace(execution)
        _same((execution.request_id,execution.previous_state,execution.actor_id,execution.target_id,execution.slot_index),
            (expected.id,combat,expected.actor_id,expected.target_id,1),'PC Attack receipt is detached')
        result = execution.resolution
        _same(execution.applied_rule_ids,('RULE-COMBAT-004:attack-action-execution',),'Attack action rule trace changed')
        _canonical_attack(expected.kernel_request.attack,result.attack)
        _ordinary_resolution(expected.kernel_request,result)
        if result.request_id != expected.kernel_request.id:
            raise ValueError('PC Attack kernel result changed its source ID')
        pc_test = (expected.kernel_request.attack.attacker_test if expected.actor_id == pc_actor
            else expected.kernel_request.attack.defender_test)
        if pc_test is None:
            if proof.fate_decline is not None:
                raise ValueError('Defenceless Protection cannot invent a Test/Fate window')
            pc_injury = member.injury
        else:
            _decline(state,proof.fate_decline,pc_actor,pc_test.id,'test')
            caused = (critical_for_action(member,CombatActionKind.ATTACK,used_hand=usable_weapon_hand(member))
                if expected.actor_id == pc_actor else critical_for_hand(member,
                    usable_weapon_hand(member) if proof.protection.source_request.selected_skill is Skill.DEFENCE else None))
            pc_injury = pc_after_test(state,pc_actor,caused)
        before = expected.kernel_request.target_state
        pending_wound = None
        if result.attack.outcome is AttackOutcome.MISS:
            _same(result.target_state,before,'miss changed the target injury')
            followups = ((AttackerStaggerRequest(expected.kernel_request.attack.id),)
                if result.attack.miss_consequence is MissConsequence.STAGGER_ATTACKER else ())
            if result.character_wound is not None or result.profile_wound is not None or result.pending_character_wound is not None:
                raise ValueError('miss invented a Wound')
        elif result.attack.impact is ImpactOutcome.STAGGERED and not before.conditions.has(Condition.STAGGERED) and not condition_forces_wound(expected.kernel_request,result.attack):
            target = replace(before,conditions=before.conditions.with_condition(Condition.STAGGERED))
            _same(result.target_state,target,'first Staggered changed unrelated injury state')
            followups = ()
            if result.character_wound is not None or result.profile_wound is not None or result.pending_character_wound is not None:
                raise ValueError('first Staggered invented a Wound')
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
                    kernel.wound_dice_modifiers,kernel.wound_negation_options))
            replace(wound_source)
            replace(wound_source.wound)
            _same(wound_source,actual_source,'PC Wound pool/options/IDs differ from the actual ordinary Attack')
            _same((result.character_wound,result.target_state,result.wound_effect),
                (pending_wound.wound_result,pending_wound.wound_result.state,None),'PC Wound effects preceded its Fate window')
            followups = ()
        else:
            if result.character_wound is not None or result.pending_character_wound is not None:
                raise ValueError('NPC profile Wound cannot carry a PLAYER lifecycle branch')
            wounds = min(before.wounds+1,before.wound_limit)
            defeated = wounds == before.wound_limit
            target = replace(before,wounds=wounds,defeated=defeated,
                conditions=before.conditions.without_condition(Condition.STAGGERED))
            _same(result.target_state,target,'NPC profile Wound changed unrelated state')
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
                (expected.kernel_request.id+':wound',1,1,()),'NPC profile Wound has a foreign source or count')
            if (type(profile.wounds_requested) is not int or type(profile.wounds_inflicted) is not int
                    or type(profile.state_change.previous_wounds) is not int
                    or type(profile.state_change.current_wounds) is not int
                    or type(profile.state_change.defeated) is not bool
                    or not isinstance(profile.state_change.npc_type,ProfileNpcType)):
                raise TypeError('NPC profile Wound requires typed source/count fields')
            if type(profile.request_id) is not str:
                raise TypeError('NPC profile Wound ID must be a string')
            followups = (change,)
        _same(result.follow_ups,followups,'PC Attack altered mandatory follow-up order')
        enemies = state.enemies
        if expected.target_id == pc_actor:
            pc_injury = result.target_state
        else:
            enemies = _enemy_update(state,expected.target_id,result.target_state)
        return finish(round_state=execution.state,party=_party_update(state,pc_actor,injury=pc_injury),enemies=enemies,
            pending=result.follow_ups,pending_wound=pending_wound)
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
        if injury.dead and pc_actor not in (*combat.completed_turn_entity_ids,*combat.excluded_turn_entity_ids):
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
        _test_result(expected_test,proof.test)
        _decline(state,proof.fate_decline,pc_actor,expected_test.id,'test')
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
        return finish(party=_party_update(state,pc_actor,injury=injury,timed_wounds=timed),pending=(*more,*state.pending[1:]))
    if isinstance(proof,PcHandDropProof):
        if state.pending_wound is not None or not state.pending or state.pending[0] != proof.source:
            raise ValueError('random hand is detached from the next Wound consequence')
        if proof.source.consequence is not WoundConsequence.DROP_RANDOM_HAND_ITEM:
            raise ValueError('unsupported random-hand consequence')
        changed = body_consequence(member,PcBodyConsequenceProof(proof.source,proof.die,proof.hand))
        return finish(party=_party_update(state,pc_actor,weapon_hand=changed.weapon_hand,body_facts=changed.body_facts),pending=state.pending[1:])
    if isinstance(proof,PcBodyConsequenceProof):
        if state.pending_wound is not None or not state.pending or state.pending[0] != proof.source:
            raise ValueError('anatomical consequence is detached from its actual mandatory source')
        replace(proof.source)
        changed = body_consequence(member,proof)
        return finish(party=_party_update(state,pc_actor,injury=changed.injury,weapon_hand=changed.weapon_hand,
            body_facts=changed.body_facts),pending=state.pending[1:])
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
    if isinstance(proof,PcHandSwapProof):
        _ready(state)
        if combat.active_turn is None or combat.active_turn.actor_id != pc_actor or combat.active_turn.action_slots:
            raise ValueError('incidental weapon swap requires its own unreserved turn')
        if member.injury.conditions.has(Condition.DEFENCELESS):
            raise ValueError('Defenceless actor cannot perform an incidental weapon swap')
        hand = preferred_weapon_hand(member,participant.initial_weapon_hand)
        if member.weapon_hand is None or hand is None or hand is member.weapon_hand:
            raise ValueError('no supported beneficial held-weapon swap exists')
        if proof.previous_hand is not member.weapon_hand or proof.hand is not hand:
            raise ValueError('held-weapon swap changed its full current hand source')
        return finish(party=_party_update(state,pc_actor,weapon_hand=hand,
            injury=critical_for_incidental_hand_use(member,hand)))
    if isinstance(proof,PcAttackerStaggerProof):
        if state.pending_wound is not None or not state.pending or state.pending[0] != proof.source:
            raise ValueError('miss Staggered is detached from its pending Attack')
        actor = combat.active_turn.actor_id
        if actor == pc_actor:
            injury = replace(member.injury,conditions=member.injury.conditions.with_condition(Condition.STAGGERED))
            return finish(party=_party_update(state,pc_actor,injury=injury),pending=state.pending[1:])
        old = state.enemy(actor).state.injury
        return finish(enemies=_enemy_update(state,actor,replace(old,conditions=old.conditions.with_condition(Condition.STAGGERED))),pending=state.pending[1:])
    if isinstance(proof,PcProfileWoundProof):
        if (type(proof.source) is not ProfileStateChangeRequest
                or not isinstance(proof.source.npc_type,ProfileNpcType)
                or type(proof.source.previous_wounds) is not int
                or type(proof.source.current_wounds) is not int
                or type(proof.source.defeated) is not bool):
            raise TypeError('profile Wound acknowledgement requires canonical change fields')
        if state.pending_wound is not None or not state.pending or state.pending[0] != proof.source:
            raise ValueError('defeat disposition is detached from its pending profile change')
        attack = next(p for p in reversed(state.history) if isinstance(p,PcAttackProof))
        target = attack.request.target_id
        if target == pc_actor or proof.source != attack.execution.resolution.profile_wound.state_change:
            raise ValueError('profile Wound acknowledgement requires its actual NPC Attack')
        if not proof.source.defeated:
            if proof.decision is not None:
                raise ValueError('a living NPC cannot receive a defeat disposition')
            return finish(pending=state.pending[1:])
        if not isinstance(proof.decision,MinionDefeatDecision):
            raise TypeError('defeated NPC requires the typed caller/GM decision')
        replace(proof.decision)
        _same(proof.decision,participant.defeat_decision(target),'NPC disposition differs from caller/GM decision')
        updated = combat
        if target not in (*combat.completed_turn_entity_ids,*combat.excluded_turn_entity_ids):
            updated = replace(combat,excluded_turn_entity_ids=(*combat.excluded_turn_entity_ids,target))
        return finish(round_state=updated,pending=state.pending[1:])
    if isinstance(proof,PcRecoverProof):
        _ready(state)
        if pc_melee_selected_action(state) is not CombatActionKind.RECOVER:
            raise ValueError('Recover must be the selected PC action')
        expected = build_pc_melee_recover(state)
        replace(proof.result)
        replace(proof.result.resolution)
        for change in proof.result.resolution.condition_changes:
            replace(change)
            ConditionState(change.previous_conditions.conditions)
            ConditionState(change.conditions.conditions)
        replace(proof.result.resolution.previous_magic_state)
        replace(proof.result.resolution.magic_state)
        validate_pc_melee_combat_shape(proof.result.round_state)
        _same(proof.result.source_request,expected,'Recover differs from full owner/weapon/Conditions')
        conditions = member.injury.conditions
        for change in proof.result.resolution.condition_changes:
            conditions = change.conditions
        effects = tuple(e for e in member.injury.active_wound_effects
            if expected.choice.prone_target is None or not isinstance(e,WoundConditionEffect) or e.condition is not Condition.PRONE
                or e.duration is not WoundEffectDuration.UNTIL_REMOVED)
        injury = replace(member.injury,conditions=conditions,active_wound_effects=effects)
        hand = preferred_weapon_hand(member,participant.initial_weapon_hand) if expected.choice.object_interaction is not None else member.weapon_hand
        injury = critical_for_action(replace(member,injury=injury),CombatActionKind.RECOVER,
            removes_prone=expected.choice.prone_target is not None,
            used_hand=hand if expected.choice.object_interaction is not None else None)
        return finish(round_state=proof.result.round_state,party=_party_update(state,pc_actor,injury=injury,weapon_hand=hand))
    if isinstance(proof,(PcTurnEndProof,PcIncapacitatedTurnEndProof)):
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
        return finish(round_state=expected)
    raise TypeError('unsupported PC journal proof type')
