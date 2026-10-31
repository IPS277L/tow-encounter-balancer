"""One ordinary Minion attack against a Champion, with Wound completion.

PG1.4 Rules pp118-121, Wounds Table pp190-191; GM1.1 Champions p92.
This adapter owns no Casting, spatial movement, or encounter terminal policy.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from towr.domain.action_execution_models import AttackActionExecutionRequest, AttackActionExecutionResult
from towr.domain.condition_models import Condition
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
from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleCompletionResult


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

    def __post_init__(self) -> None:
        for value, kind in ((self.state, NpcChampionAttackState),
                            (self.preparation, NpcProtectedAttackPreparationResult),
                            (self.execution, AttackActionExecutionRequest)):
            _typed(value, kind)
        state, execution, prepared = self.state, self.execution, self.preparation
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
        for participant in (actor, target):
            if not participant.state.injury.conditions.conditions <= {Condition.STAGGERED, Condition.PRONE}:
                raise ValueError('bridge currently supports only initial Staggered or standalone Prone Shooting')
        injury = target.state.injury
        if injury.active_wound_effects or any(not w.effect_resolved for w in injury.wounds):
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
        _validate_prone_shooting(actor, target, prepared, kernel)
        if kernel != KernelAttackRequest(
            kernel.id, execution.target_id, prepared.attack, TargetInjuryPolicy.CHAMPION,
            injury, kernel.can_target_leave_zone, kernel.target_has_given_ground_this_round,
        ):
            raise ValueError('kernel differs from prepared attack/current Champion injury')
        # K1 derives this roll ID. Detect a reused kernel ID before consuming RNG.
        if f'{kernel.id}:wound-lifecycle' in state.consumed_wound_roll_ids:
            raise ValueError('Champion Wound roll was already consumed')


@dataclass(frozen=True, slots=True)
class NpcChampionAttackResult:
    source: NpcChampionAttackRequest
    execution: AttackActionExecutionResult
    resolution: ResolutionResult
    completion: CharacterWoundLifecycleCompletionResult | None = None

    def __post_init__(self) -> None:
        for value, kind in ((self.source, NpcChampionAttackRequest),
                            (self.execution, AttackActionExecutionResult), (self.resolution, ResolutionResult)):
            _typed(value, kind)
        source, actual = self.source.execution, self.execution
        raw, expected = actual.resolution, source.kernel_request
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
                    or roll.source_request.wound.state != expected.target_state
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
