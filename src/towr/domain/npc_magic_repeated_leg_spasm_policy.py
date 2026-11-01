"""Finite native repeated-stand cursor (ADR-0053), not a journal proof token."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.injury_models import WoundEntryId, WoundRecordOrigin
from towr.domain.npc_magic_scenario_models import (
    NpcMagicScenario, validate_npc_magic_scenario_admission, _validate_magic_scenario_permissions,
)
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandResult
from towr.domain.npc_roster_repeated_leg_spasm_models import (
    NpcRosterRepeatedLegSpasmStandRequest, NpcRosterRepeatedLegSpasmStandResult,
    _anchors, _attack_witness, _injury, _owner, _prefix, _readmit,
)
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.wound_lifecycle_models import CharacterWoundLifecycleOutcome

if TYPE_CHECKING:
    from towr.domain.npc_magic_scene_models import NpcMagicSceneFrame
    from towr.domain.npc_magic_step_models import NpcMagicStep


def _qualifying(previous: NpcRosterLegSpasmStandResult, attack: NpcRosterChampionAttackResult) -> bool:
    """Only prefix admission; never synthesize a Wizard turn after the Attack."""
    _readmit(attack.source.attack)
    _readmit(attack.source)
    _readmit(attack.attack)
    _readmit(attack)
    completion = attack.attack.completion
    if completion is None:
        return False
    _readmit(completion)
    if completion.wound_effect is None:
        return False
    _readmit(completion.wound_effect.request)
    if (completion.outcome is not CharacterWoundLifecycleOutcome.ACCEPTED
            or completion.wound_effect.request.entry_id is not WoundEntryId.LEG_SPASM
            or attack.attack.pending_follow_ups):
        return False
    actor_id = previous.source.actor_id
    before = attack.source.state
    old = previous.state
    injury = before.roster.participant(actor_id).state.injury
    _injury(injury)
    # Existing base paths (including timed/expired6) remain valid, but cannot
    # supply a new52 prefix. Do not turn their completion into an exception.
    if (any(w.entry_id not in (WoundEntryId.LEG_SPASM, WoundEntryId.SUPERFICIAL_INJURY) for w in injury.wounds)
            or before.wound_expiries
            or any(r.expired_sources or r.expired_attack_ids for r in before.wound_turn_end_receipts)):
        return False
    _attack_witness(attack, actor_id)
    if (_anchors(old) != _anchors(before)
            or injury != old.roster.participant(actor_id).state.injury
            or old.champion_attack.daily_wounds != before.champion_attack.daily_wounds
            or old.champion_attack.consumed_wound_roll_ids != before.champion_attack.consumed_wound_roll_ids
            or not _prefix(old.consumed_execution_ids, before.consumed_execution_ids)
            or not _prefix(old.champion_attack.consumed_execution_ids, before.champion_attack.consumed_execution_ids)
            or before.round_state.round_number <= old.round_state.round_number):
        return False
    wound = completion.state.wounds[-1]
    return (len(completion.state.wounds) == len(injury.wounds) + 1
            and completion.state.wounds[:-1] == injury.wounds
            and wound.origin is WoundRecordOrigin.TABLE_ROLL and wound.table_total == 9)


@dataclass(frozen=True, slots=True)
class NpcMagicRepeatedLegSpasmHistory:
    """Bounded current context; publication derives membership from its prefix."""

    state: NpcRosterCastingState
    previous_stand: NpcRosterLegSpasmStandResult | None = None
    wound_attack: NpcRosterChampionAttackResult | None = None
    repeated_stand: NpcRosterRepeatedLegSpasmStandResult | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, NpcRosterCastingState):
            raise TypeError('repeated history requires the full current owner')
        _readmit(self.state)  # Current may legitimately have mandatory pending phases.
        previous = self.previous_stand
        if previous is not None:
            if not isinstance(previous, NpcRosterLegSpasmStandResult):
                raise TypeError('repeated history requires its typed stand48')
            _owner(previous.source.state)
            _readmit(previous.source)
            _readmit(previous)
            if previous.source.actor_id != self.state.wizard.actor_id:
                raise ValueError('repeated history belongs to another owner')
        if self.wound_attack is not None:
            if not isinstance(self.wound_attack, NpcRosterChampionAttackResult):
                raise TypeError('repeated history requires its outer bound Attack')
            if previous is None or not _qualifying(previous, self.wound_attack):
                raise ValueError('repeated history Attack has no matching stand48 prefix')
        if self.repeated_stand is not None:
            if not isinstance(self.repeated_stand, NpcRosterRepeatedLegSpasmStandResult):
                raise TypeError('repeated history consumption requires a full stand52')
            _readmit(self.repeated_stand)
            if (previous is None or self.wound_attack is None
                    or self.repeated_stand.source.previous_stand != previous
                    or self.repeated_stand.source.wound_attack != self.wound_attack):
                raise ValueError('repeated history consumption has different full witnesses')


def _validate_history(scenario: NpcMagicScenario, state: NpcRosterCastingState,
                      history: NpcMagicRepeatedLegSpasmHistory | None) -> None:
    if not isinstance(scenario, NpcMagicScenario):
        raise TypeError('repeated context requires a typed Scenario')
    _validate_magic_scenario_permissions(scenario)
    if history is not None:
        if not isinstance(history, NpcMagicRepeatedLegSpasmHistory):
            raise TypeError('repeated context requires NpcMagicRepeatedLegSpasmHistory')
        _readmit(history)
        if scenario.repeated_leg_spasm_continuation is None or history.state != state:
            raise ValueError('repeated history belongs to another permission or full current owner')


def initial_magic_repeated_leg_spasm_history(scenario: NpcMagicScenario) -> NpcMagicRepeatedLegSpasmHistory | None:
    validate_npc_magic_scenario_admission(scenario)
    return (None if scenario.repeated_leg_spasm_continuation is None
            else NpcMagicRepeatedLegSpasmHistory(scenario.initial_runtime_state))


def advance_magic_repeated_leg_spasm_history(
    scenario: NpcMagicScenario, history: NpcMagicRepeatedLegSpasmHistory | None, step: NpcMagicStep,
) -> NpcMagicRepeatedLegSpasmHistory | None:
    from towr.domain.npc_magic_step_models import NpcMagicStep
    if not isinstance(step, NpcMagicStep):
        raise TypeError('repeated history advance requires a typed magic step')
    _validate_history(scenario, step.before, history)
    if scenario.repeated_leg_spasm_continuation is None:
        if isinstance(step.result, NpcRosterRepeatedLegSpasmStandResult):
            raise ValueError('repeated stand requires its independent permission')
        return None
    if history is None:
        raise ValueError('opted publication requires its derived repeated history')
    previous, attack, repeated = history.previous_stand, history.wound_attack, history.repeated_stand
    result = step.result
    if isinstance(result, NpcRosterLegSpasmStandResult):
        if previous is not None:
            raise ValueError('repeated history cannot replace its first recorded stand48')
        previous = result
    elif isinstance(result, NpcRosterChampionAttackResult):
        if previous is not None and attack is None and repeated is None and _qualifying(previous, result):
            attack = result
    elif isinstance(result, NpcRosterRepeatedLegSpasmStandResult):
        _readmit(result)
        if (repeated is not None or previous is None or attack is None
                or result.source.previous_stand != previous or result.source.wound_attack != attack):
            raise ValueError('repeated stand witnesses differ from the recorded journal prefix')
        repeated = result
    return NpcMagicRepeatedLegSpasmHistory(step.after, previous, attack, repeated)


def _proposal(scenario: NpcMagicScenario, state: NpcRosterCastingState,
              history: NpcMagicRepeatedLegSpasmHistory | None, request_id: str) -> NpcRosterRepeatedLegSpasmStandRequest | None:
    _validate_history(scenario, state, history)
    if (scenario.repeated_leg_spasm_continuation is None or history is None
            or history.previous_stand is None or history.wound_attack is None or history.repeated_stand is not None):
        return None
    try:
        return NpcRosterRepeatedLegSpasmStandRequest(request_id, state, state.wizard.actor_id,
            False, scenario.facts.no_external_condition_sources, history.previous_stand, history.wound_attack)
    except ValueError:
        # A pure low-level scope refusal (e.g. wrong phase/spent move), never
        # an execution error. TypeErrors for damaged witnesses remain errors.
        return None


def magic_repeated_leg_spasm_stand_family(
    scenario: NpcMagicScenario, state: NpcRosterCastingState, history: NpcMagicRepeatedLegSpasmHistory | None,
) -> bool:
    return _proposal(scenario, state, history, 'repeated:family-check') is not None


def magic_repeated_leg_spasm_stand_eligible(
    scenario: NpcMagicScenario, state: NpcRosterCastingState, frame: NpcMagicSceneFrame | None,
    history: NpcMagicRepeatedLegSpasmHistory | None,
) -> bool:
    if not magic_repeated_leg_spasm_stand_family(scenario, state, history) or frame is None:
        return False
    from towr.domain.npc_magic_journal_policy import magic_scene_key
    if frame != scenario.frame_for(magic_scene_key(state)):
        return False
    actor = state.wizard.actor_id
    return not any(p.target_range is RangedWeaponRange.CLOSE
                   and actor in (p.first_actor_id, p.second_actor_id) for p in frame.pair_ranges)


def magic_repeated_leg_spasm_stand_request(
    scenario: NpcMagicScenario, state: NpcRosterCastingState, frame: NpcMagicSceneFrame | None,
    history: NpcMagicRepeatedLegSpasmHistory | None, request_id: str,
) -> NpcRosterRepeatedLegSpasmStandRequest | None:
    if not magic_repeated_leg_spasm_stand_eligible(scenario, state, frame, history):
        return None
    return _proposal(scenario, state, history, request_id)


def validate_magic_repeated_leg_spasm_step(
    scenario: NpcMagicScenario, step: NpcMagicStep, history: NpcMagicRepeatedLegSpasmHistory | None,
) -> None:
    _validate_history(scenario, step.before, history)
    if scenario.repeated_leg_spasm_continuation is None:
        if isinstance(step.result, NpcRosterRepeatedLegSpasmStandResult):
            raise ValueError('repeated stand requires its independent permission')
        return
    from towr.domain.npc_magic_journal_policy import magic_scene_key
    frame = scenario.frame_for(magic_scene_key(step.before))
    result = step.result
    if isinstance(result, NpcRosterRepeatedLegSpasmStandResult):
        _readmit(result)
        expected = magic_repeated_leg_spasm_stand_request(scenario, step.before, frame, history, result.source.id)
        if expected is None or result.source != expected:
            raise ValueError('repeated stand differs from permission, scene, current history or recorded full witnesses')
    elif magic_repeated_leg_spasm_stand_eligible(scenario, step.before, frame, history):
        raise ValueError('eligible repeated stand is mandatory before another phase/action')
