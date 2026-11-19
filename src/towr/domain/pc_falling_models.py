"""Source-bound forced landing and the scene's explicit falling Hazard.

The GM supplies the Hazard rating. This is not a distance-to-damage formula.
Landing spends no voluntary movement; avoidance, Wounds and Fate remain real.
"""
from __future__ import annotations

from dataclasses import dataclass,replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition,ConditionApplicationResult
from towr.domain.injury_models import (
    CharacterInjuryState,CharacterWoundRequest,ProfileInjuryState,ProfileNpcType,
    ProfileStateChangeRequest,ProfileWoundResult,
)
from towr.domain.minion_defeat_models import NpcDefeatDisposition
from towr.domain.pc_battlefield_models import (
    PcBattlefieldState,battlefield_is_midair,battlefield_ground_below,with_actor_placement,
)
from towr.domain.pc_mount_models import PcDismountProof,CombatMount
from towr.domain.resolution_models import (
    HazardExposureRequest,HazardResolutionRequest,HazardResolutionResult,TargetInjuryPolicy,
)
from towr.domain.test_models import Skill,TestRequest,TestResult
from towr.domain.wound_lifecycle_models import (
    CharacterWoundLifecycleRollRequest,CharacterWoundLifecycleCompletionResult,
)

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcFateDecline,PcMeleeState
    from towr.domain.fate_models import FateGloriousSpendResult


FALLING_RULE_ID='RULE-HAZARD-001:scene-falling'


def _identifier(value):
    if type(value) is not str or not value.strip():
        raise TypeError('falling source requires an exact nonempty identifier')


def _same(actual,expected,message):
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types
    if actual!=expected:
        raise ValueError(message)
    validate_pc_melee_source_types(actual,expected)


def _injury(state,actor):
    return (state.participant(actor).injury if actor in state.source.pc_activation_order
        else state.enemy(actor).state.injury)


def falling_npc_disposition(source,actor):
    dispositions={decision.disposition for member in source.party for decision in member.defeat_decisions
        if decision.target_id==actor and decision.gm_approved}
    if len(dispositions)!=1:
        raise ValueError('a falling NPC requires one unambiguous GM-approved defeat disposition')
    return next(iter(dispositions))


def validate_pc_falling_scene(source):
    if source.battlefield is None or source.battlefield.airspace is None:
        return
    for enemy in source.enemies:
        components=enemy.definition.generated_components
        if components is not None and components.mount is CombatMount.PEGASUS:
            falling_npc_disposition(source,enemy.state.actor_id)


def prepare_hazard_avoidance(state,actor,exposure,*,environmental=False):
    """Prepare the actual supplied Hazard context, sharing armour with both sides."""
    from towr.domain.pc_armour_models import actor_armour_test_modifiers
    from towr.domain.armour_models import ITHILMAR_ENVIRONMENT_RULE_ID
    if type(exposure) is not HazardExposureRequest or type(environmental) is not bool:
        raise TypeError('Hazard preparation needs its exact exposure and environmental fact')
    replace(exposure)
    if actor in state.source.pc_activation_order:
        from towr.domain.pc_melee_result_models import _pc_test
        request=_pc_test(state,actor,exposure.test_id,exposure.avoidance_skill)
        # _pc_test already includes ordinary armour penalties. Only the extra
        # environmental benefit is added here, exactly once.
        environmental_bonus=tuple(modifier for modifier in actor_armour_test_modifiers(
            state,actor,exposure.avoidance_skill,environmental=environmental)
            if modifier.rule_id==ITHILMAR_ENVIRONMENT_RULE_ID)
        if state.participant(actor).injury.conditions.has(Condition.DRAINED):
            environmental_bonus=()
        return replace(request,dice_modifiers=(*request.dice_modifiers,*environmental_bonus))
    enemy=state.enemy(actor)
    profile=next((option.test_profile for option in enemy.definition.protection
        if option.skill is exposure.avoidance_skill),None)
    if profile is None:
        raise ValueError('Hazard avoidance needs an explicit NPC Skill profile')
    from towr.domain.pc_magic_models import magic_test_modifiers
    dice,qualities=magic_test_modifiers(state,actor,exposure.avoidance_skill)
    modifiers=(*dice,*actor_armour_test_modifiers(state,actor,exposure.avoidance_skill,
        environmental=environmental))
    if enemy.state.injury.conditions.has(Condition.DRAINED):
        modifiers=tuple(modifier for modifier in modifiers if modifier.amount<=0)
    return TestRequest(exposure.test_id,profile,modifiers,qualities)


@dataclass(frozen=True,slots=True)
class PcFallingRequest:
    id: str
    actor_id: str
    dismount_history_index: int
    source_dismount: PcDismountProof
    previous_battlefield: PcBattlefieldState
    battlefield: PcBattlefieldState
    exposure: HazardExposureRequest
    avoidance_test: TestRequest | None
    previous_injury: CharacterInjuryState | ProfileInjuryState
    target_injury: CharacterInjuryState | ProfileInjuryState
    target_policy: TargetInjuryPolicy

    def __post_init__(self):
        _identifier(self.id);_identifier(self.actor_id)
        if type(self.dismount_history_index) is not int or self.dismount_history_index<0:
            raise ValueError('falling requires its actual dismount history index')
        if type(self.source_dismount) is not PcDismountProof or self.source_dismount.actor_id!=self.actor_id:
            raise ValueError('falling must retain this actor\'s forced dismount')
        for item,kind in ((self.previous_battlefield,PcBattlefieldState),
                (self.battlefield,PcBattlefieldState),(self.exposure,HazardExposureRequest)):
            if type(item) is not kind:
                raise TypeError('falling requires exact battlefield and exposure sources')
            replace(item)
        if self.avoidance_test is not None:
            if type(self.avoidance_test) is not TestRequest or self.avoidance_test.id!=self.exposure.test_id:
                raise ValueError('falling avoidance must preserve the exposure Test')
            replace(self.avoidance_test)
        if (type(self.previous_injury) not in (CharacterInjuryState,ProfileInjuryState)
                or type(self.target_injury) is not type(self.previous_injury)):
            raise TypeError('falling injury states must retain their exact body type')
        replace(self.previous_injury);replace(self.target_injury)
        if self.target_policy not in (TargetInjuryPolicy.PLAYER,TargetInjuryPolicy.MINION):
            raise ValueError('this falling owner requires an admitted PC or generated Minion')


@dataclass(frozen=True,slots=True)
class PcFallingProof:
    request: PcFallingRequest
    test: TestResult | None
    result: HazardResolutionResult | None
    fate_decline: PcFateDecline | None = None
    glorious: FateGloriousSpendResult | None = None
    npc_disposition: NpcDefeatDisposition | None = None

    @property
    def actor_id(self):
        return self.request.actor_id


@dataclass(frozen=True,slots=True)
class PcFallingAcknowledgementProof:
    source_id: str
    completion: CharacterWoundLifecycleCompletionResult
    result: HazardResolutionResult


def expected_pc_falling_request(state):
    if state.battlefield is None or state.source.battlefield.airspace is None:
        return None
    if state.pending or state.pending_wound is not None:
        return None
    used={proof.request.dismount_history_index for proof in state.history if type(proof) is PcFallingProof}
    for index,proof in enumerate(state.history):
        if type(proof) is not PcDismountProof or index in used:
            continue
        actor=proof.actor_id
        if not battlefield_is_midair(state.battlefield,actor):
            continue
        origin=state.battlefield.spatial.placement_for(actor).zone_id
        landing=battlefield_ground_below(state.battlefield,origin)
        battlefield=with_actor_placement(state.battlefield,actor,landing)
        identifier=state.source.id+':fall:'+str(index)+':'+actor
        exposure=HazardExposureRequest(identifier,identifier+':athletics',
            state.source.battlefield.airspace.fall_hazard_rating,Skill.ATHLETICS,FALLING_RULE_ID,
            True,(Condition.PRONE,))
        injury=_injury(state,actor)
        is_pc=actor in state.source.pc_activation_order
        alive=not (injury.dead if is_pc else injury.defeated)
        test=prepare_hazard_avoidance(state,actor,exposure,environmental=True) if alive else None
        if is_pc and alive:
            from towr.domain.pc_melee_result_models import pc_after_test
            target=pc_after_test(state,actor)
        else:
            target=injury
        return PcFallingRequest(identifier,actor,index,proof,state.battlefield,battlefield,
            exposure,test,injury,target,TargetInjuryPolicy.PLAYER if is_pc else TargetInjuryPolicy.MINION)
    return None


def falling_hazard_request(request,test):
    return HazardResolutionRequest(request.id,request.actor_id,request.exposure,test,
        request.target_policy,request.target_injury)


def _prone_application(identifier,injury):
    return ConditionApplicationResult(identifier+':failure-condition:0:prone',
        injury.conditions.with_condition(Condition.PRONE),Condition.PRONE,
        injury.conditions.has(Condition.PRONE),False,FALLING_RULE_ID,None,(FALLING_RULE_ID,))


def _canonical_hazard(request,test,result):
    """Validate retained outcomes without executing a second Hazard or Wound roll."""
    if type(result) is not HazardResolutionResult:
        raise TypeError('falling must retain its actual Hazard result')
    rating=request.exposure.rating
    shortfall=max(0,rating-test.successes)
    injury=request.target_injury
    if not shortfall:
        expected=HazardResolutionResult(request.id,injury,True,test.successes,rating,0,
            None,None,None,(),(),(FALLING_RULE_ID,))
    elif request.target_policy is TargetInjuryPolicy.PLAYER:
        pending=result.pending_character_wound
        if pending is None:
            raise ValueError('failed falling Hazard must retain its real PC Wound lifecycle')
        replace(pending)
        source=CharacterWoundLifecycleRollRequest(request.id+':wound-lifecycle',request.actor_id,
            CharacterWoundRequest(request.id+':wound',injury,base_dice=shortfall))
        _same(pending.source_request,source,'falling Wound changed its actual shortfall/body source')
        expected=HazardResolutionResult(request.id,pending.wound_result.state,False,test.successes,
            rating,shortfall,pending.wound_result,None,None,(),(),(FALLING_RULE_ID,),
            pending_character_wound=pending,deferred_failure_exposure=request.exposure)
    else:
        wounds=min(injury.wound_limit,injury.wounds+shortfall)
        wounded=ProfileInjuryState(wounds,injury.wound_limit,
            injury.conditions.without_condition(Condition.STAGGERED),wounds>=injury.wound_limit)
        change=ProfileStateChangeRequest(ProfileNpcType.MINION,injury.wounds,wounds,wounded.defeated)
        profile=ProfileWoundResult(request.id+':wound',wounded,shortfall,wounds-injury.wounds,change,())
        application=_prone_application(request.id,wounded)
        after=replace(wounded,conditions=application.state)
        expected=HazardResolutionResult(request.id,after,False,test.successes,rating,shortfall,
            None,None,profile,(Condition.PRONE,),(change,),(FALLING_RULE_ID,),
            condition_applications=(application,))
    _same(result,expected,'falling Hazard changed its canonical Test/Wound/Condition outcome')


def falling_acknowledgement_source(state):
    from towr.domain.pc_melee_result_models import PcWoundCompletionProof
    acknowledged={proof.source_id for proof in state.history if type(proof) is PcFallingAcknowledgementProof}
    for proof in state.history:
        if (type(proof) is not PcFallingProof or proof.result is None
                or proof.result.pending_character_wound is None or proof.request.id in acknowledged):
            continue
        completion=next((item.completion for item in state.history
            if type(item) is PcWoundCompletionProof
            and item.completion.source_request.roll==proof.result.pending_character_wound),None)
        if completion is not None:
            return proof,completion
    return None


def build_pc_falling_acknowledgement(state):
    from towr.rules.hazard_resolution import apply_hazard_character_wound_completion
    source=falling_acknowledgement_source(state)
    if source is None:
        raise ValueError('no actual falling Wound completion awaits acknowledgement')
    proof,completion=source
    return PcFallingAcknowledgementProof(proof.request.id,completion,
        apply_hazard_character_wound_completion(proof.result,completion))


def project_pc_falling_step(state,proof):
    if type(proof) is PcFallingAcknowledgementProof:
        source=falling_acknowledgement_source(state)
        if source is None:
            raise ValueError('falling acknowledgement is detached or repeated')
        previous,completion=source
        _same(proof.completion,completion,'falling acknowledgement replaced the actual Wound completion')
        application=_prone_application(previous.request.id,completion.state)
        injury=replace(completion.state,conditions=application.state)
        expected=replace(previous.result,state=injury,wound_effect=completion.wound_effect,
            failure_conditions=(Condition.PRONE,),condition_applications=(application,),
            follow_ups=(() if completion.wound_effect is None else completion.wound_effect.follow_ups),
            pending_character_wound=None,deferred_failure_exposure=None,character_wound_completion=completion)
        _same(proof,PcFallingAcknowledgementProof(previous.request.id,completion,expected),
            'falling acknowledgement changed its deferred failure effects')
        actor=previous.actor_id
        member=state.participant(actor)
        return dict(party=tuple(replace(item,injury=injury) if item.actor_id==actor else item for item in state.party))
    if type(proof) is not PcFallingProof or type(proof.request) is not PcFallingRequest:
        raise TypeError('falling requires its exact source-bound proof')
    request=expected_pc_falling_request(state)
    _same(proof.request,request,'falling changed its actual dismount, position or GM Hazard facts')
    actor=request.actor_id
    updates=dict(battlefield=request.battlefield)
    if request.avoidance_test is None:
        if any(value is not None for value in (proof.test,proof.result,proof.fate_decline,
                proof.glorious,proof.npc_disposition)):
            raise ValueError('a confirmed dead body cannot invent another avoidance Test or Wound')
        return updates
    if type(proof.test) is not TestResult:
        raise TypeError('a living falling participant must retain its real avoidance Test')
    is_pc=actor in state.source.pc_activation_order
    fate=None
    if is_pc:
        from towr.domain.pc_fate_test_models import validate_pc_test_fate
        _,fate=validate_pc_test_fate(state,actor,Skill.ATHLETICS,request.avoidance_test,
            proof.test,proof.fate_decline,proof.glorious)
        if proof.npc_disposition is not None:
            raise ValueError('a falling PC cannot carry an NPC defeat disposition')
    else:
        from towr.domain.pc_melee_result_models import _test_result
        if proof.fate_decline is not None or proof.glorious is not None:
            raise ValueError('NPC falling cannot invent PC Fate')
        _test_result(request.avoidance_test,proof.test)
    _canonical_hazard(request,proof.test,proof.result)
    if is_pc:
        updates['party']=tuple(replace(member,injury=proof.result.state,
            fate=member.fate if fate is None else fate) if member.actor_id==actor else member for member in state.party)
        updates['pending_wound']=proof.result.pending_character_wound
        if proof.result.pending_character_wound is not None:
            updates['pending_actor_id']=actor
    else:
        disposition=falling_npc_disposition(state.source,actor) if proof.result.profile_wound is not None else None
        if proof.npc_disposition is not disposition:
            raise ValueError('NPC falling must acknowledge the actual agreed GM defeat disposition')
        updates['enemies']=tuple(replace(enemy,state=replace(enemy.state,injury=proof.result.state))
            if enemy.state.actor_id==actor else enemy for enemy in state.enemies)
        clock=state.round_state
        if (proof.result.state.defeated
                and actor not in (*clock.completed_turn_entity_ids,*clock.excluded_turn_entity_ids)):
            # A fall during someone else's Attack must retain that actual
            # paid turn. An active defeated rider cannot keep an open turn.
            active=clock.active_turn
            updates['round_state']=replace(clock,
                active_turn=None if active is not None and active.actor_id==actor else active,
                excluded_turn_entity_ids=(*clock.excluded_turn_entity_ids,actor))
    from towr.domain.pc_magic_models import consume_magic_modifiers
    updates['magic_modifiers']=consume_magic_modifiers(state.magic_modifiers,proof)
    return updates
