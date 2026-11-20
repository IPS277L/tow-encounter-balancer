"""One Bash Attack permission from a real new Brawn Staggered, PG1.4 III73.

This is an immediate-strike source, not an ordinary action slot. The encounter
owner binds the inventory and Brawn profile to the actual actor, checks owned
Talents and current liveness, and consumes the source once. Constructing this
grant never selects or executes its subsequent Melee attack.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace

from towr.domain.action_execution_models import AttackActionExecutionRequest, AttackActionExecutionResult
from towr.domain.attack_models import (
    AttackOutcome, AttackRequest, AttackResult, ConditionImpactSpec, DamageImpactSpec,
    DamageModifier, DamageProfile, ResilienceModifier, ResilienceProfile,
)
from towr.domain.condition_models import Condition, ConditionState, StaggerOutcome, StaggerResult
from towr.domain.injury_models import (
    CharacterInjuryState, ProfileInjuryState, WoundConditionEffect, WoundRecord, WoundRestrictionEffect,
)
from towr.domain.resolution_models import KernelAttackRequest, ResolutionResult, TargetInjuryPolicy
from towr.domain.talent_catalog import TalentId
from towr.domain.talent_models import AcquiredTalent
from towr.domain.test_models import (
    DiceModifier, InlineProfile, QualityModifier, RerollLock, RerollTrace, RollTrace, Skill,
    SuccessModifier, TestProfile, TestQuality, TestRequest, TestResult, _expected_initial_roll_parameters,
)
from towr.domain.turn_models import (
    ActionExecutionReceipt, CombatActionDeclaration, CombatActionSlot, CombatRoundState, CombatSide,
    CombatTurnParticipant, CombatTurnState,
)
from towr.domain.weapon_catalog import WeaponKind
from towr.domain.weapon_impact_preparation import UNARMED_IMPACT_RULE_ID
from towr.domain.weapon_use_models import WeaponUse


BASH_ATTACK_RULE_ID = 'RULE-TALENT-002:bash-attack'


def _same_typed(actual, expected):
    """Receipt equality must not treat bool/int or raw strings/Enums as equal."""
    if type(actual) is not type(expected):
        return False
    if is_dataclass(expected):
        return all(_same_typed(getattr(actual, field.name), getattr(expected, field.name))
            for field in fields(expected))
    if type(expected) is tuple:
        return len(actual) == len(expected) and all(_same_typed(a, b) for a, b in zip(actual, expected))
    if type(expected) is frozenset:
        return len(actual) == len(expected) and all(any(_same_typed(a, b) for b in expected) for a in actual)
    return actual == expected


def _conditions(value):
    if (type(value) is not ConditionState or type(value.conditions) is not frozenset
            or any(type(condition) is not Condition for condition in value.conditions)):
        raise TypeError('Bash Attack requires its exact immutable Conditions')
    replace(value)


def _injury(value):
    if type(value) not in (CharacterInjuryState, ProfileInjuryState):
        raise TypeError('Bash Attack requires its exact target injury source')
    _conditions(value.conditions)
    if type(value) is CharacterInjuryState:
        for name, kinds in (('wounds', (WoundRecord,)),
                ('active_wound_effects', (WoundConditionEffect, WoundRestrictionEffect))):
            values = getattr(value, name)
            if type(values) is not tuple or any(type(item) not in kinds for item in values):
                raise TypeError('Bash Attack requires canonical target Wound sources')
            for item in values:
                replace(item)
    replace(value)


def _round(value):
    if type(value) is not CombatRoundState:
        raise TypeError('Bash Attack requires its actual typed combat round')
    for name in ('participants', 'side_order', 'completed_turn_entity_ids', 'excluded_turn_entity_ids'):
        if type(getattr(value, name)) is not tuple:
            raise TypeError('Bash Attack round collections must remain immutable tuples')
    for participant in value.participants:
        if type(participant) is not CombatTurnParticipant or type(participant.side) is not CombatSide:
            raise TypeError('Bash Attack requires its exact combat participants')
        replace(participant)
    if any(type(side) is not CombatSide for side in value.side_order):
        raise TypeError('Bash Attack requires exact combat sides')
    turn = value.active_turn
    if type(turn) is not CombatTurnState or type(turn.action_slots) is not tuple:
        raise TypeError('Bash Attack requires the actual immutable source turn')
    for slot in turn.action_slots:
        if type(slot) is not CombatActionSlot or type(slot.declaration) is not CombatActionDeclaration:
            raise TypeError('Bash Attack requires its actual typed source slots')
        replace(slot.declaration)
        replace(slot)
        if slot.execution is not None:
            if type(slot.execution) is not ActionExecutionReceipt:
                raise TypeError('Bash Attack requires the exact execution receipt')
            replace(slot.execution)
    replace(turn)
    replace(value)


def _completed_test(request, result):
    """Check the recorded final dice, including legal chosen Glorious rerolls."""
    if (type(request) is not TestRequest or type(result) is not TestResult
            or type(result.trace) is not RollTrace):
        raise TypeError('Bash Attack requires the full actual completed Attack Tests')
    if type(request.profile) not in (TestProfile, InlineProfile):
        raise TypeError('Bash Attack requires an exact typed Test profile')
    replace(request.profile)
    for name, kind in (('dice_modifiers', DiceModifier), ('quality_modifiers', QualityModifier),
            ('success_modifiers', SuccessModifier), ('reroll_locks', RerollLock)):
        values = getattr(request, name)
        if type(values) is not tuple or any(type(item) is not kind for item in values):
            raise TypeError('Bash Attack requires canonical Test modifier sources')
        for item in values:
            replace(item)
            if kind is DiceModifier and type(item.bypasses_pool_cap) is not bool:
                raise TypeError('Test cap bypass requires an exact boolean')
    replace(request)
    trace = result.trace
    for name in ('base_dice', 'pool_cap', 'regular_dice_delta', 'cap_bypassing_dice',
            'dice_before_minimum', 'rolled_dice', 'threshold', 'rolled_successes', 'success_delta', 'successes'):
        if type(getattr(trace, name)) is not int:
            raise TypeError('Bash Attack Test trace counters require exact integers')
    if type(trace.minimum_die_rule_applied) is not bool or type(trace.quality) is not TestQuality:
        raise TypeError('Bash Attack Test trace flags require their exact types')
    for values in (trace.initial_values, trace.final_values):
        if type(values) is not tuple or any(type(value) is not int or not 1 <= value <= 10 for value in values):
            raise TypeError('Bash Attack Test trace requires exact recorded d10 tuples')
    if type(trace.rerolls) is not tuple or any(type(item) is not RerollTrace for item in trace.rerolls):
        raise TypeError('Bash Attack requires typed recorded rerolls')
    parameters = _expected_initial_roll_parameters(request)
    if len(trace.initial_values) != parameters[5] or len(trace.final_values) != parameters[5]:
        raise ValueError('Bash Attack changed the actual source Test pool')
    qualities = {item.quality for item in request.quality_modifiers}
    quality = next(iter(qualities)) if len(qualities) == 1 else TestQuality.NORMAL
    locked = {item.value for item in request.reroll_locks}
    eligible = tuple(index for index, value in enumerate(trace.initial_values)
        if value not in locked and (value <= parameters[6] if quality is TestQuality.GRIM else value > parameters[6]))
    indices = tuple(item.index for item in trace.rerolls)
    if any(type(index) is not int for index in indices) or indices != tuple(sorted(set(indices))):
        raise ValueError('Bash Attack rerolls require exact unique ordered indices')
    if (quality is TestQuality.NORMAL and indices
            or quality is TestQuality.GRIM and indices != eligible
            or quality is TestQuality.GLORIOUS and not set(indices) <= set(eligible)):
        raise ValueError('Bash Attack changed legal source Test reroll choices')
    final = list(trace.initial_values)
    for reroll in trace.rerolls:
        if (type(reroll.original) is not int or type(reroll.replacement) is not int
                or not 1 <= reroll.replacement <= 10 or reroll.original != final[reroll.index]):
            raise ValueError('Bash Attack changed an actual rerolled die')
        final[reroll.index] = reroll.replacement
    successes = sum(value <= parameters[6] for value in final)
    delta = sum(item.amount for item in request.success_modifiers)
    rules = tuple(item.rule_id for values in (request.dice_modifiers, request.quality_modifiers,
        request.success_modifiers, request.reroll_locks) for item in values)
    expected = RollTrace(request.id, *parameters[:6], parameters[6], parameters[7], quality,
        trace.initial_values, trace.rerolls, tuple(final), successes, delta, max(0, successes + delta), rules)
    if not _same_typed(trace, expected):
        raise ValueError('Bash Attack Test trace differs from its actual complete source')


class _NoRolls:
    def randint(self, start, end):
        raise ValueError('a new Bash Attack grant cannot resolve a Wound or roll another Test')


@dataclass(frozen=True, slots=True)
class BashAttackGrant:
    source_request: AttackActionExecutionRequest
    source_execution: AttackActionExecutionResult
    weapon_use: WeaponUse
    talent: AcquiredTalent

    def __post_init__(self):
        if (type(self.source_request) is not AttackActionExecutionRequest
                or type(self.source_execution) is not AttackActionExecutionResult):
            raise TypeError('Bash Attack requires its complete typed source Attack request and execution')
        request, execution = self.source_request, self.source_execution
        for value in (request.id, request.actor_id, request.target_id):
            if type(value) is not str or not value.strip():
                raise TypeError('Bash Attack requires exact source and participant identifiers')
        _round(request.state)
        _round(execution.previous_state)
        _round(execution.state)
        replace(request)
        replace(execution)
        if type(self.weapon_use) is not WeaponUse:
            raise TypeError('Bash Attack requires the actual selected WeaponUse')
        replace(self.weapon_use)
        if (self.weapon_use.actor_id != request.actor_id or self.weapon_use.skill is not Skill.BRAWN
                or self.weapon_use.kind not in (WeaponKind.UNARMED, WeaponKind.KNUCKLEDUSTERS)):
            raise ValueError('Bash Attack requires this actor\'s actual Brawn weapon mode')
        if type(self.talent) is not AcquiredTalent:
            raise TypeError('Bash Attack requires its actual acquired Talent')
        replace(self.talent)
        if self.talent.id is not TalentId.BASH_ATTACK:
            raise ValueError('another Talent cannot authorise Bash Attack')
        kernel = request.kernel_request
        if type(kernel) is not KernelAttackRequest or type(kernel.attack) is not AttackRequest:
            raise TypeError('Bash Attack requires the exact bound kernel and Attack sources')
        for value in (kernel.id, kernel.target_id, kernel.attack.id):
            if type(value) is not str or not value.strip():
                raise TypeError('Bash Attack requires exact kernel and Attack identifiers')
        if type(kernel.target_policy) is not TargetInjuryPolicy:
            raise TypeError('Bash Attack requires the actual typed target injury policy')
        _injury(kernel.target_state)
        replace(kernel.attack)
        replace(kernel)
        if (not kernel.physical_attack or not kernel.attack.is_close_range
                or request.actor_id == request.target_id):
            raise ValueError('Bash Attack requires an actual physical Close Brawn attack on another actor')
        impact = kernel.attack.impact_spec
        if self.weapon_use.kind is WeaponKind.UNARMED:
            if (type(impact) is not ConditionImpactSpec
                    or impact != ConditionImpactSpec(Condition.STAGGERED, UNARMED_IMPACT_RULE_ID)):
                raise ValueError('Unarmed Bash requires its actual Staggered impact, not Shove or Dismount')
            replace(impact)
        else:
            if type(impact) is not DamageImpactSpec:
                raise ValueError('Knuckledusters Bash requires its actual numeric Damage impact')
            for value, kind in ((impact.damage, DamageProfile), (impact.resilience, ResilienceProfile)):
                if type(value) is not kind:
                    raise TypeError('Knuckledusters requires its exact Damage and Resilience sources')
                replace(value)
            for values, kind in ((impact.damage_modifiers, DamageModifier),
                    (impact.resilience_modifiers, ResilienceModifier)):
                if type(values) is not tuple or any(type(item) is not kind for item in values):
                    raise TypeError('Knuckledusters requires canonical typed impact modifiers')
                for item in values:
                    replace(item)
            replace(impact)
        resolution = execution.resolution
        if type(resolution) is not ResolutionResult or type(resolution.attack) is not AttackResult:
            raise TypeError('Bash Attack requires its actual typed kernel resolution')
        _injury(resolution.target_state)
        stagger = resolution.stagger
        if (resolution.attack.outcome is not AttackOutcome.HIT or type(stagger) is not StaggerResult
                or stagger.outcome is not StaggerOutcome.CONDITION_ADDED
                or kernel.target_state.conditions.has(Condition.STAGGERED)
                or not resolution.target_state.conditions.has(Condition.STAGGERED)):
            raise ValueError('Bash Attack requires a genuinely new Staggered from its Brawn HIT')
        _completed_test(kernel.attack.attacker_test, resolution.attack.attacker_test)
        if kernel.attack.defender_test is None:
            if resolution.attack.defender_test is not None:
                raise ValueError('an unopposed Bash source cannot invent a defender Test')
        else:
            _completed_test(kernel.attack.defender_test, resolution.attack.defender_test)
        # Reuse the actual pure owners: no new roll, decision or ordinary slot.
        from towr.rules.attack_action_execution import _complete_attack_action, _validate_attack_action_slot
        from towr.rules.attack_resolution import _resolve_attack_after_tests
        from towr.rules.kernel import _resolve_kernel_attack_after_test
        _validate_attack_action_slot(request)
        attack = _resolve_attack_after_tests(kernel.attack, resolution.attack.attacker_test,
            resolution.attack.defender_test)
        if not _same_typed(resolution.attack, attack):
            raise ValueError('Bash Attack changed its source Attack outcome or impact comparison')
        expected_resolution = _resolve_kernel_attack_after_test(kernel, attack, _NoRolls())
        if not _same_typed(resolution, expected_resolution):
            raise ValueError('Bash Attack changed its actual first-Staggered kernel transition')
        if not _same_typed(execution, _complete_attack_action(request, expected_resolution)):
            raise ValueError('Bash Attack changed its full source action or execution receipt')

    @property
    def id(self) -> str:
        return self.source_request.id + ':bash-attack'

    @property
    def actor_id(self) -> str:
        return self.source_request.actor_id

    @property
    def target_id(self) -> str:
        return self.source_request.target_id

    @property
    def round_number(self) -> int:
        return self.source_request.state.round_number

    @property
    def rule_id(self) -> str:
        return BASH_ATTACK_RULE_ID
