"""Actual reactive Give Ground, PG1.4 V119/123 and ADR-0140.

PG119 separately forbids moving through enemies, obstacles and areas the
creature treats as Difficult Terrain. That prohibition applies to reactive
Give Ground too; PG115's own-turn Athletics timing does not waive it.
This owner spends neither a combat action nor the once-per-turn free move.
"""
from __future__ import annotations

from dataclasses import dataclass,replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition,ConditionState,StaggerChoice
from towr.domain.injury_models import CharacterInjuryState,ProfileInjuryState,WoundRestriction
from towr.domain.pc_battlefield_models import PcBattlefieldState,with_actor_placement,battlefield_is_midair
from towr.domain.resolution_models import (
    GiveGroundRequest,GiveGroundResolutionRequest,GiveGroundResolutionResult,
    ConditionAfterGiveGroundRequest,ConditionAfterGiveGroundResult,
)
from towr.rules.spatial_resolution import resolve_give_ground
from towr.rules.condition_effect_resolution import resolve_condition_after_give_ground

if TYPE_CHECKING:
    from towr.domain.pc_melee_result_models import PcAttackProof
    from towr.domain.pc_demigryph_models import PcDemigryphStrikeProof


def _id(value):
    if type(value) is not str or not value.strip():
        raise TypeError('Give Ground requires exact actual actor identifiers')


def _injury(state,actor):
    return (state.participant(actor).injury if actor in state.source.pc_activation_order
        else state.enemy(actor).state.injury)


def _known_pair(state,actor,attacker,*,allow_friendly_source=False):
    _id(actor);_id(attacker)
    if type(allow_friendly_source) is not bool:
        raise TypeError('friendly Give Ground source permission must be an exact bool')
    if actor==attacker and not allow_friendly_source:
        raise ValueError('an actor cannot Give Ground away from itself')
    actors=(*state.source.pc_activation_order,*state.source.enemy_activation_order)
    if actor not in actors or attacker not in actors:
        raise ValueError('Give Ground requires two actual source participants')
    if not allow_friendly_source and (actor in state.source.pc_activation_order)==(attacker in state.source.pc_activation_order):
        raise ValueError('Give Ground requires an opposing actual attacker')


def _enemies(state,actor):
    return (tuple(enemy.state.actor_id for enemy in state.live_enemies)
        if actor in state.source.pc_activation_order else tuple(member.actor_id for member in state.live_party))


@dataclass(frozen=True,slots=True)
class PcGiveGroundContext:
    actor_id: str
    attacker_id: str
    can_leave: bool
    given_this_round: bool
    destination_zone_id: str | None

    def __post_init__(self):
        _id(self.actor_id);_id(self.attacker_id)
        if type(self.can_leave) is not bool or type(self.given_this_round) is not bool:
            raise TypeError('Give Ground context retains exact boolean facts')
        if self.destination_zone_id is not None:_id(self.destination_zone_id)
        if self.can_leave!=(self.destination_zone_id is not None):
            raise ValueError('Give Ground requires its actual available destination')


def pc_give_ground_context(state,actor,attacker,*,allow_friendly_source=False):
    """Choose a real adjacent destination, preferring an enemy-free Zone.

    The secondary-impact owner may retain a friendly/self source. A self
    impact has no distinct actor to move away from; it invents no substitute.
    Primary Attack callers keep the strict opposing-participant guard.
    """
    _known_pair(state,actor,attacker,allow_friendly_source=allow_friendly_source)
    before=state.battlefield
    given=before is not None and actor in before.spatial.gave_ground_entity_ids
    blocked=PcGiveGroundContext(actor,attacker,False,given,None)
    if before is None or state.source.battlefield is None:
        return blocked
    injury=_injury(state,actor)
    if (getattr(injury,'dead',False) or getattr(injury,'defeated',False)
            or actor in state.exited_npc_ids
            or any(injury.conditions.has(condition) for condition in (Condition.PRONE,Condition.DEFENCELESS))):
        return blocked
    from towr.domain.pc_briarroot_models import briarroot_allows_give_ground
    if not briarroot_allows_give_ground(state,actor):
        return blocked
    # This personal injury makes every displacement Difficult Terrain (PG190),
    # so it cannot be laundered through a merely open destination Zone.
    if type(injury) is CharacterInjuryState:
        from towr.domain.pc_heavy_wound_models import restriction_sources
        if restriction_sources(injury,WoundRestriction.MOVEMENT_IS_DIFFICULT_TERRAIN):
            return blocked
    from towr.domain.pc_battlefield_movement_models import aerialmovement_permission,movement_keeps_briarroot_close
    from towr.domain.pc_scene_feature_models import difficult_terrain_crossed
    origin=before.spatial.placement_for(actor).zone_id
    source=GiveGroundRequest(state.source.id+':give-ground-query:'+actor+':'+attacker)
    candidates=[]
    for destination in before.spatial.graph.adjacent_zone_ids(origin):
        if not aerialmovement_permission(state,actor,(destination,)):
            continue
        flying=any(battlefield_is_midair(before,zone,zone=True) for zone in (origin,destination))
        if difficult_terrain_crossed(state,actor,before,(destination,),moved=True,flying=flying):
            continue
        request=GiveGroundResolutionRequest(source,before.spatial,actor,destination,injury.conditions,
            away_from_entity_id=None if actor==attacker else attacker,
            enemy_entity_ids=_enemies(state,actor))
        try:
            actual=resolve_give_ground(request)
        except ValueError:
            continue
        following=with_actor_placement(before,actor,destination)
        following=replace(following,spatial=actual.state)
        if not movement_keeps_briarroot_close(state,actor,following):
            continue
        candidates.append((actual.entered_enemy_zone,destination))
    if not candidates:
        return blocked
    destination=min(candidates)[1]
    return PcGiveGroundContext(actor,attacker,True,given,destination)


class _AttackDecisions:
    def __init__(self,state,request,base):
        self.state=state
        self.request=request
        self.base=base

    def __getattr__(self,name):
        return getattr(self.base,name)

    def choose_repeated_stagger(self,*,request,allowed_choices):
        if request.id!=self.request.kernel_request.id+':stagger':
            return self.base.choose_repeated_stagger(request=request,allowed_choices=allowed_choices)
        target=self.request.target_id
        if target in self.state.source.pc_activation_order:
            from towr.domain.pc_melee_models import PcMeleePolicy
            automatic=self.state.source.participant(target).policy is PcMeleePolicy.AUTOMATIC_COMBAT
        else:
            automatic=self.state.enemy(target).definition.generated_components is not None
        if not automatic:
            return self.base.choose_repeated_stagger(request=request,allowed_choices=allowed_choices)
        context=pc_give_ground_context(self.state,target,self.request.actor_id)
        for choice in (StaggerChoice.GIVE_GROUND,StaggerChoice.FALL_PRONE,StaggerChoice.SUFFER_WOUND):
            if choice in allowed_choices and (choice is not StaggerChoice.GIVE_GROUND or context.can_leave):
                return choice
        raise ValueError('the actual repeated-Stagger source has no legal reaction')


def pc_attack_decisions(state,request,base):
    """Adapt only this actual primary K1 Stagger; every other decision is delegated."""
    from towr.domain.action_execution_models import AttackActionExecutionRequest
    from towr.domain.pc_demigryph_models import PcDemigryphStrikeRequest
    if type(request) not in (AttackActionExecutionRequest,PcDemigryphStrikeRequest):
        raise TypeError('Give Ground decisions require an exact actual Attack or Demigryph strike source')
    replace(request)
    _known_pair(state,request.target_id,request.actor_id)
    return _AttackDecisions(state,request,base)


def _source_attack(state,resolution_id):
    from towr.domain.pc_melee_result_models import PcAttackProof
    from towr.domain.pc_demigryph_models import PcDemigryphStrikeProof,pc_kernel_resolution
    for index in range(len(state.history)-1,-1,-1):
        proof=state.history[index]
        if type(proof) in (PcAttackProof,PcDemigryphStrikeProof) and proof.request.kernel_request.id==resolution_id:
            return index,proof,pc_kernel_resolution(proof)
    raise ValueError('Give Ground continuation lacks its actual journaled K1 Attack')


def _check_attack(attack,source):
    from towr.domain.pc_melee_result_models import PcAttackProof
    from towr.domain.pc_demigryph_models import PcDemigryphStrikeProof,pc_kernel_resolution
    if type(attack) not in (PcAttackProof,PcDemigryphStrikeProof):
        raise TypeError('Give Ground retains its exact actual K1 strike family')
    replace(attack.request)
    if (attack.request.kernel_request.id!=source.resolution_id
            or source not in pc_kernel_resolution(attack).follow_ups):
        raise ValueError('Give Ground lost the actual K1 strike that requested it')


@dataclass(frozen=True,slots=True)
class PcGiveGroundProof:
    attack_index: int
    attack: PcAttackProof | PcDemigryphStrikeProof
    request: GiveGroundResolutionRequest
    result: GiveGroundResolutionResult
    previous: PcBattlefieldState
    state: PcBattlefieldState

    @property
    def actor_id(self):return self.request.mover_id

    def __post_init__(self):
        if type(self.attack_index) is not int or self.attack_index<0:
            raise TypeError('Give Ground needs its exact Attack journal index')
        if type(self.request) is not GiveGroundResolutionRequest or type(self.result) is not GiveGroundResolutionResult:
            raise TypeError('Give Ground requires its exact K1 source and movement result')
        if type(self.previous) is not PcBattlefieldState or type(self.state) is not PcBattlefieldState:
            raise TypeError('Give Ground requires the full exact before/after battlefield')
        for record in (self.request,self.result,self.previous,self.state):replace(record)
        _check_attack(self.attack,self.request.source)
        if (self.request.mover_id!=self.attack.request.target_id
                or self.request.away_from_entity_id!=self.attack.request.actor_id):
            raise ValueError('Give Ground changed its actual source attacker or moving target')
        if self.request.state!=self.previous.spatial or self.result!=resolve_give_ground(self.request):
            raise ValueError('Give Ground changed its actual K1 spatial source or result')
        after=with_actor_placement(self.previous,self.request.mover_id,self.request.destination_zone_id)
        after=replace(after,spatial=self.result.state)
        if self.state!=after:
            raise ValueError('Give Ground changed another actor, Close relation or movement resource')


@dataclass(frozen=True,slots=True)
class PcAfterGiveGroundProof:
    attack_index: int
    attack: PcAttackProof | PcDemigryphStrikeProof
    request: ConditionAfterGiveGroundRequest
    previous: CharacterInjuryState | ProfileInjuryState
    result: ConditionAfterGiveGroundResult

    @property
    def actor_id(self):return self.attack.request.target_id

    def __post_init__(self):
        if type(self.attack_index) is not int or self.attack_index<0:
            raise TypeError('post-Give-Ground Condition needs its exact Attack journal index')
        if type(self.request) is not ConditionAfterGiveGroundRequest or type(self.result) is not ConditionAfterGiveGroundResult:
            raise TypeError('post-Give-Ground Condition requires its exact K1 source/result')
        if type(self.previous) not in (CharacterInjuryState,ProfileInjuryState):
            raise TypeError('post-Give-Ground Condition needs the actual typed injury state')
        replace(self.request);replace(self.previous)
        _check_attack(self.attack,self.request)
        if self.result!=resolve_condition_after_give_ground(self.request,self.previous):
            raise ValueError('post-Give-Ground Condition changed its source or real effect')


def expected_pc_give_ground(state):
    if not state.pending or state.pending_wound is not None:
        return None
    source=state.pending[0]
    if type(source) not in (GiveGroundRequest,ConditionAfterGiveGroundRequest):
        return None
    replace(source)
    index,attack,result=_source_attack(state,source.resolution_id)
    if source not in result.follow_ups:
        raise ValueError('Give Ground pending source is absent from its actual K1 Attack result')
    actor,attacker=attack.request.target_id,attack.request.actor_id
    if type(source) is ConditionAfterGiveGroundRequest:
        if not any(type(proof) is PcGiveGroundProof and proof.attack_index==index for proof in state.history[index+1:]):
            raise ValueError('post-Give-Ground Condition must follow its actual completed movement')
        injury=_injury(state,actor)
        return PcAfterGiveGroundProof(index,attack,source,injury,resolve_condition_after_give_ground(source,injury))
    context=pc_give_ground_context(state,actor,attacker)
    if not context.can_leave:
        raise ValueError('the chosen Give Ground has no actual legal adjacent route')
    request=GiveGroundResolutionRequest(source,state.battlefield.spatial,actor,context.destination_zone_id,
        _injury(state,actor).conditions,away_from_entity_id=attacker,enemy_entity_ids=_enemies(state,actor))
    actual=resolve_give_ground(request)
    following=with_actor_placement(state.battlefield,actor,request.destination_zone_id)
    following=replace(following,spatial=actual.state)
    return PcGiveGroundProof(index,attack,request,actual,state.battlefield,following)


def pc_give_ground_pending_actor(state):
    """Only an actual K1 continuation may extend the pending queue to an NPC."""
    if not state.pending or state.pending_wound is not None:
        return None
    source=state.pending[0]
    if type(source) not in (GiveGroundRequest,ConditionAfterGiveGroundRequest):
        return None
    replace(source)
    index,attack,result=_source_attack(state,source.resolution_id)
    if source not in result.follow_ups:
        raise ValueError('Give Ground pending actor lost its actual K1 follow-up source')
    if type(source) is ConditionAfterGiveGroundRequest and not any(
            type(proof) is PcGiveGroundProof and proof.attack_index==index for proof in state.history[index+1:]):
        raise ValueError('post-Give-Ground pending actor lacks its actual movement')
    return attack.request.target_id


def project_pc_give_ground(state,proof):
    expected=expected_pc_give_ground(state)
    from towr.domain.pc_melee_result_models import validate_pc_melee_source_types,_party_update,_enemy_update
    if expected is None or proof!=expected:
        raise ValueError('Give Ground proof is replayed, detached or changed its actual mandatory source')
    validate_pc_melee_source_types(proof,expected)
    injury=(replace(_injury(state,proof.actor_id),conditions=proof.result.conditions)
        if type(proof) is PcGiveGroundProof else proof.result.state)
    updates=dict(pending=state.pending[1:],pending_actor_id=proof.actor_id if state.pending[1:] else None)
    if type(proof) is PcGiveGroundProof:updates['battlefield']=proof.state
    if proof.actor_id in state.source.pc_activation_order:
        updates['party']=_party_update(state,proof.actor_id,injury=injury)
    else:
        updates['enemies']=_enemy_update(state,proof.actor_id,injury)
    return updates


GIVE_GROUND_PROOFS=(PcGiveGroundProof,PcAfterGiveGroundProof)
