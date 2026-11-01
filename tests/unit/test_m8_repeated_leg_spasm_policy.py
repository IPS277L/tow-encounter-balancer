"""ADR-0053 permissions, derived witnesses, strict admission and bounded continuation."""
from copy import deepcopy
from dataclasses import fields, replace
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_stationary_wound_runner import scenario as base_scenario, HIT
from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_scenario_models import NpcMagicRepeatedLegSpasmPolicy as Policy
from towr.domain.npc_magic_repeated_leg_spasm_policy import (
    NpcMagicRepeatedLegSpasmHistory as History,
    initial_magic_repeated_leg_spasm_history as initial,
    advance_magic_repeated_leg_spasm_history as advance,
    magic_repeated_leg_spasm_stand_family as family,
    magic_repeated_leg_spasm_stand_eligible as eligible,
    magic_repeated_leg_spasm_stand_request as proposal,
)
from towr.domain.npc_magic_journal_policy import validate_magic_step_policy, magic_scene_key
from towr.domain.npc_magic_scenario_result_models import NpcMagicScenarioResult, diagnose_npc_magic_unsupported as diagnose
from towr.domain.npc_magic_step_models import NpcMagicStep, NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_roster_champion_attack_models import NpcRosterChampionAttackResult
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandResult
from towr.domain.npc_roster_repeated_leg_spasm_models import NpcRosterRepeatedLegSpasmStandResult
from towr.domain.npc_roster_miscast_models import NpcRosterUnnaturalWindResult
from towr.domain.npc_roster_dead_champion_models import NpcRosterDeadChampionExclusionResult
from towr.domain.magic_models import WizardMagicState
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario as run


PREFIX = (*HIT, 9, *((10,) * 9), *HIT, 4, 5, *((10,) * 9))
FULL = (*PREFIX, *((10,) * 15))
POST_SIX = (*PREFIX, *HIT, 1, 2, 3, *((10,) * 9))
THIRD_NINE = (*PREFIX, *HIT, 3, 3, 3)


def scenario(*, repeated=True, stationary=True, miscast=False, wizard_level=4):
    return replace(base_scenario(stationary=stationary, miscast=miscast, wizard_level=wizard_level),
        repeated_leg_spasm_continuation=Policy.STAND_ONCE_WITH_JOURNAL_WITNESSES if repeated else None)


def complete(values=FULL, **kwargs):
    source = scenario(**kwargs)
    dice = Dice(values)
    result = run(source, dice)
    dice.exhausted()
    return result


def repeated_position(result):
    history = initial(result.source)
    for index, step in enumerate(result.steps):
        if isinstance(step.result, NpcRosterRepeatedLegSpasmStandResult):
            return index, step, history
        history = advance(result.source, history, step)
    raise AssertionError('actual journal has no repeated stand')


class RepeatedLegSpasmPolicyTests(unittest.TestCase):
    def test_six_valid_two_invalid_combinations_preserve_independent_permissions(self):
        results = {}
        for repeated in (False, True):
            for stationary in (False, True):
                for miscast in (False, True):
                    with self.subTest(repeated=repeated, stationary=stationary, miscast=miscast):
                        if repeated and not stationary:
                            with self.assertRaises(ValueError): scenario(repeated=repeated, stationary=stationary, miscast=miscast)
                            continue
                        values = FULL if repeated else FULL[:24] if stationary else (*HIT, 9)
                        result = complete(values, repeated=repeated, stationary=stationary, miscast=miscast)
                        results[repeated, stationary, miscast] = result
                        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED if repeated else Outcome.UNSUPPORTED_PATH)
                        if not repeated: self.assertIs(result.unsupported.reason, Reason.ACTOR_INJURY)
        for repeated, stationary in ((False, False), (False, True), (True, True)):
            self.assertEqual(results[repeated, stationary, False].steps, results[repeated, stationary, True].steps)
            self.assertEqual(results[repeated, stationary, False].current, results[repeated, stationary, True].current)

    def test_actual_two_stands_do_not_count_as_actions_or_change_history(self):
        result = complete()
        snapshot, rng_before = deepcopy(result), getstate()
        first = [s for s in result.steps if isinstance(s.result, NpcRosterLegSpasmStandResult)]
        index, step, history = repeated_position(result)
        self.assertEqual(len(first), 1)
        self.assertEqual((result.executed_actions, result.started_rounds, result.completed_rounds), (9, 3, 3))
        self.assertEqual(step.result.source.previous_stand, first[0].result)
        self.assertEqual(step.result.source.wound_attack, history.wound_attack)
        self.assertEqual(step.before.round_state, step.after.round_state)
        self.assertEqual(step.before.consumed_execution_ids, step.after.consumed_execution_ids)
        self.assertEqual(step.before.wound_turn_end_receipts, step.after.wound_turn_end_receipts)
        self.assertEqual(step.after.roster, step.after.champion_attack.roster)
        self.assertEqual(step.after.roster, step.after.minion_attack.roster)
        self.assertEqual(len(step.after.roster.participant('wizard').state.injury.active_wound_effects), 2)
        self.assertEqual(replace(result), result)
        self.assertEqual(result, snapshot)
        self.assertEqual(getstate(), rng_before)

    def test_history_uses_runtime_source_and_advances_on_foreign_turn_without_executor(self):
        result = complete()
        history = initial(result.source)
        self.assertEqual(history.state, result.source.initial_runtime_state)
        self.assertEqual({f.name for f in fields(history)}, {'state', 'previous_stand', 'wound_attack', 'repeated_stand'})
        with patch('towr.rules.npc_roster_repeated_leg_spasm_resolution.stand_npc_roster_repeated_leg_spasm',
                   side_effect=AssertionError('history must be pure')):
            for step in result.steps:
                previous = history
                history = advance(result.source, history, step)
                self.assertEqual(history.state, step.after)
                self.assertEqual(previous.state, step.before)
                if isinstance(step.result, NpcRosterChampionAttackResult) and history.previous_stand is not None:
                    if history.wound_attack == step.result:
                        self.assertEqual(history.state.round_state.active_turn.actor_id, 'enemy')
        self.assertIsNotNone(history.repeated_stand)
        self.assertEqual(history.state, result.current)

    def test_proposal_requires_exact_scene_current_and_derived_witnesses(self):
        result = complete()
        _, step, history = repeated_position(result)
        source, state = result.source, step.before
        frame = source.frame_for(magic_scene_key(state))
        self.assertTrue(family(source, state, history))
        self.assertTrue(eligible(source, state, frame, history))
        self.assertEqual(proposal(source, state, frame, history, step.result.source.id), step.result.source)
        self.assertIsNone(diagnose(source, state, step.id, repeated_history=history))
        self.assertIs(diagnose(source, state, step.id).reason, Reason.ACTOR_INJURY)
        self.assertFalse(eligible(source, state, None, history))
        missing = History(state)
        self.assertFalse(family(source, state, missing))
        self.assertIs(diagnose(source, state, step.id, repeated_history=missing).reason, Reason.ACTOR_INJURY)
        foreign = replace(history, state=replace(state, wizard=replace(state.wizard, magic_state=WizardMagicState(1))))
        with self.assertRaises(ValueError): diagnose(source, state, step.id, repeated_history=foreign)
        with self.assertRaises(ValueError): advance(source, foreign, step)

    def test_third_wound_cannot_reset_or_replace_consumed_witnesses(self):
        result = complete(THIRD_NINE)
        self.assertIs(result.unsupported.reason, Reason.ACTOR_INJURY)
        _, repeated, _ = repeated_position(result)
        history = initial(result.source)
        for step in result.steps: history = advance(result.source, history, step)
        self.assertEqual(history.repeated_stand, repeated.result)
        self.assertEqual(history.wound_attack, repeated.result.source.wound_attack)
        self.assertFalse(family(result.source, result.current, history))
        self.assertEqual(tuple(w.table_total for w in result.current.roster.participant('wizard').state.injury.wounds), (9, 9, 9))

    def test_post_repeat_six_keeps_supported_expiry_and_journal_reconstruction(self):
        result = complete(POST_SIX)
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
        injury = result.current.roster.participant('wizard').state.injury
        self.assertEqual(tuple(w.table_total for w in injury.wounds), (9, 9, 6))
        self.assertFalse(injury.conditions.has(Condition.DRAINED))
        self.assertEqual(result.current.wound_expiries, ())
        self.assertEqual(len([e for r in result.current.wound_turn_end_receipts for e in r.expired_sources]), 1)
        self.assertEqual(len(injury.active_wound_effects), 2)
        self.assertEqual(replace(result), result)

    def test_same_id_and_projected_state_cannot_replace_recorded_attack(self):
        original = complete()
        alternate = complete((*FULL[:16], 3, 2, 1, *FULL[19:]))
        index, step, history = repeated_position(original)
        _, foreign_step, _ = repeated_position(alternate)
        self.assertEqual(original.current, alternate.current)
        self.assertEqual(step.before, foreign_step.before)
        self.assertEqual(step.result.source.wound_attack.attack.execution.request_id,
                         foreign_step.result.source.wound_attack.attack.execution.request_id)
        self.assertNotEqual(step.result.source.wound_attack, foreign_step.result.source.wound_attack)
        source = replace(step.result.source, wound_attack=foreign_step.result.source.wound_attack)
        forged = NpcMagicStep(replace(step.result, source=source))
        with self.assertRaises(ValueError): validate_magic_step_policy(original.source, forged, repeated_history=history)
        with self.assertRaises(ValueError): advance(original.source, history, forged)
        with self.assertRaises(ValueError): replace(original, steps=(*original.steps[:index], forged, *original.steps[index + 1:]))

    def test_permission_substitution_cannot_reinterpret_existing_journal(self):
        result = complete()
        _, step, history = repeated_position(result)
        old = replace(result.source, repeated_leg_spasm_continuation=None)
        with self.assertRaises(ValueError): validate_magic_step_policy(old, step)
        with self.assertRaises(ValueError): replace(result, source=old)
        self.assertIsNone(initial(old))
        self.assertEqual(initial(result.source).previous_stand, None)

    def test_raw_policy_fact_and_nested_miscast_facts_reject_before_rng_or_publication(self):
        result = complete(miscast=True)
        for kind in ('repeated', 'stationary', 'fact', 'miscast-fact'):
            bad = deepcopy(result.source)
            if kind in ('repeated', 'stationary'):
                name = 'repeated_leg_spasm_continuation' if kind == 'repeated' else 'stationary_wound_continuation'
                object.__setattr__(bad, name, getattr(bad, name).value)
            elif kind == 'fact':
                object.__setattr__(bad.facts, 'no_external_condition_sources', 1)
            else:
                fact = bad.miscast_continuation.facts
                name = next(f.name for f in fields(fact) if getattr(fact, f.name) is True)
                object.__setattr__(fact, name, 1)
            self.assertEqual(bad, result.source)
            dice = Dice(())
            with self.subTest(kind=kind):
                with self.assertRaises(TypeError): run(bad, dice)
                with self.assertRaises(TypeError): replace(result, source=bad)
                with self.assertRaises(TypeError): diagnose(bad, result.current, 'bad:source')
                self.assertEqual(dice.calls, 0)

    def test_pending_wound_and_miscast_are_not_skipped_by_cursor(self):
        wound = complete((*FULL[:16], *HIT, 1, 3))
        self.assertIs(wound.unsupported.reason, Reason.WOUND_EFFECT)
        self.assertIsNotNone(wound.current.champion_attack.pending)
        pending = complete((*PREFIX, *((10,) * 6), 9, 9, 9), wizard_level=2)
        self.assertIs(pending.unsupported.reason, Reason.MISCAST_PREPARATION)
        self.assertIsNotNone(pending.current.pending_miscast)
        wind = complete((*PREFIX, *((10,) * 6), 9, 9, 9, 7, 7, 7), wizard_level=2, miscast=True)
        self.assertIs(wind.unsupported.reason, Reason.END_TURN)
        self.assertTrue(any(isinstance(s.result, NpcRosterUnnaturalWindResult) for s in wind.steps))
        self.assertTrue(wind.current.roster.participant('wizard').state.injury.conditions.has(Condition.PRONE))

    def test_lethal_third_wound_keeps_immediate_dead_champion_exclusion(self):
        result = complete((*PREFIX, *HIT, 10, 10, 10))
        death = next(i for i, s in enumerate(result.steps) if isinstance(s.result, NpcRosterDeadChampionExclusionResult))
        self.assertIsInstance(result.steps[death - 1].result, NpcRosterChampionAttackResult)
        self.assertTrue(result.current.roster.participant('wizard').state.injury.dead)
        self.assertEqual(sum(isinstance(s.result, NpcRosterRepeatedLegSpasmStandResult) for s in result.steps), 1)

    def test_spent_resource_and_close_frame_do_not_fall_back_to_another_stand(self):
        result = complete()
        _, step, history = repeated_position(result)
        state, source = step.before, result.source
        spent = replace(state, spatial_state=replace(state.spatial_state, free_move_used_entity_ids=('wizard',)))
        spent_history = replace(history, state=spent)
        self.assertFalse(family(source, spent, spent_history))
        self.assertIs(diagnose(source, spent, step.id, repeated_history=spent_history).reason, Reason.ACTOR_INJURY)
        frame = source.frame_for(magic_scene_key(state))
        close = replace(frame, pair_ranges=tuple(replace(p, target_range=RangedWeaponRange.CLOSE)
            if 'wizard' in (p.first_actor_id, p.second_actor_id) else p for p in frame.pair_ranges))
        # A Close pair cannot be an admitted initial Shooting scene. Author a
        # distinct initial placement and a future frame for this standalone
        # explicit-cursor check; do not claim that this source produced the journal.
        destination = next(z for z in state.spatial_state.graph.zone_ids if z != 'arena')
        placements = tuple(replace(p, zone_id=destination) if p.entity_id == 'wizard' else p
                           for p in source.initial.spatial_state.placements)
        initial_state = replace(source.initial, spatial_state=replace(source.initial.spatial_state, placements=placements))
        from tests.unit.test_m8_npc_magic_scenario import frame as make_frame
        initial_frame = replace(make_frame(initial_state), attack_departures=frame.attack_departures)
        initial_frame = replace(initial_frame, give_ground_plans=tuple(replace(p,
            can_leave_zone=False, destination_zone_id=None, route=None, impossible_confirmed=True)
            for p in initial_frame.give_ground_plans))
        close_source = replace(source, initial=initial_state, scene_frames=(initial_frame, close))
        self.assertFalse(eligible(close_source, state, close, history))
        self.assertIsNone(proposal(close_source, state, close, history, 'no:close-stand'))
        self.assertIs(diagnose(close_source, state, step.id, repeated_history=history).reason, Reason.ACTOR_INJURY)

    def test_six_history_before_second_nine_remains_unsupported_without_cursor_exception(self):
        values = (*FULL[:16], *HIT, 1, 5, *((10,) * 9), *HIT, 3, 3, 3)
        result = complete(values)
        self.assertIs(result.unsupported.reason, Reason.ACTOR_INJURY)
        self.assertFalse(any(isinstance(s.result, NpcRosterRepeatedLegSpasmStandResult) for s in result.steps))
        history = initial(result.source)
        for step in result.steps: history = advance(result.source, history, step)
        self.assertIsNotNone(history.previous_stand)
        self.assertIsNone(history.wound_attack)
        self.assertIsNone(history.repeated_stand)
        self.assertEqual(tuple(w.table_total for w in result.current.roster.participant('wizard').state.injury.wounds), (9, 6, 9))

    def test_permission_and_history_slots_are_strict_and_dependent(self):
        source = scenario()
        for bad in (True, 1, {}, Policy.STAND_ONCE_WITH_JOURNAL_WITNESSES.value):
            with self.subTest(bad=bad), self.assertRaises(TypeError):
                replace(source, repeated_leg_spasm_continuation=bad)
        result = complete()
        _, step, history = repeated_position(result)
        with self.assertRaises(ValueError): History(step.before, wound_attack=history.wound_attack)
        with self.assertRaises(TypeError): History(step.before, previous_stand=history.wound_attack)
        with self.assertRaises(TypeError): History(step.before, repeated_stand=history.previous_stand)
        damaged = deepcopy(history.previous_stand)
        object.__setattr__(damaged.source, 'underlying_cause_allows_removal', 1)
        self.assertEqual(damaged, history.previous_stand)
        with self.assertRaises(TypeError): History(step.before, previous_stand=damaged)


if __name__ == '__main__':
    unittest.main()
