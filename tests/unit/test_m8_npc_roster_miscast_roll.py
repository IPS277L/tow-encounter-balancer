"""ADR-0045: one table roll retains the full source, trace and Miscast Pool.

PG1.4 Magic / Miscasts p157 and Miscast Table p159. No effect is applied.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_magic_scenario_runner import admitted, Dice
from tests.unit.test_m8_npc_roster_miscast_preparation import (
    casting_pending, interruption_pending, request as preparation_request, changed_roster,
)
from towr.domain.magic_models import MiscastTableEntry, MiscastTableEntryId as Entry, WizardMagicState
from towr.domain.npc_roster_miscast_models import (
    NpcRosterMiscastRollRequest as Request, NpcRosterMiscastRollResult as Result,
)
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.miscast_resolution import resolve_miscast_roll
from towr.rules.npc_roster_miscast_resolution import (
    prepare_npc_roster_miscast as prepare, roll_npc_roster_miscast as roll,
    apply_npc_roster_miscast_roll as apply,
)


def request(raw=None, *, identifier='miscast:prepare'):
    prepared = prepare(preparation_request(raw, identifier=identifier))
    return Request(prepared.roll_request.resolution_id, prepared.state)


def two_dice_request():
    """Actual fresh Casting origin with authored Wizard Level1, not a fake Pool."""
    source = admitted(); initial = source.initial
    source = replace(source, initial=replace(initial, wizard=replace(initial.wizard,
        caster=replace(initial.wizard.caster, wizard_level=1))))
    dice = Dice((9, 9, 1))
    result = run_npc_magic_scenario(source, dice); dice.exhausted()
    assert result.current.pending_miscast is not None
    return request(result.current)


class RosterMiscastRollTests(unittest.TestCase):
    def test_wind_totals_twenty_one_and_twenty_two_preserve_pool_and_actual_trace(self):
        for values in ((7, 7, 7), (10, 10, 2)):
            with self.subTest(values=values):
                source = request(); rng = Dice(values)
                result = roll(source, rng); rng.exhausted()
                final = apply(source.state, result)
                self.assertIs(result.source, source)
                self.assertIs(result.effect_request, result.roll.effect_request)
                self.assertEqual(result.roll.roll_values, values)
                self.assertEqual(result.roll.total, sum(values))
                self.assertEqual(result.roll.entry, MiscastTableEntry(Entry.UNNATURAL_WIND, 21, 22))
                self.assertIs(final.pending_miscast_continuation, result)
                self.assertEqual(final.wizard.magic_state, WizardMagicState(3))
                self.assertEqual(result.effect_request.source_roll_id, source.id)
                self.assertEqual(result.effect_request.resolution_id, source.id + ':effect')
                self.assertEqual((result.effect_request.pool_dice_count, result.effect_request.bonus_dice), (3, 0))

    def test_other_rows_are_retained_without_cleanup_or_wind_substitution(self):
        for values, entry in (((10, 10, 10), Entry.FEARED_FOE_ILLUSION),
                              ((10, 9, 1), Entry.SUNLIGHT_BLINDNESS),
                              ((10, 10, 3), Entry.SPELL_RECAST)):
            with self.subTest(total=sum(values)):
                source = request(); rng = Dice(values)
                result = roll(source, rng); rng.exhausted()
                self.assertIs(result.roll.entry.id, entry)
                self.assertEqual(result.state.wizard.magic_state.miscast_dice, 3)
                self.assertIs(result.state.pending_miscast_continuation, result)
                self.assertEqual(result.effect_request.roll_values, values)
                self.assertEqual(result.effect_request.total, sum(values))

    def test_two_dice_pool_cannot_be_promoted_to_wind_or_receive_a_bonus_die(self):
        source = two_dice_request(); rng = Dice((10, 10))
        self.assertEqual(source.roll_request.dice_count, 2)
        result = roll(source, rng); rng.exhausted()
        self.assertEqual(result.roll.total, 20)
        self.assertIs(result.roll.entry.id, Entry.SUNLIGHT_BLINDNESS)
        self.assertEqual(result.state.wizard.magic_state.miscast_dice, 2)
        self.assertEqual(result.effect_request.bonus_dice, 0)

    def test_request_uses_actual_prepared_roll_and_only_the_canonical_identifier(self):
        source = request()
        self.assertIs(source.roll_request, source.state.pending_miscast_continuation.roll_request)
        for identifier in ('other:roll', source.id + ':again', '', ' '):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                replace(source, id=identifier)
        for identifier in (None, 1, True):
            with self.assertRaises(TypeError): replace(source, id=identifier)

    def test_raw_nonpending_and_already_rolled_states_cannot_request_a_roll(self):
        source = request(); final = roll(source, Dice((7, 7, 7))).state
        for state in (casting_pending()[1], admitted().initial_runtime_state, final):
            for identifier in (source.id, source.id + ':new'):
                with self.subTest(state=type(state), identifier=identifier), self.assertRaises(ValueError):
                    Request(identifier, state)
        with self.assertRaises(ValueError): preparation_request(final, identifier='new:prepare')

    def test_only_pending_changes_while_every_root_owner_and_history_is_retained(self):
        for raw in (casting_pending(archive=True)[1], interruption_pending(), interruption_pending(run=True)):
            source = request(raw); result = roll(source, Dice((7, 7, 7)))
            for field in fields(source.state):
                if field.name != 'pending_miscast_continuation':
                    with self.subTest(field=field.name):
                        self.assertEqual(getattr(result.state, field.name), getattr(source.state, field.name))
            self.assertEqual(result.roll.state, source.state.wizard.magic_state)

    def test_replay_and_stale_prepared_source_are_rejected_by_apply(self):
        raw = casting_pending()[1]; source = request(raw)
        result = roll(source, Dice((7, 7, 7)))
        with self.assertRaises(ValueError): apply(result.state, result)
        changed = replace(raw, consumed_execution_ids=('earlier:action', *raw.consumed_execution_ids))
        other = request(changed)
        self.assertEqual(other.id, source.id)
        self.assertEqual(other.state.wizard.magic_state, source.state.wizard.magic_state)
        with self.assertRaises(ValueError): apply(other.state, result)

    def test_rolled_context_cannot_drop_prefix_or_change_magic_roster_spatial_history(self):
        source = request(); final = roll(source, Dice((7, 7, 7))).state
        transforms = (
            lambda s: replace(s, pending_miscast_continuation=None),
            lambda s: replace(s, wizard=replace(s.wizard, magic_state=WizardMagicState())),
            lambda s: replace(s, consumed_execution_ids=(*s.consumed_execution_ids, 'later')),
            lambda s: replace(s, spatial_state=replace(s.spatial_state, gave_ground_entity_ids=('enemy',))),
            lambda s: changed_roster(s, lambda p: replace(p, state=replace(p.state, holds_shield=True))),
        )
        for transform in transforms:
            with self.subTest(transform=transform), self.assertRaises(ValueError): transform(final)
        raw = source.state.pending_miscast_continuation.source.state
        with self.assertRaises(ValueError): replace(final, pending_miscast=raw.pending_miscast)

    def test_weak_roll_dto_must_retain_exact_metadata_magic_and_applied_rules(self):
        source = request(); actual = roll(source, Dice((7, 7, 7))).roll
        variants = (
            replace(actual, request_id='foreign'), replace(actual, target_id='ally'),
            replace(actual, state=WizardMagicState()),
            replace(actual, state=replace(actual.state, casting_successes=1, casting_lore_id='lore:battle-magic')),
            replace(actual, applied_rule_ids=()), replace(actual, applied_rule_ids=tuple(reversed(actual.applied_rule_ids))),
            replace(actual, entry=MiscastTableEntry(Entry.SUNLIGHT_BLINDNESS, 19, 20)),
        )
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises((TypeError, ValueError)): Result(source, changed)

    def test_weak_roll_dto_must_have_strict_d10_values_count_and_integer_total(self):
        source = request(); actual = roll(source, Dice((7, 7, 7))).roll
        variants = (
            replace(actual, roll_values=(7, 7)), replace(actual, roll_values=(7, 7, 7, 7)),
            replace(actual, roll_values=(0, 10, 11)), replace(actual, roll_values=(True, 10, 10)),
            replace(actual, roll_values=(7.0, 7, 7)), replace(actual, roll_values=('7', 7, 7)),
            replace(actual, roll_values=None), replace(actual, roll_values=list(actual.roll_values)),
            replace(actual, total=22),
            replace(actual, total=21.0), replace(actual, total=True),
        )
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises((TypeError, ValueError)): Result(source, changed)

    def test_effect_request_requires_exact_source_target_values_pool_and_rule(self):
        source = request(); actual = roll(source, Dice((7, 7, 7))).roll
        effect = actual.effect_request
        variants = (
            replace(effect, resolution_id='foreign:effect'), replace(effect, source_roll_id='foreign:roll'),
            replace(effect, target_id='ally'), replace(effect, roll_values=(6, 7, 8)),
            replace(effect, total=22, roll_values=(7, 7, 8)),
            replace(effect, pool_dice_count=2, bonus_dice=1),
            replace(effect, rule_id='foreign:effect-rule'),
            replace(effect, entry=MiscastTableEntry(Entry.NAUSEATING_WAVE, 21, 22),
                    rule_id='RULE-MISCAST-TABLE:nauseating_wave'),
        )
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises((TypeError, ValueError)):
                Result(source, replace(actual, effect_request=changed))

    def test_known_wind_cannot_be_redirected_to_another_plausible_entry(self):
        for values in ((7, 7, 7), (10, 10, 2)):
            source = request(); actual = roll(source, Dice(values)).roll
            fake = MiscastTableEntry(Entry.NAUSEATING_WAVE, 21, 22)
            effect_rule = 'RULE-MISCAST-TABLE:nauseating_wave'
            effect = replace(actual.effect_request, entry=fake, rule_id=effect_rule)
            forged = replace(actual, entry=fake, effect_request=effect,
                             applied_rule_ids=(source.roll_request.rule_id, effect_rule))
            with self.subTest(total=sum(values)), self.assertRaises(ValueError): Result(source, forged)

    def test_wind_entry_requires_both_canonical_range_and_correct_total(self):
        for values, bounds in (((7, 7, 7), (20, 22)), ((10, 9, 1), (20, 22)), ((10, 10, 3), (21, 23))):
            source = request(); actual = roll(source, Dice(values)).roll
            fake = MiscastTableEntry(Entry.UNNATURAL_WIND, *bounds)
            effect_rule = 'RULE-MISCAST-TABLE:unnatural_wind'
            effect = replace(actual.effect_request, entry=fake, rule_id=effect_rule)
            forged = replace(actual, entry=fake, effect_request=effect,
                             applied_rule_ids=(source.roll_request.rule_id, effect_rule))
            with self.subTest(total=sum(values), bounds=bounds), self.assertRaises(ValueError): Result(source, forged)

    def test_full_roll_result_cannot_be_rebound_to_another_preparation_identifier(self):
        source = request(); result = roll(source, Dice((7, 7, 7)))
        other = request(identifier='other:prepare')
        self.assertEqual(source.state.wizard.magic_state, other.state.wizard.magic_state)
        with self.assertRaises(ValueError): Result(other, result.roll)

    def test_executor_calls_one_existing_roll_and_apply_never_replays_it(self):
        source = request(); before = deepcopy(source); global_rng = getstate(); rng = Dice((7, 7, 7))
        with patch('towr.rules.npc_roster_miscast_resolution.resolve_miscast_roll', wraps=resolve_miscast_roll) as reducer, \
             patch('towr.rules.miscast_effect_resolution.resolve_unnatural_wind', side_effect=AssertionError('no effect')), \
             patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no action Test')), \
             patch('random.Random', side_effect=AssertionError('no global RNG')):
            result = roll(source, rng); rng.exhausted()
            final = apply(source.state, result)
            self.assertEqual(final, result.state)
        reducer.assert_called_once_with(source.roll_request, source.state.wizard.magic_state, rng)
        self.assertEqual(source, before)
        self.assertEqual(getstate(), global_rng)

    def test_mid_roll_rng_failure_propagates_without_retry_cleanup_or_source_mutation(self):
        source = request(); before = deepcopy(source); failure = RuntimeError('second die failed')
        class FailingDice:
            calls = 0
            def randint(self, low, high):
                assert (low, high) == (1, 10)
                self.calls += 1
                if self.calls == 2: raise failure
                return 7
        rng = FailingDice()
        with patch('towr.rules.npc_roster_miscast_resolution.resolve_miscast_roll', wraps=resolve_miscast_roll) as reducer:
            with self.assertRaises(RuntimeError) as caught: roll(source, rng)
        self.assertIs(caught.exception, failure)
        self.assertEqual((rng.calls, reducer.call_count), (2, 1))
        self.assertEqual(source, before)
        self.assertEqual(source.state.wizard.magic_state.miscast_dice, 3)
        self.assertIsNotNone(source.state.pending_miscast_continuation)

    def test_result_constructor_validates_without_lookup_rng_or_effect_replay(self):
        source = request(); actual = roll(source, Dice((7, 7, 7))).roll
        with patch('towr.rules.miscast_table.lookup_miscast', side_effect=AssertionError('no replay lookup')), \
             patch('towr.rules.npc_roster_miscast_resolution.resolve_miscast_roll', side_effect=AssertionError('no reroll')), \
             patch('towr.rules.miscast_effect_resolution.resolve_unnatural_wind', side_effect=AssertionError('no effect')):
            result = Result(source, actual)
            self.assertEqual(result.state.wizard.magic_state.miscast_dice, 3)

    def test_types_and_frozen_slotted_finite_source_chain(self):
        source = request(); result = roll(source, Dice((7, 7, 7)))
        for value in (source, result):
            self.assertFalse(hasattr(value, '__dict__'))
            with self.assertRaises(FrozenInstanceError): setattr(value, fields(value)[0].name, None)
        self.assertEqual(deepcopy(result.state), result.state)
        self.assertIsNotNone(result.source.state.pending_miscast_continuation.source.state.pending_miscast)
        self.assertIsNone(result.source.state.pending_miscast_continuation.source.state.pending_miscast_continuation)
        for value in (None, source.state, result):
            with self.assertRaises(TypeError): roll(value, Dice(()))
        with self.assertRaises(TypeError): Request(source.id, None)
        with self.assertRaises(TypeError): Result(source.state, result.roll)
        with self.assertRaises(TypeError): Result(source, None)
        for state, value in ((None, result), (source, result), (source.state, None), (source.state, source)):
            with self.assertRaises(TypeError): apply(state, value)
        for changes in ({'entry': object()}, {'effect_request': None}, {'state': None}):
            with self.assertRaises((TypeError, ValueError)): Result(source, replace(result.roll, **changes))


if __name__ == '__main__':
    unittest.main()
