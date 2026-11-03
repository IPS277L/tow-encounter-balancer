"""ADR-0061 profile authority, exact recorded completion and pure history."""
from copy import deepcopy
from dataclasses import fields, replace
from itertools import product
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from tests.unit.test_m8_npc_magic_scenario_runner import admitted, Dice
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_battered_leg_policy import (
    NpcMagicBatteredLegHistory as History,
    initial_magic_battered_leg_history as initial,
    advance_magic_battered_leg_history as advance,
    magic_battered_leg_request as request,
    validate_magic_battered_leg_step as validate,
    validate_magic_battered_leg_predecessor as predecessor,
)
from towr.domain.npc_magic_scenario_models import (
    NpcMagicBatteredLegPolicy as Policy, NpcMagicScenario,
    NpcMagicStationaryWoundPolicy as Stationary,
    NpcMagicRepeatedLegSpasmPolicy as Repeated, NpcMagicCrushedRibPolicy as Crushed,
    validate_npc_magic_scenario_admission,
)
from towr.domain.npc_magic_step_models import NpcMagicStep as Step
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.test_models import InlineProfile
from towr.domain.turn_models import CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.npc_roster_battered_leg_resolution import execute_npc_roster_battered_leg as execute
from towr.rules.npc_wound_turn_end import end_npc_wound_turn


FIRST_FIVE = (1, 2, 3, 10, 10, 10, 5)
PROFILE = InlineProfile(2, 5)


def selected(source):
    return replace(source, battered_leg_continuation=Policy(PROFILE))


def pending_pair(values=FIRST_FIVE):
    legacy = admitted(wizard_side=CombatSide.OPPOSITION)
    dice = Dice(values)
    prefix = run_npc_magic_scenario(legacy, dice)
    dice.exhausted()
    source = selected(legacy)
    history = initial(source)
    for step in prefix.steps:
        history = advance(source, history, step)
    assert history.state == prefix.current
    return legacy, source, prefix, history


def completed_pair(values=(1, 10)):
    legacy, source, prefix, history = pending_pair()
    requested = request(source, history.state, prefix.steps[-1], history)
    dice = Dice(values)
    result = execute(requested, dice)
    dice.exhausted()
    step = Step(result)
    return legacy, source, prefix, history, step, advance(source, history, step)


class NativeBatteredLegPolicyTests(unittest.TestCase):
    def setUp(self):
        self.global_rng = getstate()

    def tearDown(self):
        self.assertEqual(getstate(), self.global_rng)

    def test_append_last_preserves_positional_source_and_24_independent_permissions(self):
        source = admitted()
        self.assertEqual(fields(NpcMagicScenario)[-1].name, 'battered_leg_continuation')
        old_values = tuple(getattr(source, item.name) for item in fields(source)[:-1])
        self.assertEqual(NpcMagicScenario(*old_values), source)
        valid = invalid = 0
        for miscast, stationary, repeated, crushed, battered in product((False, True), repeat=5):
            kwargs = dict(
                miscast_continuation=continuation_policy() if miscast else None,
                stationary_wound_continuation=Stationary.LEG_SPASM_STAND_AND_CONTINUE if stationary else None,
                repeated_leg_spasm_continuation=Repeated.STAND_ONCE_WITH_JOURNAL_WITNESSES if repeated else None,
                crushed_rib_continuation=Crushed.NEXT_TEST_WITH_JOURNAL_WITNESSES if crushed else None,
                battered_leg_continuation=Policy(PROFILE) if battered else None,
            )
            with self.subTest(kwargs=kwargs):
                if repeated and not stationary:
                    with self.assertRaises(ValueError):
                        replace(source, **kwargs)
                    invalid += 1
                else:
                    opted = replace(source, **kwargs)
                    validate_npc_magic_scenario_admission(opted)
                    self.assertEqual(opted.battered_leg_continuation, kwargs['battered_leg_continuation'])
                    valid += 1
        self.assertEqual((valid, invalid), (24, 8))

    def test_policy_requires_authored_normal_inline_profile(self):
        for value in (None, True, {}, '2d/5', PROFILE):
            if value is PROFILE:
                continue
            with self.subTest(value=value), self.assertRaises(TypeError):
                Policy(value)
        with self.assertRaises(ValueError):
            Policy(InlineProfile(2, 5, pool_cap=2))
        for value in (True, {}, PROFILE, 'endurance'):
            with self.subTest(value=value), self.assertRaises(TypeError):
                replace(admitted(), battered_leg_continuation=value)

    def test_original_profile_and_facts_are_readmitted_before_native_use(self):
        source = selected(admitted())
        for field, value in (('dice', True), ('threshold', True), ('pool_cap', False)):
            bad = deepcopy(source)
            object.__setattr__(bad.battered_leg_continuation.endurance_profile, field, value)
            with self.subTest(field=field), self.assertRaises((TypeError, ValueError)):
                initial(bad)
        for name in ('unmounted_combatants_only', 'no_external_condition_sources'):
            bad = deepcopy(source)
            object.__setattr__(bad.facts, name, 1)
            self.assertEqual(bad, source)
            with self.subTest(name=name), self.assertRaises(TypeError):
                initial(bad)

    def test_initial_uses_runtime_owner_and_requires_history_for_opt_in(self):
        legacy = admitted()
        self.assertIsNone(initial(legacy))
        opted = selected(legacy)
        history = initial(opted)
        self.assertEqual(history.state, opted.initial_runtime_state)
        self.assertNotEqual(history.state, opted.initial)
        self.assertIsNone(history.completion)
        self.assertIsNone(request(opted, history.state, None, history))
        with self.assertRaises(TypeError):
            request(opted, history.state, None, None)
        with self.assertRaises(ValueError):
            request(legacy, history.state, None, history)

    def test_actual_pending_uses_wizard_profile_and_existing_follow_up_not_active_actor(self):
        legacy, source, prefix, history = pending_pair()
        before = deepcopy((source, prefix, history))
        result = request(source, history.state, prefix.steps[-1], history)
        self.assertEqual(result.endurance_profile, PROFILE)
        self.assertNotEqual(result.endurance_profile, source.initial.wizard.caster.casting_profile)
        self.assertEqual(result.attack, prefix.steps[-1].result)
        self.assertEqual(result.state, prefix.current)
        self.assertTrue(result.unmounted)
        self.assertTrue(result.no_external_condition_sources)
        self.assertEqual(result.k1_request.actor_id, 'wizard')
        self.assertEqual(result.state.round_state.active_turn.actor_id, 'enemy')
        self.assertEqual(result.k1_request.endurance_test.id,
                         prefix.steps[-1].result.attack.pending_follow_ups[0].test_id)
        self.assertIsNone(request(legacy, prefix.current, prefix.steps[-1], None))
        self.assertEqual((source, prefix, history), before)

    def test_other_pending_wound_remains_unsupported_instead_of_constructor_error(self):
        _, source, prefix, history = pending_pair((*FIRST_FIVE[:-1], 4))
        self.assertIsNone(request(source, history.state, prefix.steps[-1], history))
        predecessor(source, prefix.steps[-1], None)
        self.assertIsNone(history.completion)
        self.assertIsNotNone(history.state.champion_attack.pending)

    def test_completion_step_has_wizard_actor_without_spending_another_action(self):
        _, source, prefix, history, step, updated = completed_pair()
        self.assertEqual(step.actor_id, 'wizard')
        self.assertEqual(step.before.round_state.active_turn.actor_id, 'enemy')
        self.assertEqual(step.id, step.result.source.id)
        self.assertEqual(step.before, history.state)
        self.assertEqual(step.after, step.result.state)
        self.assertEqual(updated.completion, step.result)
        self.assertEqual(updated.state.battered_leg_receipt.endurance, step.result.endurance)
        self.assertEqual(updated.state.consumed_execution_ids, history.state.consumed_execution_ids)
        self.assertEqual(updated.state.round_state, history.state.round_state)
        self.assertIsNone(updated.state.champion_attack.pending)
        validate(source, step, history)
        predecessor(source, prefix.steps[-1], step)

    def test_eligible_predecessor_requires_immediate_completion_including_journal_tail(self):
        _, source, prefix, _, step, _ = completed_pair()
        with self.assertRaises(ValueError):
            predecessor(source, prefix.steps[-1], None)
        with self.assertRaises(ValueError):
            predecessor(source, None, step)
        with self.assertRaises(ValueError):
            predecessor(source, prefix.steps[0], step)
        with self.assertRaises(ValueError):
            predecessor(source, prefix.steps[-1], prefix.steps[0])
        _, _, foreign_prefix, _ = pending_pair((3, 2, 1, 10, 10, 10, 5))
        self.assertNotEqual(foreign_prefix.steps[-1].result, prefix.steps[-1].result)
        with self.assertRaises(ValueError):
            predecessor(source, foreign_prefix.steps[-1], step)

    def test_original_predecessor_and_attack_enums_are_typed_before_eligibility(self):
        _, source, prefix, history = pending_pair()
        for previous in (True, {}, 'previous'):
            with self.subTest(previous=previous), self.assertRaises(TypeError):
                predecessor(source, previous, None)
        for name in ('outcome', 'impact'):
            previous = deepcopy(prefix.steps[-1])
            attack = previous.result.attack.execution.resolution.attack
            object.__setattr__(attack, name, getattr(attack, name).value)
            self.assertEqual(previous, prefix.steps[-1])
            with self.subTest(name=name), self.assertRaises(TypeError):
                request(source, history.state, previous, history)

    def test_completion_and_receipt_descendants_require_independent_permission(self):
        legacy, _, _, _, step, updated = completed_pair()
        with self.assertRaises(ValueError):
            validate(legacy, step, None)
        with self.assertRaises(ValueError):
            advance(legacy, None, step)
        ended = end_npc_wound_turn(NpcWoundTurnEndRequest('native61:enemy:end', updated.state, 'enemy'))
        with self.assertRaises(ValueError):
            validate(legacy, Step(ended), None)

    def test_none_permission_cannot_hide_receipt_in_prepared_miscast_ancestry(self):
        from towr.domain.npc_roster_miscast_models import NpcRosterMiscastRollResult
        source = replace(selected(admitted(wizard_side=CombatSide.OPPOSITION)),
                         miscast_continuation=continuation_policy())
        dice = Dice((*FIRST_FIVE, 1, 10, 9, 9, 9, 1, 1, 1))
        journal = run_npc_magic_scenario(source, dice)
        dice.exhausted()
        roll = next(s.result for s in journal.steps if isinstance(s.result, NpcRosterMiscastRollResult))
        forged = deepcopy(roll)
        object.__setattr__(forged.source.state, 'battered_leg_receipt', None)
        self.assertIsNotNone(forged.source.state.pending_miscast_continuation.source.state.battered_leg_receipt)
        legacy = replace(source, battered_leg_continuation=None)
        with self.assertRaises(ValueError):
            validate(legacy, Step(forged), None)

    def test_validation_and_history_advance_do_not_rerun_completed_endurance(self):
        _, source, prefix, history, step, _ = completed_pair()
        before = deepcopy((source, prefix, history, step))
        with patch('towr.rules.npc_roster_battered_leg_resolution.execute_battered_leg_endurance_test',
                   side_effect=AssertionError('validation replayed Endurance')):
            validate(source, step, history)
            predecessor(source, prefix.steps[-1], step)
            updated = advance(source, history, step)
        self.assertEqual(updated.completion, step.result)
        self.assertEqual((source, prefix, history, step), before)

    def test_same_source_successes_and_injury_do_not_allow_foreign_recorded_trace(self):
        _, source, _, history, first, updated = completed_pair()
        dice = Dice((2, 10))
        alternative = execute(first.result.source, dice)
        dice.exhausted()
        self.assertEqual(first.result.source, alternative.source)
        self.assertEqual(first.result.endurance.test_result.successes, alternative.endurance.test_result.successes)
        self.assertEqual(first.result.endurance.wound_result.state, alternative.endurance.wound_result.state)
        self.assertNotEqual(first.result.endurance.test_result.trace, alternative.endurance.test_result.trace)
        self.assertNotEqual(updated.state.battered_leg_receipt, alternative.state.battered_leg_receipt)
        with self.assertRaises(ValueError):
            History(updated.state, alternative)
        ended = end_npc_wound_turn(NpcWoundTurnEndRequest('native61:foreign:end', alternative.state, 'enemy'))
        with self.assertRaises(ValueError):
            validate(source, Step(ended), updated)
        self.assertEqual(advance(source, history, first).completion, first.result)

    def test_scenario_profile_cannot_be_replaced_by_equally_successful_other_profile(self):
        _, source, _, history, step, _ = completed_pair()
        other = replace(step.result.source, endurance_profile=InlineProfile(2, 4))
        dice = Dice((1, 10))
        actual = execute(other, dice)
        dice.exhausted()
        self.assertEqual(actual.endurance.wound_result.state, step.result.endurance.wound_result.state)
        with self.assertRaises(ValueError):
            validate(source, Step(actual), history)
        with self.assertRaises(ValueError):
            advance(source, history, Step(actual))

    def test_history_cannot_reset_or_strip_completion_receipt(self):
        _, source, _, _, step, updated = completed_pair()
        stripped = replace(updated.state, battered_leg_receipt=None)
        with self.assertRaises(ValueError):
            History(stripped, step.result)
        with self.assertRaises(ValueError):
            History(updated.state)
        forged = deepcopy(updated)
        object.__setattr__(forged, 'completion', None)
        ended = end_npc_wound_turn(NpcWoundTurnEndRequest('native61:reset:end', updated.state, 'enemy'))
        with self.assertRaises(ValueError):
            validate(source, Step(ended), forged)

    def test_replayed_completion_and_foreign_current_owner_are_rejected(self):
        _, source, prefix, history, step, updated = completed_pair()
        with self.assertRaises(ValueError):
            advance(source, updated, step)
        with self.assertRaises(ValueError):
            request(source, source.initial_runtime_state, prefix.steps[-1], history)
        with self.assertRaises(ValueError):
            validate(source, step, initial(source))

    def test_normal_end_preserves_exact_first_completion(self):
        _, source, _, _, step, updated = completed_pair()
        ended = end_npc_wound_turn(NpcWoundTurnEndRequest('native61:preserved:end', updated.state, 'enemy'))
        next_history = advance(source, updated, Step(ended))
        self.assertIs(next_history.completion, updated.completion)
        self.assertEqual(next_history.state.battered_leg_receipt, step.after.battered_leg_receipt)
        self.assertIsNone(next_history.state.round_state.active_turn)

    def test_history_storage_keeps_new_unsupported_injury_without_relaxing_execution(self):
        _, _, _, _, step, updated = completed_pair()
        state = updated.state
        old = state.roster.participant('wizard').state.injury
        injury = replace(old, conditions=old.conditions.with_condition(Condition.STAGGERED))
        roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=injury))
            if p.state.actor_id == 'wizard' else p for p in state.roster.participants))
        current = replace(state, roster=roster,
            champion_attack=replace(state.champion_attack, roster=roster),
            minion_attack=replace(state.minion_attack, roster=roster))
        stored = History(current, step.result)
        self.assertEqual(stored.state.roster.participant('wizard').state.injury, injury)
        self.assertEqual(stored.state.battered_leg_receipt, state.battered_leg_receipt)
        with self.assertRaisesRegex(ValueError, 'outside the completed Test scope'):
            NpcWoundTurnEndRequest('native61:outside:end', current, 'enemy')

    def test_history_reads_original_aliases_before_equality_or_normalization(self):
        _, source, prefix, history = pending_pair()
        for name, value in (('consumed_execution_ids', list(history.state.consumed_execution_ids)),):
            state = deepcopy(history.state)
            object.__setattr__(state, name, value)
            with self.subTest(name=name), self.assertRaises(TypeError):
                History(state)
        state = deepcopy(history.state)
        object.__setattr__(state.roster.participant('wizard').state, 'holds_shield', 0)
        self.assertEqual(state, history.state)
        with self.assertRaises(TypeError):
            History(state)
        bad = deepcopy(history)
        object.__setattr__(bad.state.roster.participant('wizard').state.injury.wounds[0], 'treated', 0)
        self.assertEqual(bad, history)
        with self.assertRaises(TypeError):
            request(source, bad.state, prefix.steps[-1], bad)

    def test_history_reads_detached_child_rosters_before_root_equality(self):
        _, _, _, history = pending_pair()
        for name in ('champion_attack', 'minion_attack'):
            state = deepcopy(history.state)
            child = deepcopy(getattr(state, name))
            object.__setattr__(child.roster.participant('wizard').state, 'holds_shield', 0)
            object.__setattr__(state, name, child)
            self.assertEqual(state, history.state)
            with self.subTest(name=name), self.assertRaises(TypeError):
                History(state)

    def test_history_reads_original_daily_wound_receipts_before_equal_comparison(self):
        _, _, _, history = pending_pair()
        for name, value in (('treated', 0), ('origin', 'table_roll'), ('sequence', True)):
            state = deepcopy(history.state)
            record = state.champion_attack.daily_wounds.receipts[0].wound
            object.__setattr__(record, name, value)
            self.assertEqual(state, history.state)
            with self.subTest(name=name), self.assertRaises(TypeError):
                History(state)


if __name__ == '__main__':
    unittest.main()
