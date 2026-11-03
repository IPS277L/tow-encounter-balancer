"""Native first Battered Leg evidence and membership checks (ADR-0061).

History stores bounded evidence, not a proof token. Only the runner/result's
own continuous prefix and immediate predecessor establish journal membership.
PG1.4 Characteristics/Skills pp68-70, Prone p123, Wounds Table p190; GM1.1 p92.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.attack_models import AttackOutcome, ImpactOutcome
from towr.domain.injury_models import CharacterInjuryState, WoundEntryId, WoundRecord
from towr.domain.npc_magic_scenario_models import (
    NpcMagicScenario, NpcMagicPronePolicy,
    _validate_magic_scenario_permissions, validate_npc_magic_scenario_admission,
)
from towr.domain.npc_roster_battered_leg_models import (
    NpcBatteredLegCompletionWitness, NpcRosterBatteredLegRequest, NpcRosterBatteredLegResult,
    _owner, _readmit,
)
from towr.domain.npc_roster_casting_models import NpcRosterCastingState
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_battered_leg_prone_models import (
    NpcRosterBatteredLegProneStandRequest, NpcRosterBatteredLegProneStandResult,
)
from towr.domain.npc_roster_battered_leg_recover_models import (
    NpcRosterBatteredLegRecoverRequest, NpcRosterBatteredLegRecoverResult,
)
from towr.domain.npc_roster_miscast_models import NpcRosterMiscastPreparationResult, NpcRosterMiscastRollResult

if TYPE_CHECKING:
    from towr.domain.npc_magic_step_models import NpcMagicStep


def _receipt(completion, prone_stand=None, prone_recover=None):
    if completion is None:
        return None
    return NpcBatteredLegCompletionWitness(completion.source.attack, completion.endurance,
        completion.source.no_external_condition_sources, prone_stand, prone_recover)


def _owners(state):
    """The finite prepared/rolled Miscast ancestry, never a generic graph walk."""
    owners = [state]
    pending = state.pending_miscast_continuation
    if isinstance(pending, NpcRosterMiscastRollResult):
        owners.append(pending.source.state)
        pending = pending.source.state.pending_miscast_continuation
        if not isinstance(pending, NpcRosterMiscastPreparationResult):
            raise TypeError('Battered Leg rolled ancestry requires its typed preparation')
    if isinstance(pending, NpcRosterMiscastPreparationResult):
        owners.append(pending.source.state)
    elif pending is not None:
        raise TypeError('Battered Leg history requires typed Miscast ancestry')
    return tuple(owners)


def _validate_receipts(state, expected):
    for owner in _owners(state):
        _owner(owner)
        if owner.battered_leg_receipt != expected:
            raise ValueError('Battered Leg history differs from its complete recorded receipt or ancestry')


@dataclass(frozen=True, slots=True)
class NpcMagicBatteredLegHistory:
    state: NpcRosterCastingState
    completion: NpcRosterBatteredLegResult | None = None
    prone_stand: NpcRosterBatteredLegProneStandResult | None = None
    prone_recover: NpcRosterBatteredLegRecoverResult | None = None

    def __post_init__(self) -> None:
        _owner(self.state)  # Storage also admits new pending/unsupported injury.
        if self.completion is not None:
            if not isinstance(self.completion, NpcRosterBatteredLegResult):
                raise TypeError('Battered Leg history requires its full completion')
            _readmit(self.completion)
        if self.prone_stand is not None:
            if not isinstance(self.prone_stand, NpcRosterBatteredLegProneStandResult):
                raise TypeError('Battered Leg history requires its typed full Prone stand')
            _readmit(self.prone_stand)
            if (self.completion is None or self.prone_stand.source.state.battered_leg_receipt
                    != _receipt(self.completion)):
                raise ValueError('Battered Leg stand must retain its exact first Endurance completion')
        if self.prone_recover is not None:
            if not isinstance(self.prone_recover, NpcRosterBatteredLegRecoverResult):
                raise TypeError('Battered Leg history requires its typed full Recover result')
            _readmit(self.prone_recover)
            if (self.completion is None or self.prone_stand is not None
                    or self.prone_recover.source.state.battered_leg_receipt != _receipt(self.completion)):
                raise ValueError('Battered Leg Recover must retain its exact unconsumed Endurance completion')
        _validate_receipts(self.state, _receipt(self.completion, self.prone_stand, self.prone_recover))


def _validate_battered_leg_history(scenario, state, history):
    if not isinstance(scenario, NpcMagicScenario) or not isinstance(state, NpcRosterCastingState):
        raise TypeError('Battered Leg policy requires a typed Scenario and full current owner')
    _validate_magic_scenario_permissions(scenario)
    if scenario.battered_leg_continuation is None:
        if history is not None or any(owner.battered_leg_receipt is not None for owner in _owners(state)):
            raise ValueError('Battered Leg evidence requires its independent permission')
        return
    if not isinstance(history, NpcMagicBatteredLegHistory):
        raise TypeError('Battered Leg opt-in requires its typed current history')
    _owner(state)
    _readmit(history)
    if history.state != state:
        raise ValueError('Battered Leg history differs from the complete current owner')
    if (history.completion is not None and history.completion.source.endurance_profile
            != scenario.battered_leg_continuation.endurance_profile):
        raise ValueError('Battered Leg completion differs from the Scenario Endurance profile')
    if (history.prone_stand is not None and scenario.battered_leg_continuation.prone_policy
            is not NpcMagicPronePolicy.SELF_STAND_WHEN_SAFE):
        raise ValueError('Battered Leg stand requires its independently selected Prone policy')
    if (history.prone_recover is not None and scenario.battered_leg_continuation.prone_policy
            is not NpcMagicPronePolicy.RECOVER_SELF):
        raise ValueError('Battered Leg Recover requires its independently selected action policy')


def initial_magic_battered_leg_history(scenario: NpcMagicScenario) -> NpcMagicBatteredLegHistory | None:
    validate_npc_magic_scenario_admission(scenario)
    return (None if scenario.battered_leg_continuation is None
            else NpcMagicBatteredLegHistory(scenario.initial_runtime_state))


def _candidate(scenario, state, previous):
    """Finite eligibility shape first; corrupt applicable evidence is an error."""
    from towr.domain.npc_magic_step_models import NpcMagicStep
    if previous is not None and not isinstance(previous, NpcMagicStep):
        raise TypeError('Battered Leg predecessor requires a typed magic step')
    policy = scenario.battered_leg_continuation
    if policy is None or previous is None or not isinstance(previous.result, NpcRosterChampionAttackResult):
        return None
    if state.champion_attack is None or state.champion_attack.pending is None:
        return None
    _owner(state)
    injury = state.roster.participant(state.wizard.actor_id).state.injury
    canonical = WoundRecord(1, WoundEntryId.BATTERED_LEG, 5, (5,), effect_resolved=True)
    if (not isinstance(injury, CharacterInjuryState) or injury.dead or injury.conditions.conditions
            or injury.active_wound_effects or injury.wounds != (canonical,)
            or state.battered_leg_receipt is not None):
        return None
    attack = previous.result
    _readmit(attack.source)
    _readmit(attack)
    actual = attack.attack.execution.resolution.attack
    if (not isinstance(actual.outcome, AttackOutcome)
            or actual.impact is not None and not isinstance(actual.impact, ImpactOutcome)):
        raise TypeError('Battered Leg Attack outcome/impact must retain typed enums')
    if actual.outcome is not AttackOutcome.HIT or actual.impact is not ImpactOutcome.WOUND:
        return None  # A Wound from repeated Staggered is a different consumer.
    return NpcRosterBatteredLegRequest(previous.id + ':battered-leg', state, attack,
        policy.endurance_profile, scenario.facts.unmounted_combatants_only,
        scenario.facts.no_external_condition_sources)


def magic_battered_leg_request(scenario: NpcMagicScenario, state: NpcRosterCastingState,
                              previous: NpcMagicStep | None,
                              history: NpcMagicBatteredLegHistory | None) -> NpcRosterBatteredLegRequest | None:
    _validate_battered_leg_history(scenario, state, history)
    return _candidate(scenario, state, previous)


def validate_magic_battered_leg_predecessor(scenario: NpcMagicScenario,
                                           previous: NpcMagicStep | None,
                                           step: NpcMagicStep | None) -> None:
    from towr.domain.npc_magic_step_models import NpcMagicStep
    if not isinstance(scenario, NpcMagicScenario):
        raise TypeError('Battered Leg predecessor requires a typed Scenario')
    _validate_magic_scenario_permissions(scenario)
    if previous is not None and not isinstance(previous, NpcMagicStep):
        raise TypeError('Battered Leg predecessor requires a typed magic step')
    if step is not None and not isinstance(step, NpcMagicStep):
        raise TypeError('Battered Leg successor requires a typed magic step')
    completion = step.result if step is not None else None
    if isinstance(completion, NpcRosterBatteredLegResult):
        if scenario.battered_leg_continuation is None:
            raise ValueError('Battered Leg completion requires its independent permission')
        _readmit(completion)
        if (previous is None or not isinstance(previous.result, NpcRosterChampionAttackResult)
                or completion.source.attack != previous.result or step.before != previous.after):
            raise ValueError('Battered Leg completion requires its immediate full recorded Attack predecessor')
    if previous is None:
        return
    request = _candidate(scenario, previous.after, previous)
    if request is not None:
        if not isinstance(completion, NpcRosterBatteredLegResult):
            raise ValueError('eligible Battered Leg pending requires its immediate completion')
        if completion.source != replace(request, id=completion.source.id):
            raise ValueError('Battered Leg completion differs from the recorded Attack/Scenario profile')
    elif isinstance(completion, NpcRosterBatteredLegResult):
        raise ValueError('Battered Leg completion has no eligible recorded predecessor')


def validate_magic_battered_leg_step(scenario: NpcMagicScenario, step: NpcMagicStep,
                                    history: NpcMagicBatteredLegHistory | None) -> None:
    from towr.domain.npc_magic_step_models import NpcMagicStep
    if not isinstance(step, NpcMagicStep):
        raise TypeError('Battered Leg policy requires a typed magic step')
    _validate_battered_leg_history(scenario, step.before, history)
    result = step.result
    if scenario.battered_leg_continuation is None:
        if (isinstance(result, (NpcRosterBatteredLegResult, NpcRosterBatteredLegProneStandResult,
                               NpcRosterBatteredLegRecoverResult))
                or any(owner.battered_leg_receipt is not None for owner in _owners(step.after))
                or step.origin_witness is not None and (
                    any(owner.battered_leg_receipt is not None for owner in _owners(step.origin_witness.source.state))
                    or any(owner.battered_leg_receipt is not None for owner in _owners(step.origin_witness.state)))):
            raise ValueError('Battered Leg journal phases require their independent permission')
        return
    _readmit(step)
    _readmit(result.source)
    _readmit(result)
    completion, prone_stand, prone_recover = history.completion, history.prone_stand, history.prone_recover
    if isinstance(result, NpcRosterBatteredLegResult):
        if completion is not None:
            raise ValueError('Battered Leg journal cannot complete a second Endurance Test')
        if (result.source.endurance_profile != scenario.battered_leg_continuation.endurance_profile
                or result.source.unmounted is not scenario.facts.unmounted_combatants_only
                or result.source.no_external_condition_sources is not scenario.facts.no_external_condition_sources):
            raise ValueError('Battered Leg completion differs from the Scenario profile/facts')
        completion = result
    turn = step.before.round_state.active_turn
    recover_selected = magic_battered_leg_recover_selected(
        scenario, step.before, step.before.wizard.actor_id, history)
    if isinstance(result, NpcRosterBatteredLegRecoverResult):
        if not recover_selected or turn is None:
            raise ValueError('Battered Leg Recover differs from its selected action/source policy')
        prone_recover = result
    elif recover_selected and turn is not None:
        raise ValueError('selected Battered Leg Recover is required for the current action')
    if isinstance(result, NpcRosterBatteredLegProneStandResult):
        from towr.domain.npc_magic_journal_policy import magic_scene_key
        frame = scenario.frame_for(magic_scene_key(step.before))
        if not magic_battered_leg_prone_stand_eligible(scenario, step.before, frame, history):
            raise ValueError('Battered Leg stand differs from the recorded source/scene/resource policy')
        prone_stand = result
    elif magic_battered_leg_prone_stand_family(scenario, step.before, history):
        from towr.domain.npc_magic_journal_policy import magic_scene_key
        frame = scenario.frame_for(magic_scene_key(step.before))
        if magic_battered_leg_prone_stand_eligible(scenario, step.before, frame, history):
            raise ValueError('selected Battered Leg self-stand is required before the next action')
    NpcMagicBatteredLegHistory(step.after, completion, prone_stand, prone_recover)
    if step.origin_witness is not None:
        # The full origin is recorded earlier. Neither detached root may swap
        # the first Test witness while keeping equal injury/IDs.
        expected = _receipt(history.completion, history.prone_stand, history.prone_recover)
        for owner in (step.origin_witness.source.state, step.origin_witness.state):
            _validate_receipts(owner, expected)


def advance_magic_battered_leg_history(scenario: NpcMagicScenario,
                                      history: NpcMagicBatteredLegHistory | None,
                                      step: NpcMagicStep) -> NpcMagicBatteredLegHistory | None:
    validate_magic_battered_leg_step(scenario, step, history)
    if scenario.battered_leg_continuation is None:
        return None
    completion = step.result if isinstance(step.result, NpcRosterBatteredLegResult) else history.completion
    stand = step.result if isinstance(step.result, NpcRosterBatteredLegProneStandResult) else history.prone_stand
    recover = step.result if isinstance(step.result, NpcRosterBatteredLegRecoverResult) else history.prone_recover
    return NpcMagicBatteredLegHistory(step.after, completion, stand, recover)


def magic_battered_leg_scope_mismatch(scenario: NpcMagicScenario, state: NpcRosterCastingState,
                                     history: NpcMagicBatteredLegHistory | None) -> bool:
    """Only after history/receipt admission; legal new injury is not tampering."""
    _validate_battered_leg_history(scenario, state, history)
    return (history is not None and history.completion is not None
            and state.roster.participant(state.wizard.actor_id).state.injury
            != state.battered_leg_receipt.completed_injury)


def magic_battered_leg_prone_stand_family(scenario, state, history) -> bool:
    """A sourced failed Test, selected self-stand, and the Wizard's own action phase."""
    _validate_battered_leg_history(scenario, state, history)
    policy = scenario.battered_leg_continuation
    turn = state.round_state.active_turn
    return (policy is not None and policy.prone_policy is NpcMagicPronePolicy.SELF_STAND_WHEN_SAFE
            and history.completion is not None and history.prone_stand is None and history.prone_recover is None
            and not history.completion.endurance.test_result.succeeded
            and turn is not None and turn.actor_id == state.wizard.actor_id
            and not turn.action_slots[0].executed
            and state.roster.participant(state.wizard.actor_id).state.injury
            == history.completion.endurance.wound_result.state)


def magic_battered_leg_prone_stand_eligible(scenario, state, frame, history) -> bool:
    if not magic_battered_leg_prone_stand_family(scenario, state, history) or frame is None:
        return False
    from towr.domain.npc_magic_journal_policy import magic_scene_key
    from towr.domain.npc_magic_scene_models import NpcMagicSceneFrame
    from towr.domain.ranged_weapon_profiles import RangedWeaponRange
    if not isinstance(frame, NpcMagicSceneFrame):
        raise TypeError('Battered Leg stand requires its typed current scene frame')
    _readmit(frame)
    if frame != scenario.frame_for(magic_scene_key(state)):
        raise ValueError('Battered Leg stand frame differs from the supplied current scene')
    actor = state.roster.participant(state.wizard.actor_id)
    if actor.state.actor_id in state.spatial_state.free_move_used_entity_ids:
        return False
    for pair in frame.pair_ranges:
        if pair.target_range is not RangedWeaponRange.CLOSE:
            continue
        ids = (pair.first_actor_id, pair.second_actor_id)
        if actor.state.actor_id in ids:
            other = ids[1] if ids[0] == actor.state.actor_id else ids[0]
            if state.roster.participant(other).state.side is not actor.state.side:
                return False
    return True


def magic_battered_leg_prone_stand_request(scenario, state, frame, history, identifier):
    if not magic_battered_leg_prone_stand_eligible(scenario, state, frame, history):
        return None
    return NpcRosterBatteredLegProneStandRequest(identifier, state, state.wizard.actor_id, False)


def magic_battered_leg_recover_selected(scenario, state, actor_id, history) -> bool:
    """Choose the declared action before reserving a turn, or while it is unexecuted."""
    _validate_battered_leg_history(scenario, state, history)
    policy = scenario.battered_leg_continuation
    turn = state.round_state.active_turn
    return (policy is not None and policy.prone_policy is NpcMagicPronePolicy.RECOVER_SELF
            and actor_id == state.wizard.actor_id
            and history.completion is not None and history.prone_stand is None and history.prone_recover is None
            and not history.completion.endurance.test_result.succeeded
            and (turn is None or turn.actor_id == actor_id and not turn.action_slots[0].executed)
            and state.roster.participant(actor_id).state.injury == history.completion.endurance.wound_result.state)


def magic_battered_leg_recover_request(scenario, state, history, identifier):
    if state.round_state.active_turn is None or not magic_battered_leg_recover_selected(
            scenario, state, state.wizard.actor_id, history):
        return None
    return NpcRosterBatteredLegRecoverRequest(identifier, state, state.wizard.actor_id)
