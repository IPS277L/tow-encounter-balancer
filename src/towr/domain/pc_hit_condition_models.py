"""Closed PC hit effects: early Prone and independent post-Damage Drained."""
from __future__ import annotations

from dataclasses import dataclass,replace
from typing import TYPE_CHECKING

from towr.domain.attack_models import AttackOutcome,ConditionOnHitSpec,ProneBeforeGiveGroundSpec
from towr.domain.condition_models import Condition,ConditionApplicationResult,ConditionState,EffectClassification
from towr.domain.resolution_models import TargetInjuryPolicy

if TYPE_CHECKING:
    from towr.domain.action_execution_models import AttackActionExecutionRequest
    from towr.domain.injury_models import CharacterInjuryState
    from towr.domain.resolution_models import KernelAttackRequest,ResolutionResult


CRUSHING_WEIGHT_PRONE_RULE_ID = 'RULE-PROFILE-CREATURE-010:crushing-weight-prone'


def validate_pc_hit_effects(effects: tuple[ConditionOnHitSpec | ProneBeforeGiveGroundSpec,...]) -> None:
    if type(effects) is not tuple or len(effects)>1:
        raise ValueError('PC NPC attacks support at most one admitted hit effect')
    for effect in effects:
        if type(effect) not in (ConditionOnHitSpec,ProneBeforeGiveGroundSpec):
            raise TypeError('PC hit effect must retain its exact admitted type')
        replace(effect)
        if type(effect.rule_id) is not str or not effect.rule_id.strip():
            raise TypeError('PC hit effect requires its exact source Rule ID')
        if type(effect) is ProneBeforeGiveGroundSpec:
            if type(effect.affects_monstrosities) is not bool:
                raise TypeError('pre-Stagger Prone requires its exact bool flag')
            if effect.rule_id!=CRUSHING_WEIGHT_PRONE_RULE_ID or not effect.affects_monstrosities:
                raise ValueError('PC pre-Stagger Prone requires canonical Crushing Weight semantics')
        elif (type(effect.condition) is not Condition or effect.condition is not Condition.DRAINED
                or type(effect.classification) is not EffectClassification
                or effect.classification is not EffectClassification.UNCLASSIFIED):
            raise ValueError('PC on-hit effect supports unclassified Drained only')


def pc_pre_stagger_target(kernel: KernelAttackRequest,outcome: AttackOutcome):
    """Project early Prone before the Stagger/Wound branch, without a late receipt."""
    effects = kernel.attack.secondary_effects
    validate_pc_hit_effects(effects)
    before = kernel.target_state
    if outcome is not AttackOutcome.HIT or not effects or type(effects[0]) is not ProneBeforeGiveGroundSpec:
        return before,()
    if kernel.target_policy is not TargetInjuryPolicy.PLAYER or kernel.target_effect_immunities:
        raise ValueError('bounded early Prone requires its ordinary PLAYER target without immunities')
    return replace(before,conditions=before.conditions.with_condition(Condition.PRONE)),(effects[0].rule_id,)


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
    effects = kernel.attack.secondary_effects
    validate_pc_hit_effects(effects)
    if outcome is not AttackOutcome.HIT or not effects:
        return base,(),()
    if kernel.target_policy is not TargetInjuryPolicy.PLAYER or kernel.target_effect_immunities:
        raise ValueError('bounded PC hit Condition requires its ordinary PLAYER target without immunities')
    effect, = effects
    if type(effect) is ProneBeforeGiveGroundSpec:
        # Already applied before Stagger/Wound. Reapplying after Damage would
        # conceal a false Wound source and change the Near Miss retained state.
        return base,(),(effect.rule_id,)
    conditions = base.conditions.with_condition(Condition.DRAINED)
    application = ConditionApplicationResult(kernel.id+':'+effect.rule_id+':on-hit-condition',conditions,
        Condition.DRAINED,base.conditions.has(Condition.DRAINED),False,effect.rule_id,None,(effect.rule_id,))
    return replace(base,conditions=conditions),(application,),(effect.rule_id,)


def hit_condition_sources_from_attack(request: AttackActionExecutionRequest,result: ResolutionResult
        ) -> tuple[PcHitConditionSource,...]:
    from towr.domain.pc_net_models import is_net_impact
    if is_net_impact(request.kernel_request.attack.impact_spec):
        return ()  # Net has its own primary-impact cause bank.
    effects = request.kernel_request.attack.secondary_effects
    validate_pc_hit_effects(effects)
    if result.attack.outcome is not AttackOutcome.HIT or not effects:
        if result.condition_applications:
            raise ValueError('no successful source hit can invent a Condition application')
        return ()
    if type(effects[0]) is ProneBeforeGiveGroundSpec:
        if result.condition_applications:
            raise ValueError('pre-Stagger Prone cannot carry a post-Damage application')
        return ()
    if type(result.condition_applications) is not tuple or len(result.condition_applications)!=1:
        raise ValueError('one actual successful on-hit effect requires one application receipt')
    effect, = effects
    application, = result.condition_applications
    if type(application) is not ConditionApplicationResult:
        raise TypeError('hit Condition receipt must be its exact typed result')
    if (type(application.was_already_present) is not bool or type(application.blocked) is not bool
            or application.blocked or application.blocked_by_rule_id is not None
            or application.condition is not Condition.DRAINED
            or application.source_rule_id!=effect.rule_id
            or application.request_id!=request.kernel_request.id+':'+effect.rule_id+':on-hit-condition'
            or type(application.applied_rule_ids) is not tuple or application.applied_rule_ids!=(effect.rule_id,)
            or any(type(rule) is not str for rule in application.applied_rule_ids)
            or type(application.state) is not ConditionState
            or type(application.state.conditions) is not frozenset
            or any(type(condition) is not Condition for condition in application.state.conditions)
            or not application.state.has(Condition.DRAINED)):
        raise ValueError('hit Condition receipt changed its actual unblocked application source')
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
