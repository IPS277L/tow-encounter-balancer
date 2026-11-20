"""Closed PC hit effects: early Prone and independent post-Damage Drained."""
from __future__ import annotations

from dataclasses import dataclass,replace
from typing import TYPE_CHECKING

from towr.domain.attack_models import (AttackOutcome,ConditionOnHitSpec,ProneBeforeGiveGroundSpec,
    NearbyTargetsStaggerSpec,ConditionAfterGiveGroundSpec)
from towr.domain.condition_models import Condition,ConditionApplicationResult,ConditionState,EffectClassification
from towr.domain.resolution_models import TargetInjuryPolicy
from towr.domain.pc_mount_models import (HORSE_NOBLE_STEED_RULE_ID,PEGASUS_KNIGHTS_RULE_ID,
    DEMIGRYPH_FEARSOME_RULE_ID,SKELETAL_STEED_FRIGHTENING_RULE_ID)

if TYPE_CHECKING:
    from towr.domain.action_execution_models import AttackActionExecutionRequest
    from towr.domain.injury_models import CharacterInjuryState
    from towr.domain.resolution_models import KernelAttackRequest,ResolutionResult


CRUSHING_WEIGHT_PRONE_RULE_ID = 'RULE-PROFILE-CREATURE-010:crushing-weight-prone'


def validate_pc_hit_effects(effects: tuple[ConditionOnHitSpec | ProneBeforeGiveGroundSpec,...]) -> None:
    if (type(effects) is not tuple or len(set(effects))!=len(effects)
            or sum(type(effect) is ProneBeforeGiveGroundSpec for effect in effects)>1):
        raise ValueError('hit effects require distinct complete Condition sources and one early Prone')
    for effect in effects:
        if type(effect) not in (ConditionOnHitSpec,ProneBeforeGiveGroundSpec):
            raise TypeError('PC hit effect must retain its exact admitted type')
        replace(effect)
        if type(effect.rule_id) is not str or not effect.rule_id.strip():
            raise TypeError('PC hit effect requires its exact source Rule ID')
        if type(effect) is ProneBeforeGiveGroundSpec:
            if type(effect.affects_monstrosities) is not bool:
                raise TypeError('pre-Stagger Prone requires its exact bool flag')
            if not ((effect.rule_id==CRUSHING_WEIGHT_PRONE_RULE_ID and effect.affects_monstrosities)
                    or (effect.rule_id==HORSE_NOBLE_STEED_RULE_ID and not effect.affects_monstrosities)
                    or (effect.rule_id==PEGASUS_KNIGHTS_RULE_ID and effect.affects_monstrosities)):
                raise ValueError('pre-Stagger Prone requires its complete Crushing Weight or Noble Steed source')
        elif (type(effect.condition) is not Condition
                or (effect.condition is not Condition.DRAINED and not (
                    effect.condition is Condition.ABLAZE and effect.rule_id=='RULE-MAGIC-ITEM-003:dragon-fire-arrow'))
                or type(effect.classification) is not EffectClassification
                or effect.classification is not EffectClassification.UNCLASSIFIED):
            raise ValueError('on-hit effect requires its admitted Drained or Dragon fire source')


def _primary_hit_effects(effects):
    # Nearby has a separate ordered target owner; it never modifies primary again.
    from towr.domain.ranged_weapon_attack_preparation_models import BLUNDERBUSS_NEARBY_STAGGER_RULE_ID
    if type(effects) is not tuple or len(set(effects))!=len(effects):
        raise ValueError('primary hit effects require unique complete typed sources')
    primary=[]
    for effect in effects:
        if type(effect) is NearbyTargetsStaggerSpec:
            replace(effect)
            if effect.rule_id!=BLUNDERBUSS_NEARBY_STAGGER_RULE_ID:
                raise ValueError('nearby effect lost its actual Blunderbuss source')
        elif type(effect) is ConditionAfterGiveGroundSpec:
            replace(effect)
            if (effect.condition is not Condition.BROKEN or effect.rule_id not in
                    (DEMIGRYPH_FEARSOME_RULE_ID,SKELETAL_STEED_FRIGHTENING_RULE_ID)):
                raise ValueError('after-Give-Ground Condition lost its actual mounted ability')
            # The current controller chooses Wound instead of Give Ground.
            # Its exact Stagger receipt is validated by the shared projection;
            # this effect therefore has no on-hit Condition application.
        else:
            primary.append(effect)
    result=tuple(primary)
    validate_pc_hit_effects(result)
    return result


def pc_pre_stagger_target(kernel: KernelAttackRequest,outcome: AttackOutcome):
    """Project early Prone before the Stagger/Wound branch, without a late receipt."""
    effects = _primary_hit_effects(kernel.attack.secondary_effects)
    before = kernel.target_state
    effect=next((effect for effect in effects if type(effect) is ProneBeforeGiveGroundSpec),None)
    if outcome is not AttackOutcome.HIT or effect is None:
        return before,()
    if kernel.target_policy is TargetInjuryPolicy.MONSTROSITY and not effect.affects_monstrosities:
        return before,()
    return replace(before,conditions=before.conditions.with_condition(Condition.PRONE)),(effect.rule_id,)


@dataclass(frozen=True,slots=True)
class PcHitConditionSource:
    attack_id: str
    attacker_id: str
    target_id: str
    application_id: str
    rule_id: str
    condition: Condition

    def __post_init__(self):
        if any(type(value) is not str or not value.strip() for value in
                (self.attack_id,self.attacker_id,self.target_id,self.application_id,self.rule_id)):
            raise TypeError('hit Condition source IDs must be exact nonempty strings')
        if self.attacker_id==self.target_id:
            raise ValueError('hit Condition source cannot target its own attacker')
        if type(self.condition) is not Condition or self.condition is not Condition.DRAINED:
            raise TypeError('hit Condition source must retain exact Drained')


def expected_pc_hit_target(kernel: KernelAttackRequest,outcome: AttackOutcome,base):
    """Project K1's single post-damage application without executing a rule or RNG."""
    effects = _primary_hit_effects(kernel.attack.secondary_effects)
    if outcome is not AttackOutcome.HIT or not effects:
        return base,(),()
    early_rules=tuple(effect.rule_id for effect in effects if type(effect) is ProneBeforeGiveGroundSpec)
    post_effects=tuple(effect for effect in effects if type(effect) is ConditionOnHitSpec)
    if not post_effects:
        return base,(),early_rules
    # The admitted post-hit sources above are UNCLASSIFIED. A psychological
    # immunity does not block these effects or the physical early Prone.
    conditions,applications,rules=base.conditions,[],list(early_rules)
    for effect in post_effects:
        previous=conditions
        conditions=conditions.with_condition(effect.condition)
        applications.append(ConditionApplicationResult(kernel.id+':'+effect.rule_id+':on-hit-condition',conditions,
            effect.condition,previous.has(effect.condition),False,effect.rule_id,None,(effect.rule_id,)))
        rules.append(effect.rule_id)
    return replace(base,conditions=conditions),tuple(applications),tuple(rules)


def hit_condition_sources_from_attack(request: AttackActionExecutionRequest,result: ResolutionResult
        ) -> tuple[PcHitConditionSource,...]:
    from towr.domain.pc_net_models import is_net_impact
    if is_net_impact(request.kernel_request.attack.impact_spec):
        return ()  # Net has its own primary-impact cause bank.
    from towr.domain.weapon_impact_preparation import is_stagger_weapon_impact,is_oil_impact
    if (is_stagger_weapon_impact(request.kernel_request.attack.impact_spec)
            or is_oil_impact(request.kernel_request.attack.impact_spec)) and result.attack.outcome is AttackOutcome.HIT:
        # The primary application is authenticated by the impact owner; it is
        # not an additional ongoing Drained source or a second application.
        result=replace(result,condition_applications=result.condition_applications[1:])
    effects = _primary_hit_effects(request.kernel_request.attack.secondary_effects)
    if result.attack.outcome is not AttackOutcome.HIT or not effects:
        if result.condition_applications:
            raise ValueError('no successful source hit can invent a Condition application')
        return ()
    effects=tuple(effect for effect in effects if type(effect) is ConditionOnHitSpec)
    if not effects:
        if result.condition_applications:
            raise ValueError('pre-Stagger Prone cannot carry a post-Damage application')
        return ()
    if type(result.condition_applications) is not tuple or len(result.condition_applications)!=len(effects):
        raise ValueError('each actual successful on-hit effect requires its one application receipt')
    sources=[]
    for effect,application in zip(effects,result.condition_applications,strict=True):
        sources.extend(_hit_source(request,effect,application))
    return tuple(sources)


def _hit_source(request,effect,application):
    if type(application) is not ConditionApplicationResult:
        raise TypeError('hit Condition receipt must be its exact typed result')
    if (type(application.was_already_present) is not bool or type(application.blocked) is not bool
            or application.blocked or application.blocked_by_rule_id is not None
            or application.condition is not effect.condition
            or application.source_rule_id!=effect.rule_id
            or application.request_id!=request.kernel_request.id+':'+effect.rule_id+':on-hit-condition'
            or type(application.applied_rule_ids) is not tuple or application.applied_rule_ids!=(effect.rule_id,)
            or any(type(rule) is not str for rule in application.applied_rule_ids)
            or type(application.state) is not ConditionState
            or type(application.state.conditions) is not frozenset
            or any(type(condition) is not Condition for condition in application.state.conditions)
            or not application.state.has(effect.condition)):
        raise ValueError('hit Condition receipt changed its actual unblocked application source')
    if effect.condition is not Condition.DRAINED:
        return ()  # Ablaze has its own mandatory fire owner, not a Drained cause.
    return (PcHitConditionSource(request.id,request.actor_id,request.target_id,
        application.request_id,application.source_rule_id,application.condition),)


def retain_pc_hit_conditions(injury: CharacterInjuryState,sources: tuple[PcHitConditionSource,...]
        ) -> CharacterInjuryState:
    """Keep already validated independent causes after a legitimate projection/expiry."""
    if not sources:
        return injury
    for source in sources:
        if type(source) is not PcHitConditionSource:
            raise TypeError('hit Condition bank requires exact typed sources')
        replace(source)
    return replace(injury,conditions=injury.conditions.with_condition(Condition.DRAINED))
