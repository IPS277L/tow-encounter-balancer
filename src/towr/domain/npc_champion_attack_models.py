"""One ordinary Minion attack against a Champion, with Wound completion.

PG1.4 Rules pp118-121, Wounds Table pp190-191; GM1.1 Champions p92.
This adapter owns no Casting, spatial movement, or encounter terminal policy.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from towr.domain.action_execution_models import AttackActionExecutionRequest, AttackActionExecutionResult
from towr.domain.attack_models import AttackOutcome, AttackResult, DamageImpactSpec, ImpactOutcome, MissConsequence
from towr.domain.condition_models import Condition, ConditionState, StaggerOutcome, StaggerResult
from towr.domain.crushed_rib_test_models import (
    CrushedRibTestPreparationResult, CrushedRibTestResult, CrushedRibCastingResult,
    _injury as _crushed_injury, _test as _crushed_test, _completed_test as _completed_crushed_test,
)
from towr.domain.infection_models import DailyWoundState
from towr.domain.injury_models import CharacterInjuryState, CharacterWoundType
from towr.domain.npc_attack_preparation_models import NpcProtectedAttackPreparationResult
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_prone_shooting import _validate_prone_shooting
from towr.domain.resolution_models import (
    AttackerStaggerRequest, FollowUpRequest, KernelAttackRequest, ResolutionResult, TargetInjuryPolicy,
)
from towr.domain.turn_models import (
    ActionSlotGrant, CombatActionDeclaration, CombatActionKind, CombatRoundState,
)
from towr.domain.test_models import InitialTestRoll, RollTrace, Skill, TestQuality, TestRequest, TestResult
from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleCompletionResult

if TYPE_CHECKING:
    from towr.domain.npc_stationary_wound_models import NpcStationaryWoundContext


@dataclass(frozen=True, slots=True)
class NpcChampionAttackState:
    roster: NpcRoster
    round_state: CombatRoundState
    daily_wounds: DailyWoundState
    consumed_execution_ids: tuple[str, ...] = ()
    consumed_wound_roll_ids: tuple[str, ...] = ()
    pending: NpcChampionAttackResult | None = None

    def __post_init__(self) -> None:
        for value, kind in ((self.roster, NpcRoster), (self.round_state, CombatRoundState),
                            (self.daily_wounds, DailyWoundState)):
            _typed(value, kind)
        for name in ('consumed_execution_ids', 'consumed_wound_roll_ids'):
            value = getattr(self, name)
            if not isinstance(value, (tuple, list)):
                raise TypeError(f'{name} must be an ordered tuple or list')
            identifiers = tuple(value)
            if any(not isinstance(i, str) or not i.strip() for i in identifiers):
                raise ValueError(f'{name} requires nonblank strings')
            if len(set(identifiers)) != len(identifiers):
                raise ValueError(f'{name} must be unique')
            object.__setattr__(self, name, identifiers)
        if self.roster.turn_participants != self.round_state.participants:
            raise ValueError('roster must match ordered round participants')
        champion = self.roster.participant(self.daily_wounds.target_id)
        if champion.definition.injury_policy is not TargetInjuryPolicy.CHAMPION:
            raise ValueError('daily Wound owner must be a Champion')
        wounds = {w.sequence: w for w in champion.state.injury.wounds}
        for receipt in self.daily_wounds.receipts:
            wound = wounds.get(receipt.wound.sequence)
            if wound is None or (wound.entry_id, wound.table_total, wound.roll_values, wound.origin) != (
                    receipt.wound.entry_id, receipt.wound.table_total, receipt.wound.roll_values, receipt.wound.origin):
                raise ValueError('daily Wound history differs from Champion injuries')
        if self.pending is not None:
            _typed(self.pending, NpcChampionAttackResult)
            if not self.pending.pending_follow_ups:
                raise ValueError('pending attack requires unresolved follow-ups')
            if replace(self, pending=None) != self.pending._project_state(pending=None):
                raise ValueError('pending attack differs from its applied state')


@dataclass(frozen=True, slots=True)
class NpcChampionAttackRequest:
    state: NpcChampionAttackState
    preparation: NpcProtectedAttackPreparationResult
    execution: AttackActionExecutionRequest
    stationary_wounds: NpcStationaryWoundContext | None = field(default=None, kw_only=True)
    crushed_rib_preparation: CrushedRibTestPreparationResult | None = field(default=None, kw_only=True)
    crushed_rib_consumption: CrushedRibTestResult | CrushedRibCastingResult | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        for value, kind in ((self.state, NpcChampionAttackState),
                            (self.preparation, NpcProtectedAttackPreparationResult),
                            (self.execution, AttackActionExecutionRequest)):
            _typed(value, kind)
        state, execution, prepared = self.state, self.execution, self.preparation
        context = self.stationary_wounds
        crushed = self.crushed_rib_preparation is not None or self.crushed_rib_consumption is not None
        if crushed:
            _admit_crushed_rib_request(self)
        if context is not None:
            # The lower owner lacks magic/spatial/expiry chronology. Keep the
            # complete pre-action witness rather than admitting effects alone.
            from towr.domain.npc_stationary_wound_models import NpcStationaryWoundContext
            _typed(context, NpcStationaryWoundContext)
            context.validate_source(context.state, execution.target_id)
            if context.state.champion_attack != state:
                raise ValueError('stationary Champion attack differs from its full source child owner')
        if state.pending is not None:
            raise ValueError('pending attack follow-ups block another attack')
        if execution.id in state.consumed_execution_ids:
            raise ValueError('Champion attack execution was already consumed')
        if execution.state != state.round_state:
            raise ValueError('execution must use the current round snapshot')
        turn = state.round_state.active_turn
        if turn is None or turn.actor_id != execution.actor_id:
            raise ValueError('attacker must own the active turn')
        if (execution.slot_index != 1 or len(turn.action_slots) != 1
                or turn.action_slots[0].grant is not ActionSlotGrant.STANDARD
                or turn.action_slots[0].executed
                or turn.action_slots[0].declaration != CombatActionDeclaration(CombatActionKind.ATTACK)):
            raise ValueError('Champion bridge requires one unexecuted standard Attack slot')
        actor = state.roster.participant(execution.actor_id)
        target = state.roster.participant(execution.target_id)
        if (actor.definition.injury_policy is not TargetInjuryPolicy.MINION
                or target.definition.injury_policy is not TargetInjuryPolicy.CHAMPION
                or actor.state.side is target.state.side):
            raise ValueError('bridge requires an enemy Minion attacking a Champion')
        if actor.state.injury.defeated or target.state.injury.dead:
            raise ValueError('bridge requires living actor and target')
        # Additional Conditions/restrictions need dedicated current-profile adapters.
        for participant in ((actor, target) if context is None and not crushed else (actor,)):
            if not participant.state.injury.conditions.conditions <= {Condition.STAGGERED, Condition.PRONE}:
                raise ValueError('bridge currently supports only initial Staggered or standalone Prone Shooting')
        injury = target.state.injury
        if context is None and not crushed and (injury.active_wound_effects or any(not w.effect_resolved for w in injury.wounds)):
            raise ValueError('target Wound effects must be resolved and have no active restrictions')
        if state.daily_wounds.target_id != execution.target_id or state.daily_wounds.is_closed:
            raise ValueError('attack requires an open daily Wound state for this target')
        if any(r.id == execution.id + ':daily-wound' for r in state.daily_wounds.receipts):
            raise ValueError('daily Wound registration was already consumed')
        npc = prepared.npc_attack
        source = npc.source_request
        if (npc.snapshot != actor.attack_snapshot(npc.snapshot.id)
                or npc.target_id != execution.target_id
                or source.target_resilience != target.state.current_resilience
                or source.attacker_is_staggered != actor.state.injury.conditions.has(Condition.STAGGERED)):
            raise ValueError('attack preparation has stale roster context')
        if npc.attack.secondary_effects:
            raise ValueError('Champion bridge excludes secondary attack effects')
        protection = prepared.protection.source_request
        if (protection.defender_is_defenceless
                or protection.defender_wields_weapon != target.state.wields_weapon
                or protection.defender_holds_shield != target.state.holds_shield):
            raise ValueError('Protection has stale roster conditions/equipment')
        profiles = {p.skill: p.test_profile for p in target.definition.protection}
        if any(p.skill not in profiles or p.test.profile != profiles[p.skill] for p in protection.options):
            raise ValueError('Protection profiles differ from Champion definition')
        kernel = execution.kernel_request
        if context is not None:
            if npc.selected_profile.skill is not Skill.SHOOTING:
                raise ValueError('stationary Champion attack is scoped to ordinary Shooting')
            if source.dice_modifiers:
                raise ValueError('stationary Shooting requires unchanged normal attack modifiers')
            if any(p.test != TestRequest(p.test.id, profiles[p.skill]) for p in protection.options):
                raise ValueError('stationary Protection requires unchanged normal Tests')
            if kernel.can_target_leave_zone is not False:
                raise ValueError('Leg Spasm prevents Give Ground until treatment')
            if kernel.target_has_given_ground_this_round is not (
                    execution.target_id in context.state.spatial_state.gave_ground_entity_ids):
                raise ValueError('stationary Champion attack has stale Give Ground usage')
        _validate_prone_shooting(actor, target, prepared, kernel)
        if kernel != KernelAttackRequest(
            kernel.id, execution.target_id, prepared.attack, TargetInjuryPolicy.CHAMPION,
            injury, kernel.can_target_leave_zone, kernel.target_has_given_ground_this_round,
        ):
            raise ValueError('kernel differs from prepared attack/current Champion injury')
        # K1 derives this roll ID. Detect a reused kernel ID before consuming RNG.
        if f'{kernel.id}:wound-lifecycle' in state.consumed_wound_roll_ids:
            raise ValueError('Champion Wound roll was already consumed')

    @property
    def effective_attack(self):
        """Retain normal preparation; only the selected actual Test is Grim."""
        attack = self.preparation.attack
        return (replace(attack, defender_test=self.crushed_rib_preparation.test)
                if self.crushed_rib_preparation is not None else attack)


@dataclass(frozen=True, slots=True)
class NpcChampionAttackResult:
    source: NpcChampionAttackRequest
    execution: AttackActionExecutionResult
    resolution: ResolutionResult
    completion: CharacterWoundLifecycleCompletionResult | None = None
    crushed_rib: CrushedRibTestResult | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        for value, kind in ((self.source, NpcChampionAttackRequest),
                            (self.execution, AttackActionExecutionResult), (self.resolution, ResolutionResult)):
            _typed(value, kind)
        source, actual = self.source.execution, self.execution
        raw, expected = actual.resolution, source.kernel_request
        crushed = self.source.crushed_rib_preparation is not None or self.source.crushed_rib_consumption is not None
        if crushed:
            replace(self.source)
            _validate_crushed_rib_attack(self)
        elif self.crushed_rib is not None:
            raise ValueError('Crushed Rib completion requires its pending preparation')
        if (actual.request_id, actual.actor_id, actual.target_id, actual.slot_index, actual.previous_state) != (
                source.id, source.actor_id, source.target_id, source.slot_index, source.state):
            raise ValueError('attack execution belongs to another source')
        if (raw.request_id != expected.id or raw.attack.request_id != expected.attack.id
                or raw.attack.impact_spec != expected.attack.impact_spec
                or raw.attack.attacker_test.trace.request_id != expected.attack.attacker_test.id
                or (raw.attack.defender_test is None) != (expected.attack.defender_test is None)):
            raise ValueError('kernel result differs from prepared source')
        if (raw.attack.defender_test is not None
                and raw.attack.defender_test.trace.request_id != expected.attack.defender_test.id):
            raise ValueError('Protection result differs from prepared source')
        if not isinstance(raw.target_state, CharacterInjuryState):
            raise TypeError('Champion result requires CharacterInjuryState')
        if (raw.profile_wound is not None or raw.monstrosity_impact is not None
                or raw.character_wound_completion is not None or raw.wound_effect is not None
                or raw.deferred_wound_conditions or raw.deferred_wound_condition_immunities):
            raise ValueError('bridge requires an ordinary uncompleted kernel result')
        if raw.pending_character_wound is None:
            if self.completion is not None or self.resolution != raw:
                raise ValueError('no pending Wound permits no completion or changed resolution')
        else:
            _typed(self.completion, CharacterWoundLifecycleCompletionResult)
            completion = self.completion
            roll = raw.pending_character_wound
            before = self.source.state
            if (roll.source_request.target_id != source.target_id
                    or roll.source_request.wound.state != self.post_test_injury
                    or roll.source_request.wound.subject_type is not CharacterWoundType.CHAMPION
                    or completion.source_request.roll != roll
                    or completion.previous_state != raw.target_state
                    or completion.previous_daily_wounds != before.daily_wounds
                    or completion.previous_consumed_roll_ids != before.consumed_wound_roll_ids
                    or completion.source_request.near_miss is not None
                    or completion.source_request.daily_registration_id != source.id + ':daily-wound'):
                raise ValueError('Wound completion differs from Champion attack source')
            effects = () if completion.wound_effect is None else completion.wound_effect.follow_ups
            completed = replace(raw, target_state=completion.state, wound_effect=completion.wound_effect,
                                follow_ups=(*raw.follow_ups, *effects), pending_character_wound=None,
                                character_wound_completion=completion)
            if self.resolution != completed:
                raise ValueError('completed kernel result drops or changes Wound consequences')
        for effect in self.resolution.follow_ups:
            if isinstance(effect, AttackerStaggerRequest) and effect != AttackerStaggerRequest(expected.attack.id):
                raise ValueError('attacker Staggered belongs to another attack')

    @property
    def pending_follow_ups(self) -> tuple[FollowUpRequest, ...]:
        return tuple(f for f in self.resolution.follow_ups if not isinstance(f, AttackerStaggerRequest))

    @property
    def post_test_injury(self) -> CharacterInjuryState:
        """The exact consequence source; original pre-Test kernel is retained."""
        return (self.crushed_rib.state if self.crushed_rib is not None
                else self.source.execution.kernel_request.target_state)

    @property
    def post_test_kernel_request(self) -> KernelAttackRequest:
        return replace(self.source.execution.kernel_request, attack=self.source.effective_attack,
                       target_state=self.post_test_injury)

    @property
    def state(self) -> NpcChampionAttackState:
        return self._project_state(pending=self if self.pending_follow_ups else None)

    def _project_state(self, *, pending: NpcChampionAttackResult | None) -> NpcChampionAttackState:
        previous, source = self.source.state, self.source.execution
        stagger_actor = any(isinstance(f, AttackerStaggerRequest) for f in self.resolution.follow_ups)
        participants = []
        for participant in previous.roster.participants:
            injury = participant.state.injury
            if participant.state.actor_id == source.target_id:
                injury = self.resolution.target_state
            elif participant.state.actor_id == source.actor_id and stagger_actor:
                injury = replace(injury, conditions=injury.conditions.with_condition(Condition.STAGGERED))
            participants.append(participant if injury == participant.state.injury else
                                replace(participant, state=replace(participant.state, injury=injury)))
        return replace(previous, roster=NpcRoster(participants), round_state=self.execution.state,
                       daily_wounds=previous.daily_wounds if self.completion is None else self.completion.daily_wounds,
                       consumed_execution_ids=(*previous.consumed_execution_ids, source.id),
                       consumed_wound_roll_ids=(previous.consumed_wound_roll_ids if self.completion is None
                                                else self.completion.consumed_roll_ids), pending=pending)


def _typed(value: object, kind: type) -> None:
    if not isinstance(value, kind):
        raise TypeError(f'Champion bridge requires {kind.__name__}')


def _tuple(value) -> None:
    if type(value) is not tuple:
        raise TypeError('Crushed Rib attack witnesses require original tuples')


def _integer(value) -> None:
    if type(value) is not int:
        raise TypeError('Crushed Rib attack witnesses require strict integers')


def _boolean(value) -> None:
    if type(value) is not bool:
        raise TypeError('Crushed Rib attack witnesses require strict boolean facts')


def _normal_test_source(request: TestRequest) -> None:
    _crushed_test(request)
    if request.quality_modifiers or request.success_modifiers or request.reroll_locks:
        raise ValueError('Crushed Rib attack requires an unchanged normal Test')


def _damage_spec(spec) -> None:
    _typed(spec, DamageImpactSpec)
    _boolean(spec.ignores_armour)
    replace(spec.damage)
    replace(spec.resilience)
    for values in (spec.damage_modifiers, spec.resilience_modifiers):
        _tuple(values)
        for modifier in values:
            _integer(modifier.amount)
            replace(modifier)
    replace(spec)


def _normal_attack_source(attack) -> None:
    _normal_test_source(attack.attacker_test)
    if attack.defender_test is not None:
        _normal_test_source(attack.defender_test)
    _damage_spec(attack.impact_spec)
    _boolean(attack.is_close_range)
    _boolean(attack.attacker_is_staggered)
    _tuple(attack.secondary_effects)
    replace(attack)


def _admit_crushed_rib_request(request: NpcChampionAttackRequest) -> None:
    """Readmit the explicit lower source before comparisons or Attack RNG.

    This binds only a current Champion child and a K1 witness. Full-root
    lineage/phase admission belongs to NpcRosterChampionAttackRequest.
    """
    preparation, consumed = request.crushed_rib_preparation, request.crushed_rib_consumption
    if preparation is not None and consumed is not None:
        raise ValueError('Crushed Rib pending and consumed witnesses are mutually exclusive')
    if request.stationary_wounds is not None:
        raise ValueError('Crushed Rib and stationary Wound contexts are mutually exclusive')
    state, prepared, execution = request.state, request.preparation, request.execution
    for values in (state.consumed_execution_ids, state.consumed_wound_roll_ids,
                   state.roster.participants, state.daily_wounds.receipts):
        _tuple(values)
    replace(state.daily_wounds)
    replace(state.roster)
    replace(state)
    replace(execution.state)
    _integer(execution.slot_index)
    replace(execution)
    target = state.roster.participant(execution.target_id)
    injury = target.state.injury
    if preparation is not None:
        _typed(preparation, CrushedRibTestPreparationResult)
        replace(preparation)
        _crushed_injury(injury)
        original = preparation.source_request
        if original.actor_id != execution.target_id or original.state != injury:
            raise ValueError('Crushed Rib Protection preparation has foreign actor/injury')
    else:
        if not isinstance(consumed, (CrushedRibTestResult, CrushedRibCastingResult)):
            raise TypeError('Crushed Rib consumed Protection requires a typed K1 completion')
        replace(consumed)
        _crushed_injury(injury, pending=False)
        if (consumed.source.source_request.actor_id != execution.target_id
                or consumed.state != injury):
            raise ValueError('Crushed Rib consumed Protection has foreign actor/injury')
    for participant in (state.roster.participant(execution.actor_id), target):
        replace(participant.state)
        for flag in (participant.state.wields_weapon, participant.state.holds_shield):
            _boolean(flag)
        replace(participant.state.current_resilience)
        for values in (participant.definition.attacks, participant.definition.protection,
                       participant.state.available_attack_ids):
            _tuple(values)
        replace(participant.definition)
        for profile in participant.definition.attacks:
            replace(profile)
            _tuple(profile.secondary_effects)
            _boolean(profile.ignores_armour)
            _normal_test_source(TestRequest('crushed-rib:profile', profile.test_profile))
            replace(profile.damage)
        for profile in participant.definition.protection:
            replace(profile)
            _normal_test_source(TestRequest('crushed-rib:profile', profile.test_profile))
    npc = prepared.npc_attack
    source = npc.source_request
    _tuple(source.snapshot.profiles)
    _tuple(source.snapshot.available_attack_ids)
    for profile in source.snapshot.profiles:
        replace(profile)
        _tuple(profile.secondary_effects)
        _boolean(profile.ignores_armour)
        _normal_test_source(TestRequest('crushed-rib:snapshot-profile', profile.test_profile))
        replace(profile.damage)
    replace(source.snapshot)
    for flag in (source.has_enemy_in_close_range, source.attacker_is_staggered,
                 source.range_approved_by_gm):
        _boolean(flag)
    _tuple(source.dice_modifiers)
    replace(source)
    replace(npc.selected_profile)
    _tuple(npc.selected_profile.secondary_effects)
    _boolean(npc.selected_profile.ignores_armour)
    _normal_test_source(TestRequest('crushed-rib:selected-profile', npc.selected_profile.test_profile))
    replace(npc.selected_profile.damage)
    _normal_attack_source(npc.attack)
    _tuple(npc.applied_rule_ids)
    replace(npc)
    if npc.selected_profile.skill is not Skill.SHOOTING or source.dice_modifiers:
        raise ValueError('Crushed Rib Protection is scoped to ordinary Shooting')
    protection = prepared.protection.source_request
    _normal_attack_source(protection.attack)
    for flag in (protection.defender_is_aware, protection.defender_is_defenceless,
                 protection.defender_wields_weapon, protection.defender_holds_shield):
        _boolean(flag)
    _tuple(protection.options)
    if not protection.defender_is_aware or prepared.attack.defender_test is None:
        raise ValueError('Crushed Rib Protection requires an actual opposed Test')
    profiles = {p.skill: p.test_profile for p in target.definition.protection}
    selected = None
    for option in protection.options:
        replace(option)
        _crushed_test(option.test, prepared=True)
        if option.skill not in profiles:
            raise ValueError('Crushed Rib Protection has a foreign profile')
        base = TestRequest(option.test.id, profiles[option.skill])
        if option.skill is protection.selected_skill:
            selected = option
            expected = base
            if preparation is not None and preparation.source_request.test != base:
                raise ValueError('Crushed Rib preparation must use the selected normal Protection')
        else:
            expected = base
        if option.test != expected:
            raise ValueError('Crushed Rib must change only the selected Protection Test')
    if selected is None or prepared.attack.defender_test != selected.test:
        raise ValueError('Crushed Rib Protection selection differs from its actual Test')
    replace(protection)
    for values in (prepared.protection.eligible_skills, prepared.protection.unopposed_reasons,
                   prepared.protection.applied_rule_ids):
        _tuple(values)
    for skill in prepared.protection.eligible_skills:
        _typed(skill, Skill)
    _normal_attack_source(prepared.protection.attack)
    replace(prepared.protection)
    _tuple(prepared.applied_rule_ids)
    replace(prepared)
    kernel = execution.kernel_request
    _normal_attack_source(kernel.attack)
    for flag in (kernel.can_target_leave_zone, kernel.target_has_given_ground_this_round):
        _boolean(flag)
    for values in (kernel.wound_dice_modifiers, kernel.wound_negation_options,
                   kernel.additional_profile_wounds, kernel.target_effect_immunities):
        _tuple(values)
    replace(kernel)


def _normal_test_result(request: TestRequest, result: TestResult) -> None:
    _normal_test_source(request)
    _typed(result, TestResult)
    trace = result.trace
    _typed(trace, RollTrace)
    for values in (trace.initial_values, trace.final_values, trace.rerolls, trace.applied_rule_ids):
        _tuple(values)
    initial = InitialTestRoll(request, trace.base_dice, trace.pool_cap, trace.regular_dice_delta,
        trace.cap_bypassing_dice, trace.dice_before_minimum, trace.rolled_dice, trace.threshold,
        trace.minimum_die_rule_applied, trace.initial_values)
    for value in (*trace.final_values, trace.rolled_successes, trace.success_delta, trace.successes):
        _integer(value)
    successes = sum(v <= initial.threshold for v in initial.initial_values)
    if (trace.request_id != request.id or trace.quality is not TestQuality.NORMAL or trace.rerolls
            or trace.final_values != initial.initial_values
            or (trace.rolled_successes, trace.success_delta, trace.successes) != (successes, 0, successes)
            or trace.applied_rule_ids != tuple(m.rule_id for m in request.dice_modifiers)):
        raise ValueError('Crushed Rib attack normal Test trace differs from its complete source')


def _actual_attack(request, actual: AttackResult) -> None:
    """Pure exact normal-damage Attack arithmetic around validated Tests."""
    _typed(actual, AttackResult)
    _normal_test_result(request.attacker_test, actual.attacker_test)
    _typed(actual.outcome, AttackOutcome)
    _typed(actual.miss_consequence, MissConsequence)
    _boolean(actual.tie_break_applied)
    _integer(actual.success_margin)
    for value in (actual.damage, actual.effective_resilience):
        if value is not None:
            _integer(value)
    _tuple(actual.applied_rule_ids)
    _damage_spec(actual.impact_spec)
    a, b = actual.attacker_test.successes, actual.defender_test.successes
    hit = a > 0 and a >= b
    margin, tie = (a - b, a == b) if hit else (0, False)
    if not hit:
        miss = MissConsequence.STAGGER_ATTACKER if request.is_close_range and not request.attacker_is_staggered else MissConsequence.NONE
        expected = AttackResult(request.id, actual.attacker_test, actual.defender_test,
            AttackOutcome.MISS, 0, request.impact_spec, None, None, None, miss, False, ())
    else:
        spec = request.impact_spec
        _typed(spec, DamageImpactSpec)
        damage = spec.damage.base + margin * spec.damage.success_multiplier
        resilience = spec.resilience.toughness if spec.ignores_armour else spec.resilience.total
        expected = AttackResult(request.id, actual.attacker_test, actual.defender_test,
            AttackOutcome.HIT, margin, spec, damage, resilience,
            ImpactOutcome.WOUND if damage > resilience else ImpactOutcome.STAGGERED,
            MissConsequence.NONE, tie, ('RULE-COMBAT-006:attack-tie',) if tie else ())
    if actual.impact is not None:
        _typed(actual.impact, ImpactOutcome)
    if actual != expected:
        raise ValueError('Crushed Rib Attack differs from its exact completed Tests/arithmetic')


def _strict_injury_snapshot(injury) -> None:
    """Readmit a post-consequence injury, including newly unsupported Wounds."""
    _typed(injury, CharacterInjuryState)
    _boolean(injury.dead)
    _tuple(injury.wounds)
    _tuple(injury.active_wound_effects)
    _typed(injury.conditions, ConditionState)
    if type(injury.conditions.conditions) is not frozenset:
        raise TypeError('Crushed Rib consequence Conditions must be a frozenset')
    for condition in injury.conditions.conditions:
        _typed(condition, Condition)
    for wound in injury.wounds:
        _integer(wound.sequence)
        _integer(wound.table_total)
        _tuple(wound.roll_values)
        for value in wound.roll_values:
            _integer(value)
        for flag in (wound.treated, wound.effect_resolved, wound.healed):
            _boolean(flag)
        replace(wound)
    for effect in injury.active_wound_effects:
        _integer(effect.wound_sequence)
        replace(effect)
    replace(injury)


def _validate_crushed_rib_attack(result: NpcChampionAttackResult) -> None:
    source, raw = result.source, result.execution.resolution
    replace(result.execution)
    preparation = source.crushed_rib_preparation
    if preparation is not None:
        _typed(result.crushed_rib, CrushedRibTestResult)
        replace(result.crushed_rib)
        _completed_crushed_test(preparation.test, raw.attack.defender_test)
        if result.crushed_rib.source != preparation or result.crushed_rib.test != raw.attack.defender_test:
            raise ValueError('Crushed Rib receipt differs from the actual selected Protection')
    else:
        if result.crushed_rib is not None:
            raise ValueError('Consumed Protection cannot create another Crushed Rib completion')
        _normal_test_result(source.preparation.attack.defender_test, raw.attack.defender_test)
    _actual_attack(source.effective_attack, raw.attack)
    # The final resolution is a separately transportable object; equality with
    # the raw trace must not launder detached bool/string aliases.
    final_attack = result.resolution.attack
    if preparation is not None:
        _completed_crushed_test(preparation.test, final_attack.defender_test)
    else:
        _normal_test_result(source.preparation.attack.defender_test, final_attack.defender_test)
    _actual_attack(source.effective_attack, final_attack)
    _strict_injury_snapshot(result.resolution.target_state)
    injury, kernel = result.post_test_injury, result.post_test_kernel_request
    for name in ('follow_ups', 'applied_secondary_rule_ids', 'condition_applications',
                 'deferred_wound_conditions', 'deferred_wound_condition_immunities'):
        _tuple(getattr(raw, name))
    _strict_injury_snapshot(raw.target_state)
    if raw.attack.outcome is AttackOutcome.MISS:
        follow = ((AttackerStaggerRequest(kernel.attack.id),)
                  if raw.attack.miss_consequence is MissConsequence.STAGGER_ATTACKER else ())
        expected = ResolutionResult(kernel.id, raw.attack, None, injury, None, None, None, None, None, follow)
    elif raw.attack.impact is ImpactOutcome.STAGGERED:
        conditions = injury.conditions.with_condition(Condition.STAGGERED)
        stagger = StaggerResult(kernel.id + ':stagger', conditions, StaggerOutcome.CONDITION_ADDED, (), None, False, False)
        if raw.stagger is not None:
            _boolean(raw.stagger.wound_requested)
            _boolean(raw.stagger.gave_ground)
            _typed(raw.stagger.outcome, StaggerOutcome)
        expected = ResolutionResult(kernel.id, raw.attack, None, replace(injury, conditions=conditions),
            stagger, None, None, None, None, ())
    else:
        roll = raw.pending_character_wound
        if roll is None:
            raise ValueError('Crushed Rib incoming Wound must retain its actual lifecycle roll')
        wound_request = roll.source_request.wound
        _strict_injury_snapshot(wound_request.state)
        if wound_request.state != injury:
            raise ValueError('Crushed Rib Wound must start after the Protection consumption')
        replace(wound_request)
        replace(roll.source_request)
        wound = roll.wound_result
        _boolean(wound.wound_accepted)
        _typed(wound.subject_type, CharacterWoundType)
        _integer(wound.table_roll.dice)
        _integer(wound.table_roll.total)
        _tuple(wound.table_roll.values)
        for value in wound.table_roll.values:
            _integer(value)
        replace(wound.table_roll.entry)
        replace(wound.table_roll)
        _strict_injury_snapshot(wound.state)
        replace(roll)
        expected = ResolutionResult(kernel.id, raw.attack, None, wound.state, None, wound,
            None, None, None, (), pending_character_wound=roll)
    if raw != expected:
        raise ValueError('Crushed Rib consequences differ from their exact post-Test source')
    if result.completion is not None:
        completion = result.completion
        _typed(completion, CharacterWoundLifecycleCompletionResult)
        if completion.daily_registration is None or completion.wound_effect is None:
            raise ValueError('Crushed Rib incoming Wound must retain registration and effects')
        replace(completion.source_request)
        replace(completion.daily_registration.source_request)
        replace(completion.daily_registration)
        replace(completion)
        _strict_injury_snapshot(completion.state)
        # The lifecycle may add a new unsupported Wound/Condition, but cannot
        # erase the retained Drained cause or alter older records.
        if (completion.state.wounds[:-1] != injury.wounds
                or completion.state.active_wound_effects[:len(injury.active_wound_effects)] != injury.active_wound_effects
                or not injury.conditions.conditions <= completion.state.conditions.conditions):
            raise ValueError('Crushed Rib Wound completion loses the post-Test injury history')
