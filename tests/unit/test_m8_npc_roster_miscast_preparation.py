"""ADR-0045 explicit choice and full-source prepared Miscast ownership."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from random import getstate
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_magic_scenario import scenario, frame
from tests.unit.test_m8_npc_magic_scenario_runner import admitted, departures, Dice
from tests.integration.test_m8_npc_broken_recover import wounded_broken_wizard, wizard_recovery
from tests.integration.test_m8_npc_broken_run import from_owner
from towr.domain.magic_models import CastingSpellSelection, MiscastPreparationRequest, WizardMagicState
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.npc_roster_miscast_models import (
    NpcRosterMiscastFacts as Facts, NpcRosterMiscastPolicy as Policy,
    NpcRosterMiscastPreparationRequest as Request, NpcRosterMiscastPreparationResult as Result,
)
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.engine.npc_broken_recover import execute_npc_broken_recover
from towr.engine.npc_broken_run import execute_npc_broken_run
from towr.rules.miscast_resolution import prepare_miscast
from towr.rules.npc_roster_miscast_resolution import (
    prepare_npc_roster_miscast as prepare, apply_npc_roster_miscast_preparation as apply,
)


def casting_pending(*, available=False, archive=False):
    """Actual fresh Casting origin; archive is a real prior Minion defeat."""
    source = admitted()
    values = (1, 9, 9) + (10,) * 12 + (1, 1, 9) if available else (9, 9, 9)
    if archive:
        source = departures(scenario(blocker=True))
        future = frame(source.initial, live=('wizard', 'ally', 'blocker'))
        source = departures(replace(source, activation_order=('ally', 'wizard', 'enemy', 'blocker'),
            scene_frames=(*source.scene_frames, future)))
        values = (1, 2, 3, 10, 10, 10, 9, 9, 9)
    dice = Dice(values)
    result = run_npc_magic_scenario(source, dice)
    dice.exhausted()
    assert result.current.pending_miscast is not None
    return source, result.current


def interruption_pending(*, run=False):
    """Bound Broken actions; this is not fresh runner reachability evidence."""
    _, _, owner = wounded_broken_wizard(2)
    if run:
        request = from_owner(owner, owner.wizard.actor_id)
        return execute_npc_broken_run(request).state
    dice = Dice((10, 10, 10))
    result = execute_npc_broken_recover(wizard_recovery(owner), dice)
    dice.exhausted()
    return result.state


def request(state=None, *, identifier='miscast:prepare'):
    state = casting_pending()[1] if state is None else state
    return Request(identifier, state, Policy.DECLINE_CAST_BEFORE_MISCAST, Facts(True, True, True, True, True))


def changed_roster(state, transform):
    roster = NpcRoster(tuple(transform(p) if p.state.actor_id == state.wizard.actor_id else p
                             for p in state.roster.participants))
    return replace(state, roster=roster,
        champion_attack=replace(state.champion_attack, roster=roster),
        minion_attack=None if state.minion_attack is None else replace(state.minion_attack, roster=roster))


class RosterMiscastPreparationTests(unittest.TestCase):
    def test_casting_origin_resets_only_progress_and_transfers_full_pending(self):
        source = request(); old = source.state
        result = prepare(source); final = apply(old, result)
        self.assertIs(result.source, source)
        self.assertIs(final.pending_miscast_continuation, result)
        self.assertIs(result.source.state.pending_miscast, old.pending_miscast)
        self.assertIsNone(final.pending_miscast)
        self.assertIsNone(final.pending_interruption)
        self.assertEqual(final.wizard.magic_state, WizardMagicState(3))
        self.assertEqual(result.roll_request, result.preparation.follow_ups[0])
        self.assertEqual(result.roll_request.resolution_id, source.id + ':roll')
        self.assertEqual(result.roll_request.source_resolution_id, old.pending_miscast.pending_miscast.source_resolution_id)
        self.assertEqual((result.roll_request.pool_dice_count, result.roll_request.bonus_dice), (3, 0))

    def test_available_spell_is_explicitly_declined_without_a_bonus_die(self):
        _, old = casting_pending(available=True)
        self.assertEqual(old.wizard.magic_state.casting_successes, 3)
        result = prepare(request(old))
        self.assertIs(result.source.policy, Policy.DECLINE_CAST_BEFORE_MISCAST)
        self.assertEqual(result.preparation.previous_casting_successes, 3)
        self.assertEqual(result.state.wizard.magic_state, WizardMagicState(3))
        self.assertEqual(result.preparation.follow_ups, (result.roll_request,))
        self.assertEqual(result.roll_request.bonus_dice, 0)

    def test_interruption_origins_recover_and_run_preserve_action_source(self):
        for run in (False, True):
            with self.subTest(run=run):
                old = interruption_pending(run=run)
                result = prepare(request(old)); final = result.state
                origin = old.pending_interruption
                self.assertIs(result.source.state.pending_interruption, origin)
                self.assertIsNone(final.pending_interruption)
                self.assertIsNone(final.pending_miscast)
                self.assertEqual(result.roll_request.source_resolution_id, origin.miscast_pool.roll_request.source_resolution_id)
                self.assertEqual(final.round_state.active_turn.action_slots[0].execution, origin.action)
                self.assertEqual(final.wizard.magic_state, WizardMagicState(3))
                self.assertIs(final.pending_miscast_continuation, result)

    def test_all_unrelated_root_fields_and_wizard_definition_are_preserved(self):
        for old in (casting_pending(archive=True)[1], interruption_pending(run=True)):
            source = request(old); final = prepare(source).state
            for field in fields(old):
                if field.name not in ('wizard', 'pending_miscast', 'pending_interruption', 'pending_miscast_continuation'):
                    with self.subTest(field=field.name):
                        self.assertEqual(getattr(final, field.name), getattr(old, field.name))
            self.assertEqual(final.wizard.actor_id, old.wizard.actor_id)
            self.assertEqual(final.wizard.caster, old.wizard.caster)

    def test_policy_and_scope_facts_are_required_without_defaults(self):
        old = casting_pending()[1]
        with self.assertRaises(TypeError): Facts()
        with self.assertRaises(TypeError): Request('prepare', old)
        source = request(old)
        for field in fields(source.facts):
            with self.subTest(field=field.name):
                with self.assertRaises(ValueError): replace(source.facts, **{field.name: False})
                for value in (None, 1, 'yes'):
                    with self.subTest(value=value), self.assertRaises(TypeError):
                        replace(source.facts, **{field.name: value})
        for value in (None, 'decline_cast_before_miscast', 'cast_before_miscast', True):
            with self.subTest(policy=value), self.assertRaises(TypeError): replace(source, policy=value)
        for value in (None, (True,) * 5, object()):
            with self.assertRaises(TypeError): replace(source, facts=value)

    def test_nonpending_source_and_already_prepared_source_are_rejected(self):
        source = request()
        with self.assertRaises(ValueError): request(admitted().initial_runtime_state)
        prepared = prepare(source).state
        with self.assertRaises(ValueError): request(prepared, identifier='new:phase')
        with self.assertRaises(ValueError): replace(source, state=prepared)

    def test_dead_caster_is_rejected_before_preparation(self):
        old = interruption_pending()
        dead = changed_roster(old, lambda p: replace(p, state=replace(p.state,
            injury=replace(p.state.injury, dead=True))))
        self.assertTrue(dead.roster.participant(dead.wizard.actor_id).state.injury.dead)
        with self.assertRaises(ValueError): request(dead)

    def test_latest_root_execution_must_be_the_actual_origin_receipt(self):
        old = casting_pending()[1]
        later = replace(old, consumed_execution_ids=(*old.consumed_execution_ids, 'later:action'))
        with self.assertRaises(ValueError): request(later)

    def test_interruption_requires_canonical_skipped_test_and_pool_trace(self):
        old = interruption_pending()
        raw = old.pending_interruption
        variants = (
            replace(raw, request_id='foreign:skipped'),
            replace(raw, applied_rule_ids=('foreign:skipped-rule',)),
            replace(raw, source=replace(raw.source, rule_id='foreign:source-rule')),
            replace(raw, miscast_pool=replace(raw.miscast_pool, applied_rule_ids=('foreign:pool-rule',))),
            replace(raw, miscast_pool=replace(raw.miscast_pool,
                roll_request=replace(raw.miscast_pool.roll_request, rule_id='foreign:roll-rule'))),
        )
        for origin in variants:
            # These low-level DTOs pass the legacy root guard. The new boundary
            # must require the complete action-sourced trace before preparing.
            changed = replace(old, pending_interruption=origin)
            with self.subTest(origin=origin), self.assertRaises(ValueError): request(changed)

    def test_weak_preparation_dto_cannot_change_metadata_magic_or_followup(self):
        source = request(); result = prepare(source); actual = result.preparation
        variants = (
            replace(actual, request_id='foreign'), replace(actual, target_id='ally'),
            replace(actual, previous_casting_successes=actual.previous_casting_successes + 1),
            replace(actual, previous_casting_successes=False),
            replace(actual, state=replace(actual.state, miscast_dice=0)),
            replace(actual, state=source.state.wizard.magic_state),
            replace(actual, follow_ups=()), replace(actual, applied_rule_ids=()),
            replace(actual, follow_ups=(replace(result.roll_request, bonus_dice=1),)),
            replace(actual, follow_ups=(replace(result.roll_request, resolution_id='foreign'),)),
            replace(actual, follow_ups=(replace(result.roll_request, source_resolution_id='foreign'),)),
        )
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises(ValueError): Result(source, changed)

    def test_an_actual_desperate_preparation_cannot_satisfy_decline_source(self):
        _, old = casting_pending(available=True)
        source = request(old)
        raw = old.pending_miscast.pending_miscast
        spell = CastingSpellSelection('spell:test', old.wizard.magic_state.casting_lore_id, 3)
        desperate = prepare_miscast(MiscastPreparationRequest(source.id, raw, old.wizard.magic_state, spell))
        self.assertEqual(len(desperate.follow_ups), 2)
        with self.assertRaises(ValueError): Result(source, desperate)

    def test_result_is_bound_to_full_source_and_preparation_identifier(self):
        source = request(); result = prepare(source)
        with self.assertRaises(ValueError): Result(replace(source, id='different:prepare'), result.preparation)
        changed = replace(source.state, consumed_execution_ids=('older:action', *source.state.consumed_execution_ids))
        with self.assertRaises(ValueError): apply(changed, result)
        self.assertEqual(changed.pending_miscast, source.state.pending_miscast)

    def test_replay_and_unrelated_current_state_changes_are_rejected(self):
        source = request(); result = prepare(source); final = apply(source.state, result)
        with self.assertRaises(ValueError): apply(final, result)
        with self.assertRaises(ValueError): request(final, identifier='another:id')
        for transform in (
            lambda s: replace(s, wizard=replace(s.wizard, magic_state=WizardMagicState())),
            lambda s: replace(s, consumed_execution_ids=(*s.consumed_execution_ids, 'later')),
            lambda s: replace(s, spatial_state=replace(s.spatial_state, gave_ground_entity_ids=('enemy',))),
            lambda s: changed_roster(s, lambda p: replace(p, state=replace(p.state, holds_shield=True))),
        ):
            with self.subTest(transform=transform), self.assertRaises(ValueError): transform(final)

    def test_prepared_prefix_cannot_be_dropped_combined_or_replaced_by_foreign_type(self):
        source = request(); final = prepare(source).state
        with self.assertRaises(ValueError): replace(final, pending_miscast_continuation=None)
        with self.assertRaises(ValueError): replace(final, pending_miscast=source.state.pending_miscast)
        for value in ('pending', object(), source):
            with self.subTest(value=value), self.assertRaises(TypeError):
                replace(final, pending_miscast_continuation=value)

    def test_prepare_calls_one_pure_reducer_and_never_tests_or_rolls(self):
        source = request(); before = deepcopy(source); global_rng = getstate()
        with patch('towr.rules.npc_roster_miscast_resolution.prepare_miscast', wraps=prepare_miscast) as reducer, \
             patch('towr.rules.miscast_resolution.resolve_miscast_roll', side_effect=AssertionError('no roll')), \
             patch('towr.rules.miscast_effect_resolution.resolve_unnatural_wind', side_effect=AssertionError('no effect')), \
             patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no Test')), \
             patch('random.Random', side_effect=AssertionError('no RNG')):
            result = prepare(source)
            self.assertEqual(apply(source.state, result), result.state)
            self.assertEqual(result.state, result.state)
        self.assertEqual(reducer.call_count, 1)
        self.assertEqual(source, before)
        self.assertEqual(getstate(), global_rng)

    def test_unexpected_preparation_failure_propagates_without_partial_state(self):
        source = request(); before = deepcopy(source); failure = ValueError('preparation failed')
        with patch('towr.rules.npc_roster_miscast_resolution.prepare_miscast', side_effect=failure) as reducer:
            with self.assertRaises(ValueError) as caught: prepare(source)
        self.assertIs(caught.exception, failure)
        self.assertEqual(reducer.call_count, 1)
        self.assertEqual(source, before)

    def test_types_and_nonblank_phase_identifier(self):
        source = request(); result = prepare(source)
        for value in (None, source.state, result):
            with self.assertRaises(TypeError): prepare(value)
        for state, value in ((None, result), (source, result), (source.state, None), (source.state, source)):
            with self.assertRaises(TypeError): apply(state, value)
        for value in (None, 1, True):
            with self.assertRaises(TypeError): replace(source, id=value)
        for value in ('', ' ', '\t'):
            with self.assertRaises(ValueError): replace(source, id=value)
        with self.assertRaises(TypeError): replace(source, state=None)
        with self.assertRaises(TypeError): Result(source.state, result.preparation)
        with self.assertRaises(TypeError): Result(source, None)

    def test_models_are_frozen_slotted_and_source_graph_is_finite(self):
        source = request(); result = prepare(source); final = result.state
        for value in (source.facts, source, result):
            self.assertFalse(hasattr(value, '__dict__'))
            with self.assertRaises(FrozenInstanceError): setattr(value, fields(value)[0].name, None)
        self.assertEqual(deepcopy(result), result)
        self.assertEqual(deepcopy(final), final)
        self.assertIsNone(result.source.state.pending_miscast_continuation)
        with self.assertRaises(ValueError): replace(source, state=final)


if __name__ == '__main__':
    unittest.main()
