"""Finite first-Test cursor for native Crushed Rib continuation (ADR-0057).

The cursor stores evidence; only reconstruction from the complete journal prefix
establishes membership. It deliberately accepts current pending/unsupported owners.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from towr.domain.condition_models import Condition, ConditionState
from towr.domain.crushed_rib_test_models import _magic, _test
from towr.domain.test_models import TestRequest
from towr.domain.injury_models import (
    CharacterInjuryState, WoundRecord, WoundEntryId, WoundRecordOrigin,
    WoundConditionEffect, WoundRestrictionEffect, WoundEffectDuration, WoundRestriction,
)
from towr.domain.npc_crushed_rib_models import (
    NpcCrushedRibContext, NpcCrushedRibConsumptionWitness, _combat,
)
from towr.domain.npc_magic_scenario_models import (
    NpcMagicScenario, _validate_magic_scenario_permissions, validate_npc_magic_scenario_admission,
)
from towr.domain.npc_roster_casting_models import NpcRosterCastingState, NpcRosterCastingResult
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndResult

if TYPE_CHECKING:
    from towr.domain.npc_magic_step_models import NpcMagicStep


def _readmit(value):
    if replace(value) != value:
        raise ValueError('Crushed Rib history must not normalize its original source')


def _tuple(value):
    if type(value) is not tuple:
        raise TypeError('Crushed Rib history requires original tuple snapshots')


def _injury_snapshot(injury: CharacterInjuryState) -> None:
    """Broad typed storage, not the narrow first/consumed Wound10 admission."""
    if not isinstance(injury, CharacterInjuryState):
        raise TypeError('Crushed Rib history requires CharacterInjuryState for its Wizard')
    _tuple(injury.wounds)
    _tuple(injury.active_wound_effects)
    if not isinstance(injury.conditions, ConditionState):
        raise TypeError('Crushed Rib history requires typed Conditions')
    if type(injury.conditions.conditions) is not frozenset:
        raise TypeError('Crushed Rib history requires original Condition frozensets')
    if any(not isinstance(c, Condition) for c in injury.conditions.conditions):
        raise TypeError('Crushed Rib history requires typed Condition values')
    if type(injury.dead) is not bool:
        raise TypeError('Crushed Rib history requires a boolean death flag')
    _readmit(injury.conditions)
    for wound in injury.wounds:
        if not isinstance(wound, WoundRecord):
            raise TypeError('Crushed Rib history requires typed Wound records')
        _tuple(wound.roll_values)
        if any(type(v) is not int for v in wound.roll_values):
            raise TypeError('Crushed Rib history requires integer Wound dice')
        _readmit(wound)
    for effect in injury.active_wound_effects:
        if not isinstance(effect, (WoundConditionEffect, WoundRestrictionEffect)):
            raise TypeError('Crushed Rib history requires typed Wound effects')
        _readmit(effect)
    _readmit(injury)


def _state(state: NpcRosterCastingState) -> None:
    if not isinstance(state, NpcRosterCastingState):
        raise TypeError('Crushed Rib history requires the full typed current owner')
    for values in (state.consumed_execution_ids, state.wound_expiries, state.wound_turn_end_receipts):
        _tuple(values)
    # Detached child rosters must be read before root equality can hide aliases.
    rosters = [state.roster]
    for child in (state.champion_attack, state.minion_attack):
        if child is not None:
            rosters.append(child.roster)
    for roster in rosters:
        _tuple(roster.participants)
        wizard = roster.participant(state.wizard.actor_id)
        _injury_snapshot(wizard.state.injury)
        _readmit(wizard.state)
        _readmit(wizard)
        _readmit(roster)
    _combat(state.round_state)
    for child in (state.champion_attack, state.minion_attack):
        if child is not None:
            _tuple(child.consumed_execution_ids)
            _readmit(child)
    champion = state.champion_attack
    if champion is not None:
        _combat(champion.round_state)
        _tuple(champion.consumed_wound_roll_ids)
        _tuple(champion.daily_wounds.receipts)
        for receipt in champion.daily_wounds.receipts:
            _tuple(receipt.wound.roll_values)
            if any(type(v) is not int for v in receipt.wound.roll_values):
                raise TypeError('Crushed Rib daily history requires integer dice')
            _readmit(receipt.wound)
            _readmit(receipt)
        _readmit(champion.daily_wounds)
    for values in (state.spatial_state.placements, state.spatial_state.free_move_used_entity_ids,
                   state.spatial_state.gave_ground_entity_ids,
                   state.spatial_state.difficult_terrain_tested_entity_ids,
                   state.spatial_state.graph.zone_ids, state.spatial_state.graph.connections):
        _tuple(values)
    if type(state.spatial_state.round_number) is not int:
        raise TypeError('Crushed Rib history requires an integer spatial round')
    for placement in state.spatial_state.placements:
        _readmit(placement)
    for connection in state.spatial_state.graph.connections:
        _readmit(connection)
    _readmit(state.spatial_state.graph)
    _readmit(state.spatial_state)
    _magic(state.wizard.magic_state)
    _readmit(state.wizard.caster)
    _test(TestRequest('native-crushed-rib:casting-profile', state.wizard.caster.casting_profile))
    _readmit(state.wizard)
    _readmit(state)


@dataclass(frozen=True, slots=True)
class NpcMagicCrushedRibHistory:
    state: NpcRosterCastingState
    consumption: NpcCrushedRibConsumptionWitness | None = None

    def __post_init__(self) -> None:
        _state(self.state)
        if self.consumption is not None:
            if not isinstance(self.consumption, NpcCrushedRibConsumptionWitness):
                raise TypeError('Crushed Rib history requires its full first consumption witness')
            _readmit(self.consumption)
            origin = self.consumption.result.source.state
            if (origin.wizard.actor_id != self.state.wizard.actor_id
                    or origin.wizard.caster != self.state.wizard.caster
                    or tuple(p.definition for p in origin.roster.participants)
                    != tuple(p.definition for p in self.state.roster.participants)):
                raise ValueError('Crushed Rib first consumption belongs to another owner')


def _validate_crushed_rib_history(scenario: NpcMagicScenario, state: NpcRosterCastingState,
                                history: NpcMagicCrushedRibHistory | None) -> None:
    if not isinstance(scenario, NpcMagicScenario) or not isinstance(state, NpcRosterCastingState):
        raise TypeError('Crushed Rib policy requires typed Scenario and current owner')
    _validate_magic_scenario_permissions(scenario)
    if scenario.crushed_rib_continuation is None:
        if history is not None:
            raise ValueError('Crushed Rib history requires its independent permission')
        return
    if not isinstance(history, NpcMagicCrushedRibHistory):
        raise TypeError('opted Crushed Rib continuation requires its typed current history')
    _state(state)
    _readmit(history)
    if history.state != state:
        raise ValueError('Crushed Rib history differs from the full current owner')


def initial_magic_crushed_rib_history(scenario: NpcMagicScenario) -> NpcMagicCrushedRibHistory | None:
    validate_npc_magic_scenario_admission(scenario)
    return (None if scenario.crushed_rib_continuation is None
            else NpcMagicCrushedRibHistory(scenario.initial_runtime_state))


def magic_crushed_rib_required(state: NpcRosterCastingState, actor_id: str) -> bool:
    """Wound10 cannot enter an action through a legacy injury fallback."""
    if not isinstance(state, NpcRosterCastingState):
        raise TypeError('Crushed Rib requirement needs a typed current owner')
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise TypeError('Crushed Rib requirement needs an actor ID')
    actor = state.roster.participant(actor_id)
    if actor_id != state.wizard.actor_id:
        return False
    _injury_snapshot(actor.state.injury)
    return not actor.state.injury.dead and any(w.entry_id is WoundEntryId.CRUSHED_RIB
                                              for w in actor.state.injury.wounds)


def _pending(state):
    return (state.pending_miscast is not None or state.pending_movement is not None
            or state.pending_miscast_continuation is not None or state.pending_interruption is not None
            or state.pending_minion_attack is not None
            or state.champion_attack is not None and state.champion_attack.pending is not None)


def _compatible_injury(injury, consumption):
    """Explicit finite shape predicate; provenance errors remain constructor errors."""
    if injury.dead or injury.conditions.conditions != frozenset((Condition.DRAINED,)):
        return False
    wounds = injury.wounds
    if (not wounds or wounds[-1].entry_id is not WoundEntryId.CRUSHED_RIB
            or any(w.entry_id is not WoundEntryId.SUPERFICIAL_INJURY for w in wounds[:-1])
            or any(not w.effect_resolved or w.treated or w.healed for w in wounds)
            or any(w.origin is not WoundRecordOrigin.TABLE_ROLL for w in wounds)):
        return False
    expected = (WoundConditionEffect(wounds[-1].sequence, Condition.DRAINED, WoundEffectDuration.UNTIL_TREATED),)
    if consumption is None:
        expected += (WoundRestrictionEffect(wounds[-1].sequence, WoundRestriction.NEXT_TEST_IS_GRIM,
                                           WoundEffectDuration.NEXT_TEST),)
    elif injury != consumption.consumption.state:
        return False
    return injury.active_wound_effects == expected


def magic_crushed_rib_context(scenario: NpcMagicScenario, state: NpcRosterCastingState,
                             actor_id: str, history: NpcMagicCrushedRibHistory | None) -> NpcCrushedRibContext | None:
    _validate_crushed_rib_history(scenario, state, history)
    required = magic_crushed_rib_required(state, actor_id)
    if scenario.crushed_rib_continuation is None or not required or _pending(state):
        return None
    injury = state.roster.participant(actor_id).state.injury
    if (history.consumption is None and injury.wounds
            and injury.active_wound_effects == (
                WoundConditionEffect(injury.wounds[-1].sequence, Condition.DRAINED,
                                     WoundEffectDuration.UNTIL_TREATED),)
            and injury.conditions.conditions == frozenset((Condition.DRAINED,))
            and injury.wounds[-1].entry_id is WoundEntryId.CRUSHED_RIB
            and all(w.entry_id is WoundEntryId.SUPERFICIAL_INJURY for w in injury.wounds[:-1])
            and all(w.effect_resolved and not w.treated and not w.healed for w in injury.wounds)):
        raise ValueError('spent Crushed Rib owner requires its first consumption history')
    if not _compatible_injury(injury, history.consumption):
        return None
    return NpcCrushedRibContext(state, actor_id, scenario.facts.no_external_condition_sources,
                               history.consumption)


def _pending_castings(state):
    """Only the closed Miscast/Curse pending ancestry, never generic traversal."""
    result = [p for p in (state.pending_miscast, state.pending_movement) if p is not None]
    pending = state.pending_miscast_continuation
    if pending is not None:
        from towr.domain.npc_roster_miscast_models import NpcRosterMiscastRollResult
        if isinstance(pending, NpcRosterMiscastRollResult):
            pending = pending.source.state.pending_miscast_continuation
        if pending is not None and pending.source.state.pending_miscast is not None:
            result.append(pending.source.state.pending_miscast)
    return tuple(result)


def _evidence(step):
    """Collect explicit56 markers, including stripped-upper pending descendants."""
    result = step.result
    contexts, preparations, receipts = [], [], []
    context = getattr(result.source, 'crushed_rib_context', None)
    if context is not None:
        contexts.append(context)
    castings = list(_pending_castings(step.before))
    if isinstance(result, NpcRosterCastingResult):
        castings.append(result.casting)
        preparation = result.source.casting.crushed_rib_preparation
        if preparation is not None:
            preparations.append(preparation)
    from towr.domain.npc_roster_casting_completion_models import NpcRosterCastingCompletionResult
    if isinstance(result, NpcRosterCastingCompletionResult):
        castings.extend((result.source.completion.pending, result.completion.casting))
    for casting in castings:
        if casting.source.crushed_rib_preparation is not None:
            preparations.append(casting.source.crushed_rib_preparation)
        if casting.crushed_rib is not None:
            receipts.append(casting.crushed_rib)
    if isinstance(result, NpcRosterChampionAttackResult):
        if result.source.attack.crushed_rib_preparation is not None:
            preparations.append(result.source.attack.crushed_rib_preparation)
        for receipt in (result.source.attack.crushed_rib_consumption, result.attack.crushed_rib):
            if receipt is not None:
                receipts.append(receipt)
    pending_attack = None if step.before.champion_attack is None else step.before.champion_attack.pending
    if pending_attack is not None:
        if pending_attack.source.crushed_rib_preparation is not None:
            preparations.append(pending_attack.source.crushed_rib_preparation)
        for receipt in (pending_attack.source.crushed_rib_consumption, pending_attack.crushed_rib):
            if receipt is not None:
                receipts.append(receipt)
    if step.origin_witness is not None and isinstance(step.origin_witness, NpcRosterCastingResult):
        origin = step.origin_witness
        if origin.source.crushed_rib_context is not None:
            contexts.append(origin.source.crushed_rib_context)
        if origin.casting.crushed_rib is not None:
            receipts.append(origin.casting.crushed_rib)
    return tuple(contexts), tuple(preparations), tuple(receipts)


def _fresh_receipt(result):
    if isinstance(result, NpcRosterCastingResult):
        return result.casting.crushed_rib
    if isinstance(result, NpcRosterChampionAttackResult):
        return result.attack.crushed_rib
    return None


def validate_magic_crushed_rib_step(scenario: NpcMagicScenario, step: NpcMagicStep,
                                  history: NpcMagicCrushedRibHistory | None) -> None:
    from towr.domain.npc_magic_step_models import NpcMagicStep
    if not isinstance(step, NpcMagicStep):
        raise TypeError('Crushed Rib journal validation requires a typed step')
    _validate_crushed_rib_history(scenario, step.before, history)
    contexts, preparations, receipts = _evidence(step)
    result = step.result
    from towr.domain.npc_broken_recover_models import NpcBrokenRecoverResult
    from towr.domain.npc_broken_run_models import NpcBrokenRunResult
    from towr.domain.npc_roster_prone_models import NpcRosterProneStandResult, NpcRosterProneTurnEndResult
    if (isinstance(result, (NpcBrokenRecoverResult, NpcBrokenRunResult,
                            NpcRosterProneStandResult, NpcRosterProneTurnEndResult))
            and magic_crushed_rib_required(step.before, result.source.actor_id)):
        raise ValueError('Crushed Rib does not admit Broken/Prone action or end-turn consumers')
    actor = None
    if isinstance(result, NpcRosterCastingResult):
        actor = result.source.casting.actor_id
    elif isinstance(result, NpcRosterChampionAttackResult):
        actor = result.source.attack.execution.target_id
    elif isinstance(result, NpcWoundTurnEndResult):
        actor = result.source.actor_id
    if scenario.crushed_rib_continuation is None:
        if contexts or preparations or receipts:
            raise ValueError('Crushed Rib journal phases require their independent permission')
        if actor is not None and magic_crushed_rib_required(step.before, actor):
            raise ValueError('Wound10 requires its independent Crushed Rib permission and context')
        return
    for evidence in (*contexts, *preparations, *receipts):
        _readmit(evidence)
    _readmit(step)
    _readmit(result.source)
    _readmit(result)
    if actor is not None:
        expected = magic_crushed_rib_context(scenario, step.before, actor, history)
        if expected is None and magic_crushed_rib_required(step.before, actor):
            raise ValueError('unsupported Crushed Rib source cannot fall back to legacy admission')
        if result.source.crushed_rib_context != expected:
            raise ValueError('Crushed Rib context differs from the prefix-derived full witness')
    fresh = _fresh_receipt(result)
    if fresh is not None:
        if history.consumption is not None:
            raise ValueError('Crushed Rib journal cannot consume a second first-Test receipt')
        NpcCrushedRibConsumptionWitness(result, fresh)
    elif preparations or receipts:
        if history.consumption is None:
            raise ValueError('Crushed Rib descendant has no first consumption in its own prefix')
        original = history.consumption.consumption
        if any(receipt != original for receipt in receipts):
            raise ValueError('Crushed Rib descendant differs from the complete first receipt')
        if any(preparation != original.source for preparation in preparations):
            raise ValueError('Crushed Rib descendant differs from the first preparation')
        if (step.origin_witness is not None and isinstance(step.origin_witness, NpcRosterCastingResult)
                and step.origin_witness.casting.crushed_rib is not None
                and step.origin_witness != history.consumption.result):
            raise ValueError('Crushed Rib descendant substitutes its full first parent')
    for context in contexts:
        if context.consumption is not None and context.consumption != history.consumption:
            raise ValueError('Crushed Rib context substitutes a foreign first consumption')


def advance_magic_crushed_rib_history(scenario: NpcMagicScenario,
                                    history: NpcMagicCrushedRibHistory | None,
                                    step: NpcMagicStep) -> NpcMagicCrushedRibHistory | None:
    validate_magic_crushed_rib_step(scenario, step, history)
    if scenario.crushed_rib_continuation is None:
        return None
    receipt = _fresh_receipt(step.result)
    witness = (history.consumption if receipt is None
               else NpcCrushedRibConsumptionWitness(step.result, receipt))
    return NpcMagicCrushedRibHistory(step.after, witness)
