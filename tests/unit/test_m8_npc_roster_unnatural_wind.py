"""ADR-0045 bound Wind21-22: complete applications before Pool cleanup.

PG1.4 Magic / Miscasts pp157/159, Range p114 and Prone p123.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_magic_scenario import scenario
from tests.unit.test_m8_npc_magic_scenario_runner import admitted, departures, Dice
from tests.unit.test_m8_npc_roster_miscast_preparation import casting_pending, interruption_pending
from tests.unit.test_m8_npc_roster_miscast_roll import request as roll_request
from towr.domain.condition_models import Condition
from towr.domain.magic_models import WizardMagicState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_roster_miscast_models import (
    NpcRosterUnnaturalWindRequest as Request, NpcRosterUnnaturalWindResult as Result,
)
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.miscast_effect_resolution import resolve_unnatural_wind
from towr.rules.npc_roster_miscast_resolution import (
    roll_npc_roster_miscast as roll, resolve_npc_roster_unnatural_wind as resolve,
    apply_npc_roster_unnatural_wind as apply,
)


def request(raw=None, *, values=(7, 7, 7), identifier='miscast:prepare'):
    source = roll_request(raw, identifier=identifier)
    rng = Dice(values); rolled = roll(source, rng); rng.exhausted()
    return Request(rolled.effect_request.resolution_id + ':apply', rolled.state)


def with_ally_conditions(raw):
    roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=replace(p.state.injury,
        conditions=p.state.injury.conditions.with_condition(Condition.PRONE).with_condition(Condition.STAGGERED))))
        if p.state.actor_id == 'ally' else p for p in raw.roster.participants))
    return replace(raw, roster=roster, champion_attack=replace(raw.champion_attack, roster=roster),
        minion_attack=None if raw.minion_attack is None else replace(raw.minion_attack, roster=roster))


def outside_pending():
    source = departures(scenario(enemy_zone='middle'))
    rng = Dice((9, 9, 9)); result = run_npc_magic_scenario(source, rng); rng.exhausted()
    assert result.current.pending_miscast is not None
    return source, result.current


class RosterUnnaturalWindTests(unittest.TestCase):
    def test_actual_wind21_and22_select_caster_allies_and_enemies_and_clear_only_after_application(self):
        for values in ((7, 7, 7), (10, 10, 2)):
            source = request(values=values); before = deepcopy(source.state)
            result = resolve(source); final = apply(source.state, result)
            self.assertIs(result.source, source)
            self.assertEqual(tuple(t.target_id for t in source.wind_request.targets), ('wizard', 'ally', 'enemy'))
            self.assertEqual(tuple(t.target_id for t in result.wind.targets), ('wizard', 'ally', 'enemy'))
            self.assertEqual(final.wizard.magic_state, WizardMagicState())
            self.assertIsNone(final.pending_miscast_continuation)
            self.assertIsNone(final.pending_miscast)
            self.assertIsNone(final.pending_interruption)
            for target in source.wind_request.targets:
                self.assertTrue(final.roster.participant(target.target_id).state.injury.conditions.has(Condition.PRONE))
            self.assertEqual(source.state, before)
            self.assertEqual(source.state.wizard.magic_state.miscast_dice, 3)

    def test_actual_k1_request_retains_full_rolled_effect_magic_policy_and_injury_snapshots(self):
        source = request(); low = source.wind_request
        self.assertEqual(low.id, source.id)
        self.assertIs(low.source, source.state.pending_miscast_continuation.effect_request)
        self.assertEqual(low.magic_state, source.state.wizard.magic_state)
        for target in low.targets:
            actor = source.state.roster.participant(target.target_id)
            self.assertEqual(target.policy, actor.definition.injury_policy)
            self.assertEqual(target.state, actor.state.injury)

    def test_already_prone_remains_a_target_with_true_metadata_and_unrelated_conditions(self):
        source = request(with_ally_conditions(casting_pending()[1])); result = resolve(source)
        ally = next(t for t in result.wind.targets if t.target_id == 'ally')
        self.assertTrue(ally.condition_application.was_already_present)
        self.assertFalse(ally.condition_application.blocked)
        self.assertIsNone(ally.condition_application.blocked_by_rule_id)
        self.assertEqual(ally.state, source.state.roster.participant('ally').state.injury)
        self.assertTrue(ally.state.conditions.has(Condition.STAGGERED))
        self.assertFalse(result.wind.targets[0].condition_application.was_already_present)

    def test_outside_enemy_is_not_targeted_or_changed(self):
        _, raw = outside_pending(); source = request(raw); final = resolve(source).state
        self.assertEqual(tuple(t.target_id for t in source.wind_request.targets), ('wizard', 'ally'))
        self.assertEqual(final.roster.participant('enemy'), raw.roster.participant('enemy'))
        self.assertFalse(final.roster.participant('enemy').state.injury.conditions.has(Condition.PRONE))

    def test_defeated_archive_and_other_zone_remain_stored_but_untargeted(self):
        _, raw = casting_pending(archive=True); source = request(raw); result = resolve(source)
        self.assertEqual(tuple(t.target_id for t in result.wind.targets), ('wizard', 'ally'))
        for actor in ('enemy', 'blocker'):
            self.assertEqual(result.state.roster.participant(actor), raw.roster.participant(actor))
        self.assertEqual(len(result.state.roster.participants), 4)
        self.assertEqual(len(result.state.spatial_state.placements), 4)

    def test_only_actual_canonical_rolled_wind_is_admitted_and_id_is_exact(self):
        source = request(); prefix = source.state.pending_miscast_continuation
        for state in (admitted().initial_runtime_state, casting_pending()[1], prefix.source.state, resolve(source).state):
            with self.subTest(state=type(state)), self.assertRaises(ValueError): Request(source.id, state)
        for identifier in ('new:apply', source.id + ':again', '', ' '):
            with self.assertRaises(ValueError): replace(source, id=identifier)
        for identifier in (None, 1, True):
            with self.assertRaises(TypeError): replace(source, id=identifier)
        for values in ((10, 9, 1), (10, 10, 3), (10, 10, 10)):
            rolled = roll(roll_request(), Dice(values))
            with patch('towr.rules.npc_roster_miscast_resolution.resolve_unnatural_wind', side_effect=AssertionError('no effect')):
                with self.assertRaises(ValueError): Request(rolled.effect_request.resolution_id + ':apply', rolled.state)
            self.assertEqual(rolled.state.wizard.magic_state.miscast_dice, 3)

    def test_projection_changes_only_target_conditions_magic_prefix_and_child_roster_references(self):
        for raw in (casting_pending(archive=True)[1], interruption_pending(), interruption_pending(run=True)):
            source = request(raw); final = resolve(source).state
            changed = {'roster', 'wizard', 'pending_miscast_continuation', 'champion_attack', 'minion_attack'}
            for field in fields(source.state):
                if field.name not in changed:
                    self.assertEqual(getattr(final, field.name), getattr(source.state, field.name))
            for old, new in ((source.state.champion_attack, final.champion_attack),
                             (source.state.minion_attack, final.minion_attack)):
                if old is None:
                    self.assertIsNone(new); continue
                self.assertEqual(new.roster, final.roster)
                for field in fields(old):
                    if field.name != 'roster': self.assertEqual(getattr(new, field.name), getattr(old, field.name))
            for old, new in zip(source.state.roster.participants, final.roster.participants):
                self.assertEqual(replace(new, state=replace(new.state, injury=old.state.injury)), old)
                self.assertEqual(replace(new.state.injury, conditions=old.state.injury.conditions), old.state.injury)

    def test_replay_and_same_identifier_foreign_source_are_rejected(self):
        source = request(); result = resolve(source)
        with self.assertRaises(ValueError): apply(result.state, result)
        with self.assertRaises(ValueError): Request(source.id + ':new', result.state)
        raw = casting_pending()[1]
        other = request(replace(raw, consumed_execution_ids=('earlier', *raw.consumed_execution_ids)))
        self.assertEqual(other.id, source.id)
        with self.assertRaises(ValueError): apply(other.state, result)
        # Same phase IDs and same rolled state but distinct actual dice history.
        other = request(values=(8, 6, 7))
        self.assertEqual(other.state.wizard.magic_state, source.state.wizard.magic_state)
        with self.assertRaises(ValueError): apply(other.state, result)

    def test_weak_outer_dto_requires_exact_caster_id_magic_cleanup_and_rules(self):
        source = request(); actual = resolve(source).wind
        for changed in (replace(actual, request_id='foreign'), replace(actual, caster_id='ally'),
                        replace(actual, magic_state=WizardMagicState(3)),
                        replace(actual, magic_state=WizardMagicState(0, 1, 'lore:battle-magic', 1)),
                        replace(actual, applied_rule_ids=()), replace(actual, applied_rule_ids=(*actual.applied_rule_ids, 'extra'))):
            with self.subTest(changed=changed), self.assertRaises((TypeError, ValueError)): Result(source, changed)

    def test_cleanup_cannot_hide_missing_reordered_duplicated_or_untyped_targets(self):
        source = request(); actual = resolve(source).wind
        variants = ((), actual.targets[:-1], tuple(reversed(actual.targets)),
                    (actual.targets[0], actual.targets[0], *actual.targets[2:]), list(actual.targets),
                    (None, *actual.targets[1:]))
        for targets in variants:
            with self.subTest(targets=targets), self.assertRaises((TypeError, ValueError)):
                Result(source, replace(actual, targets=targets))

    def test_target_snapshot_cannot_change_wounds_conditions_or_target_identifier(self):
        source = request(); actual = resolve(source).wind; target = actual.targets[0]
        variants = (
            replace(target, target_id='ally'), replace(target, state=source.state.roster.participant('wizard').state.injury),
            replace(target, state=replace(target.state, conditions=target.state.conditions.with_condition(Condition.BROKEN))),
            replace(target, applied_rule_ids=()), replace(target, excluded_as_monstrosity=True),
            replace(target, excluded_as_monstrosity=0), replace(target, condition_application=None),
        )
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises((TypeError, ValueError)):
                Result(source, replace(actual, targets=(changed, *actual.targets[1:])))

    def test_condition_application_requires_exact_metadata_and_strict_boolean_flags(self):
        source = request(); actual = resolve(source).wind; target = actual.targets[0]; app = target.condition_application
        variants = (
            replace(app, request_id='foreign:prone'), replace(app, condition=Condition.STAGGERED),
            replace(app, condition='prone'),
            replace(app, state=app.state.with_condition(Condition.BROKEN)),
            replace(app, was_already_present=True), replace(app, was_already_present=0),
            replace(app, blocked=True), replace(app, blocked=0), replace(app, blocked_by_rule_id='immunity'),
            replace(app, source_rule_id='foreign'), replace(app, applied_rule_ids=()),
        )
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises((TypeError, ValueError)):
                Result(source, replace(actual, targets=(replace(target, condition_application=changed), *actual.targets[1:])))
        present = request(with_ally_conditions(casting_pending()[1])); wind = resolve(present).wind
        ally = wind.targets[1]
        for value in (False, 1):
            with self.subTest(already_prone=value), self.assertRaises((TypeError, ValueError)):
                Result(present, replace(wind, targets=(wind.targets[0], replace(ally,
                    condition_application=replace(ally.condition_application, was_already_present=value)), *wind.targets[2:])))

    def test_wind_cannot_heal_wounds_or_remove_independent_wound_effects(self):
        source = request(interruption_pending()); actual = resolve(source).wind
        wizard = actual.targets[0]
        self.assertTrue(wizard.state.wounds)
        self.assertTrue(wizard.state.active_wound_effects)
        variants = (
            replace(wizard.state, wounds=(), active_wound_effects=()),
            replace(wizard.state, active_wound_effects=()),
            replace(wizard.state, dead=True),
        )
        for injury in variants:
            with self.subTest(injury=injury), self.assertRaises((TypeError, ValueError)):
                Result(source, replace(actual, targets=(replace(wizard, state=injury), *actual.targets[1:])))

    def test_no_rng_or_action_and_one_existing_effect_call_apply_never_replays(self):
        source = request(); before = deepcopy(source); global_rng = getstate()
        with patch('towr.rules.npc_roster_miscast_resolution.resolve_unnatural_wind', wraps=resolve_unnatural_wind) as effect, \
             patch('towr.rules.npc_roster_miscast_resolution.resolve_miscast_roll', side_effect=AssertionError('no reroll')), \
             patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no action')), \
             patch('random.Random', side_effect=AssertionError('no RNG')):
            result = resolve(source)
            self.assertEqual(apply(source.state, result), result.state)
        effect.assert_called_once_with(source.wind_request)
        self.assertEqual(source, before)
        self.assertEqual(getstate(), global_rng)

    def test_constructor_and_derived_state_do_not_repeat_rules(self):
        source = request(); wind = resolve(source).wind
        with patch('towr.rules.npc_roster_miscast_resolution.resolve_unnatural_wind', side_effect=AssertionError('no effect replay')), \
             patch('towr.rules.condition_effect_resolution.resolve_condition_application', side_effect=AssertionError('no condition replay')):
            result = Result(source, wind)
            self.assertEqual(apply(source.state, result), result.state)

    def test_partial_effect_failure_does_not_publish_cleanup_or_mutate_source(self):
        source = request(); before = deepcopy(source); error = RuntimeError('second target failed')
        from towr.rules.miscast_effect_resolution import _resolve_unnatural_wind_target
        calls = []
        def fail_second(low, target):
            calls.append(target.target_id)
            if len(calls) == 2: raise error
            return _resolve_unnatural_wind_target(low, target)
        with patch('towr.rules.miscast_effect_resolution._resolve_unnatural_wind_target', side_effect=fail_second):
            with self.assertRaises(RuntimeError) as caught: resolve(source)
        self.assertIs(caught.exception, error)
        self.assertEqual(calls, ['wizard', 'ally'])
        self.assertEqual(source, before)
        self.assertEqual(source.state.wizard.magic_state.miscast_dice, 3)
        self.assertIsNotNone(source.state.pending_miscast_continuation)

    def test_result_cannot_rebind_another_identifier_or_different_target_snapshot(self):
        source = request(); result = resolve(source)
        for other in (request(identifier='other:prepare'), request(with_ally_conditions(casting_pending()[1]))):
            with self.assertRaises(ValueError): Result(other, result.wind)

    def test_types_frozen_slots_replace_and_finite_source_graph(self):
        source = request(); result = resolve(source)
        for value in (source, result):
            self.assertFalse(hasattr(value, '__dict__'))
            with self.assertRaises(FrozenInstanceError): setattr(value, fields(value)[0].name, None)
        self.assertEqual(deepcopy(result), result)
        self.assertEqual(replace(result), result)
        self.assertIsNotNone(result.source.state.pending_miscast_continuation.source.state.pending_miscast_continuation)
        for value in (None, result, source.state):
            with self.assertRaises(TypeError): resolve(value)
        with self.assertRaises(TypeError): Request(source.id, None)
        with self.assertRaises(TypeError): Result(None, result.wind)
        with self.assertRaises(TypeError): Result(source, None)
        for state, value in ((None, result), (source, result), (source.state, source)):
            with self.assertRaises(TypeError): apply(state, value)


if __name__ == '__main__':
    unittest.main()
