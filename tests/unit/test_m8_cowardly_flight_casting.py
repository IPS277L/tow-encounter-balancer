from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import random
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_m8_cowardly_flight_casting_models import casting_input
from towr.domain.condition_models import Condition
from towr.domain.cowardly_flight_casting_result_models import (
    CowardlyFlightCastingResult, CowardlyFlightCastingStatus as Status,
)
from towr.domain.magic_models import (
    COWARDLY_FLIGHT_SPELL_DEFINITION, WizardMagicState,
)
from towr.domain.test_models import InlineProfile
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting as execute
from towr.rules.casting_action_execution import execute_casting_attempt


MODULE = 'towr.engine.cowardly_flight_casting.'


class CountingDice(SequenceRandom):
    def __init__(self, values):
        super().__init__(values)
        self.calls = 0

    def randint(self, start, end):
        self.calls += 1
        return super().randint(start, end)


def resolved():
    return execute(casting_input(), CountingDice([1, 2, 3, 1, 2, 3, 10, 10, 10]))


class CowardlyFlightCastingExecutionTests(unittest.TestCase):
    def test_wait_accumulates_state_consumes_one_action_and_does_not_end_turn(self):
        source = casting_input()
        rng = CountingDice([1, 10, 10])
        with patch(MODULE + 'execute_casting_attempt', wraps=execute_casting_attempt) as casting:
            result = execute(source, rng)
        casting.assert_called_once()
        self.assertEqual(rng.calls, 3)
        self.assertIs(result.source, source)
        self.assertIs(result.status, Status.WAITING)
        self.assertEqual(result.magic_state, WizardMagicState(0, 1, 'lore:battle-magic', 1))
        self.assertTrue(result.round_state.active_turn.action_slots[0].executed)
        self.assertEqual(result.round_state.completed_turn_entity_ids, ())
        self.assertEqual(tuple(t.injury for t in result.targets), tuple(t.injury for t in source.targets))
        self.assertIs(result.spatial_state, source.spatial_state)
        self.assertIsNone(result.spell)
        self.assertIsNone(result.pending_miscast)

    def test_cast_uses_latest_potency_and_stable_target_order(self):
        source = replace(casting_input(), magic_state=WizardMagicState(1, 1, 'lore:battle-magic', 1))
        rng = CountingDice([1, 2, 10, 1, 2, 10, 10, 10, 10])
        with patch(MODULE + 'execute_casting_attempt', wraps=execute_casting_attempt) as casting:
            result = execute(source, rng)
        casting.assert_called_once()
        self.assertEqual(rng.calls, 9)
        self.assertIs(result.status, Status.SPELL_RESOLVED)
        self.assertEqual(result.post_test.decision.previous_casting_successes, 3)
        self.assertEqual(result.post_test.decision.base_potency, 2)
        self.assertEqual(result.magic_state, WizardMagicState(1))
        self.assertEqual(tuple(t.actor_id for t in result.targets), ('second', 'first'))
        self.assertFalse(result.targets[0].injury.conditions.has(Condition.BROKEN))
        self.assertTrue(result.targets[1].injury.conditions.has(Condition.BROKEN))
        self.assertFalse(result.targets[1].injury.defeated)
        self.assertEqual(result.willpower.completed_movements, ())
        self.assertEqual(result.willpower.spatial_state, source.spatial_state)

    def test_zero_potency_keeps_all_target_records_without_tests(self):
        source = replace(casting_input(), magic_state=WizardMagicState(0, 3, 'lore:battle-magic', 3))
        rng = CountingDice([10, 10, 10])
        result = execute(source, rng)
        self.assertIs(result.status, Status.SPELL_RESOLVED)
        self.assertEqual(rng.calls, 3)
        self.assertEqual(len(result.spell.targets), 2)
        self.assertEqual(result.spell.follow_ups, ())
        self.assertEqual(result.zone.targets, ())
        self.assertEqual(result.willpower.targets, ())
        self.assertEqual(result.magic_state, WizardMagicState())
        self.assertEqual(tuple(t.injury for t in result.targets), tuple(t.injury for t in source.targets))

    def test_empty_zone_cast_consumes_action_and_successes_without_target_rolls(self):
        source = replace(casting_input(), selected_zone_id='empty', targets=())
        rng = CountingDice([1, 2, 3])
        result = execute(source, rng)
        self.assertIs(result.status, Status.SPELL_RESOLVED)
        self.assertEqual(result.targets, ())
        self.assertEqual(result.magic_state, WizardMagicState())
        self.assertEqual(rng.calls, 3)

    def test_pool_equal_level_still_allows_wait_and_cast(self):
        for successes in (0, 2):
            source = replace(casting_input(), magic_state=WizardMagicState(
                1, successes, 'lore:battle-magic', successes))
            values = [9, 1, 10] + ([1, 10, 10, 10, 10, 10] if successes else [])
            result = execute(source, CountingDice(values))
            self.assertIs(result.status, Status.SPELL_RESOLVED if successes else Status.WAITING)
            self.assertEqual(result.magic_state.miscast_dice, 2)
            self.assertIsNone(result.pending_miscast)

    def test_miscast_preserves_pending_source_and_successes_even_if_cv_is_ready(self):
        for previous in (0, 2):
            source = replace(casting_input(), magic_state=WizardMagicState(
                2, previous, 'lore:battle-magic', previous))
            rng = CountingDice([9, 1, 10])
            with patch(MODULE + 'resolve_spell_target_preflight', side_effect=AssertionError('no spell')):
                result = execute(source, rng)
            self.assertIs(result.status, Status.MISCAST_REQUIRED)
            self.assertEqual(rng.calls, 3)
            self.assertEqual(result.magic_state, WizardMagicState(3, previous + 1, 'lore:battle-magic', 1))
            self.assertIsNone(result.post_test.decision)
            self.assertIs(result.pending_miscast, result.post_test.miscast_pool.roll_request)
            self.assertEqual(result.pending_miscast.pool_dice_count, 3)
            self.assertEqual(result.pending_miscast.bonus_dice, 0)
            self.assertTrue(result.round_state.active_turn.action_slots[0].executed)
            with self.assertRaisesRegex(ValueError, 'mandatory Miscast'):
                replace(source, magic_state=result.magic_state)

    def test_nines_are_counted_once_and_never_rerolled(self):
        source = replace(casting_input(), caster=replace(casting_input().caster, wizard_level=1))
        rng = CountingDice([9, 9, 1])
        result = execute(source, rng)
        self.assertEqual(rng.calls, 3)
        self.assertEqual(result.execution.casting.test.trace.rerolls, ())
        self.assertEqual(result.magic_state.miscast_dice, 2)
        self.assertEqual(result.post_test.miscast_pool.dice_added, 2)
        self.assertEqual(result.pending_miscast.pool_dice_count, 2)

    def test_willpower_nines_do_not_add_caster_miscast_dice(self):
        rng = CountingDice([1, 2, 3, 9, 9, 9, 9, 9, 9])
        result = execute(casting_input(), rng)
        self.assertEqual(result.magic_state.miscast_dice, 0)
        self.assertIsNone(result.pending_miscast)

    def test_natural_single_die_uses_profile_threshold(self):
        source = casting_input()
        source = replace(source, caster=replace(source.caster, casting_profile=InlineProfile(1, 5)),
                         magic_state=WizardMagicState(0, 2, 'lore:battle-magic', 2),
                         targets=tuple(replace(t, willpower_profile=InlineProfile(1, 5)) for t in source.targets))
        result = execute(source, CountingDice([4, 4, 10]))
        self.assertIs(result.status, Status.SPELL_RESOLVED)
        self.assertTrue(result.willpower.targets[0].resisted)
        self.assertFalse(result.willpower.targets[1].resisted)

    def test_same_immutable_input_replays_but_returned_slot_cannot_repeat(self):
        source = casting_input()
        before, global_rng = deepcopy(source), random.getstate()
        first = execute(source, CountingDice([1, 10, 10]))
        self.assertEqual(first, execute(source, CountingDice([1, 10, 10])))
        self.assertEqual(source, before)
        self.assertEqual(random.getstate(), global_rng)
        with self.assertRaisesRegex(ValueError, 'unexecuted standard slot'):
            replace(source, round_state=first.round_state, magic_state=first.magic_state)

    def test_wrong_request_type_fails_before_rng(self):
        rng = CountingDice([])
        with self.assertRaises(TypeError):
            execute(None, rng)
        self.assertEqual(rng.calls, 0)

    def test_failure_propagates_without_retry_or_partial_result(self):
        problem = RuntimeError('target test unavailable')
        rng = CountingDice([1, 2, 3])
        with patch(MODULE + 'resolve_cowardly_flight_willpower_batch', side_effect=problem) as call:
            with self.assertRaises(RuntimeError) as caught:
                execute(casting_input(), rng)
        self.assertIs(caught.exception, problem)
        call.assert_called_once()
        self.assertEqual(rng.calls, 3)

    def test_canonical_definition_preserves_existing_public_export(self):
        from towr.rules.cowardly_flight_resolution import COWARDLY_FLIGHT_SPELL_DEFINITION as previous
        self.assertIs(previous, COWARDLY_FLIGHT_SPELL_DEFINITION)


class CowardlyFlightCastingResultTests(unittest.TestCase):
    def test_result_and_returned_states_are_immutable(self):
        result = resolved()
        for model, field in ((result, 'status'), (result.targets[1], 'injury')):
            self.assertFalse(hasattr(model, '__dict__'))
            with self.assertRaises(FrozenInstanceError):
                setattr(model, field, None)
        with self.assertRaises((AttributeError, TypeError)):
            result.magic_state = WizardMagicState(99)

    def test_result_rejects_untyped_required_fields(self):
        result = resolved()
        for field in ('source', 'execution', 'post_test', 'status', 'preflight', 'spell', 'zone', 'willpower'):
            with self.subTest(field=field), self.assertRaises(TypeError):
                replace(result, **{field: None})
        with self.assertRaises(TypeError):
            replace(result, status='spell_resolved')

    def test_branch_and_extra_phase_splices_are_rejected(self):
        result = resolved()
        for status in (Status.WAITING, Status.MISCAST_REQUIRED):
            with self.assertRaises(ValueError):
                replace(result, status=status)
        waiting = execute(casting_input(), CountingDice([1, 10, 10]))
        with self.assertRaisesRegex(ValueError, 'WAIT/Miscast'):
            replace(waiting, spell=result.spell)

    def test_same_ids_with_different_input_snapshots_are_rejected(self):
        result = resolved()
        source = result.source
        altered = (
            replace(source, magic_state=WizardMagicState(1)),
            replace(source, caster=replace(source.caster, wizard_level=3)),
            replace(source, caster=replace(source.caster, casting_profile=InlineProfile(3, 4))),
            replace(source, targets=(replace(source.targets[0], willpower_profile=InlineProfile(3, 4)), source.targets[1])),
            replace(source, spatial_state=replace(source.spatial_state, free_move_used_entity_ids=('wizard',))),
        )
        for changed in altered:
            with self.subTest(source=changed), self.assertRaises(ValueError):
                replace(result, source=changed)

    def test_casting_trace_and_accumulated_state_splices_are_rejected(self):
        result = resolved()
        casting = result.execution.casting
        for forged in (replace(casting, previous_casting_successes=8),
                       replace(casting, state=WizardMagicState(1, 3, 'lore:battle-magic', 3)),
                       replace(casting, follow_ups=()),
                       replace(casting, test=replace(casting.test, trace=replace(casting.test.trace, threshold=4)))):
            if forged == casting:
                continue
            with self.assertRaises(ValueError):
                replace(result, execution=replace(result.execution, casting=forged))

    def test_post_test_decision_from_another_roll_is_rejected(self):
        result = resolved()
        other = execute(result.source, CountingDice([1, 10, 10]))
        with self.assertRaises(ValueError):
            replace(result, post_test=other.post_test)

    def test_wrong_preflight_subject_or_definition_rejected(self):
        result = resolved()
        for preflight in (replace(result.preflight, selected_target_id='empty'),
                          replace(result.preflight, definition=replace(COWARDLY_FLIGHT_SPELL_DEFINITION, casting_value=4))):
            with self.assertRaises(ValueError):
                replace(result, preflight=preflight)

    def test_target_potency_and_order_splices_rejected(self):
        result = resolved()
        target = result.spell.targets[0]
        for spell in (replace(result.spell, targets=tuple(reversed(result.spell.targets))),
                      replace(result.spell, follow_ups=()),
                      replace(result.spell, targets=(replace(target, potency=replace(target.potency, effective_potency=2)),
                                                     result.spell.targets[1]))):
            with self.assertRaises(ValueError):
                replace(result, spell=spell)

    def test_zone_context_profile_and_followup_splices_rejected(self):
        result = resolved()
        zone = result.zone
        request = zone.willpower_follow_ups[0]
        forged = replace(request, test=replace(request.test, profile=InlineProfile(4, 3)))
        for changed in (replace(zone, willpower_follow_ups=()),
                        replace(zone, willpower_follow_ups=(forged, zone.willpower_follow_ups[1]))):
            with self.assertRaises(ValueError):
                replace(result, zone=changed)

    def test_willpower_order_broken_and_spatial_splices_rejected(self):
        result = resolved()
        batch = result.willpower
        broken = batch.targets[1]
        for forged in (replace(batch, targets=tuple(reversed(batch.targets))),
                       replace(batch, targets=(batch.targets[0], replace(broken, resisted=True))),
                       replace(batch, targets=(batch.targets[0], replace(broken, state=result.source.targets[1].injury))),
                       replace(batch, spatial_state=replace(batch.spatial_state, free_move_used_entity_ids=('wizard',)))):
            with self.assertRaises(ValueError):
                replace(result, willpower=forged)

    def test_pending_miscast_pool_source_cannot_be_replaced(self):
        source = replace(casting_input(), magic_state=WizardMagicState(2))
        result = execute(source, CountingDice([9, 1, 10]))
        pool = result.post_test.miscast_pool
        forged = replace(pool, roll_request=replace(pool.roll_request, source_resolution_id='foreign'))
        with self.assertRaises(ValueError):
            replace(result, post_test=replace(result.post_test, miscast_pool=forged))


if __name__ == '__main__':
    unittest.main()
