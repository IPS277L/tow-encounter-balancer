"""Actual lower Protection consumption and source refusals for ADR-0056."""
from copy import deepcopy
from dataclasses import replace
from random import getstate
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.unit.test_m8_npc_champion_attack import request as ordinary
from towr.domain.condition_models import Condition
from towr.domain.crushed_rib_test_models import CrushedRibTestPreparationRequest
from towr.domain.injury_models import CharacterInjuryState, CharacterWoundRequest, WoundRestriction
from towr.domain.npc_champion_attack_models import NpcChampionAttackRequest
from towr.domain.npc_roster_models import NpcRoster
from towr.domain.test_models import TestQuality
from towr.rules.crushed_rib_test_resolution import prepare_crushed_rib_test
from towr.rules.injury_resolution import resolve_character_wound
from towr.rules.npc_champion_attack_execution import (
    execute_npc_champion_attack as execute, apply_npc_champion_attack_result as apply,
)
from towr.rules.wound_effect_resolution import resolve_wound_effect
import towr.rules.npc_champion_attack_execution as executor


class Dice(SequenceRandom):
    def __init__(self, values):
        self.values = tuple(values)
        self.calls = 0
        super().__init__(self.values)

    def randint(self, start, end):
        self.calls += 1
        return super().randint(start, end)


def corrupt(original, /, **changes):
    result = deepcopy(original)
    for name, value in changes.items():
        object.__setattr__(result, name, value)
    return result


def pending_request():
    """Lower current snapshot with an actual rolled/resolved K1 Wound10.

    Full-root chronology is tested separately by the outer bridge. This fixture
    deliberately makes no assertion of journal membership for a lower request.
    """
    base = ordinary()
    wound = resolve_character_wound(CharacterWoundRequest('actual:rib', CharacterInjuryState()), Dice((10,)))
    injury = resolve_wound_effect(wound.effect_request, wound.state).state
    return source_with_injury(base, injury, pending=True)


def source_with_injury(base, injury, *, pending=False, consumed=None):
    target_id = base.execution.target_id
    roster = NpcRoster(tuple(replace(p, state=replace(p.state, injury=injury))
        if p.state.actor_id == target_id else p for p in base.state.roster.participants))
    state = replace(base.state, roster=roster)
    execution = replace(base.execution, kernel_request=replace(base.execution.kernel_request, target_state=injury))
    preparation = (prepare_crushed_rib_test(CrushedRibTestPreparationRequest(
        execution.id + ':crushed-rib', target_id, injury, base.preparation.attack.defender_test)) if pending else None)
    return NpcChampionAttackRequest(state, base.preparation, execution,
        crushed_rib_preparation=preparation, crushed_rib_consumption=consumed)


class CrushedRibProtectionTests(unittest.TestCase):
    def test_preparation_retains_original_normal_attack_and_injury(self):
        source = pending_request()
        before, global_rng = deepcopy(source), getstate()
        self.assertEqual(source.preparation.attack.defender_test.quality_modifiers, ())
        self.assertEqual(source.execution.kernel_request.target_state,
                         source.crushed_rib_preparation.source_request.state)
        self.assertNotEqual(source.effective_attack.defender_test,
                            source.preparation.attack.defender_test)
        self.assertEqual(source.effective_attack.attacker_test, source.preparation.attack.attacker_test)
        self.assertEqual(source, before)
        self.assertEqual(getstate(), global_rng)

    def test_both_fail_and_defender_failed_reroll_consume_without_extra_rolls(self):
        for values in ((10,) * 6, (10, 10, 10, 1, 10, 10, 9)):
            with self.subTest(values=values):
                source = pending_request()
                before = deepcopy(source)
                dice = Dice(values)
                with patch.object(executor, 'resolve_attack', wraps=executor.resolve_attack) as resolve:
                    result = execute(source, dice)
                resolve.assert_called_once_with(source.effective_attack, dice, decisions=None)
                self.assertEqual(dice.calls, len(values))
                self.assertIs(result.crushed_rib.test, result.execution.resolution.attack.defender_test)
                self.assertIs(result.crushed_rib.test.trace.quality, TestQuality.GRIM)
                self.assertEqual(result.crushed_rib.test.successes, 0)
                self.assertEqual(result.resolution.target_state, result.crushed_rib.state)
                self.assertEqual(result.state.daily_wounds, source.state.daily_wounds)
                self.assertEqual(result.state.consumed_wound_roll_ids, source.state.consumed_wound_roll_ids)
                self.assertEqual(source, before)
                self.assertEqual(apply(source.state, result), result.state)
                with self.assertRaises(ValueError):
                    apply(result.state, result)

    def test_full_wound_lifecycle_starts_after_consumption_and_keeps_new_pending10(self):
        source = pending_request()
        calls = []
        complete = executor.complete_crushed_rib_test
        continue_attack = executor._resolve_kernel_attack_after_test

        def completed(*args):
            result = complete(*args)
            calls.append('consumed')
            return result

        def consequences(kernel, attack, rng, **kwargs):
            self.assertEqual(calls, ['consumed'])
            self.assertEqual(kernel.target_state.active_wound_effects,
                             source.execution.kernel_request.target_state.active_wound_effects[:1])
            self.assertIs(attack.defender_test.trace.quality, TestQuality.GRIM)
            calls.append('consequences')
            return continue_attack(kernel, attack, rng, **kwargs)

        dice = Dice((1, 2, 3, 1, 10, 10, 9, 5, 5))
        with patch.object(executor, 'complete_crushed_rib_test', side_effect=completed), \
             patch.object(executor, '_resolve_kernel_attack_after_test', side_effect=consequences):
            result = execute(source, dice)
        self.assertEqual(dice.calls, 9)
        self.assertEqual(calls, ['consumed', 'consequences'])
        self.assertEqual(result.completion.source_request.roll.source_request.wound.state, result.crushed_rib.state)
        self.assertEqual(result.post_test_kernel_request.target_state, result.crushed_rib.state)
        self.assertEqual(result.post_test_kernel_request.attack, source.effective_attack)
        self.assertEqual(tuple(w.table_total for w in result.resolution.target_state.wounds), (10, 10))
        pending = tuple(e for e in result.resolution.target_state.active_wound_effects
                        if getattr(e, 'restriction', None) is WoundRestriction.NEXT_TEST_IS_GRIM)
        self.assertEqual(tuple(e.wound_sequence for e in pending), (2,))
        self.assertEqual(len(result.state.daily_wounds.receipts), 1)
        self.assertEqual(result.state.consumed_execution_ids, (source.execution.id,))
        self.assertEqual(result.state.consumed_wound_roll_ids,
                         (source.execution.kernel_request.id + ':wound-lifecycle',))
        self.assertTrue(result.state.round_state.active_turn.action_slots[0].executed)

    def test_new_superficial_and_unsupported_wounds_are_preserved_including_pending(self):
        for rolls, total, has_pending in (((1, 1), 2, False), ((1, 3), 4, True), ((1, 5), 6, False), ((6, 7), 13, False)):
            with self.subTest(total=total):
                source = pending_request()
                result = execute(source, Dice((1, 2, 3, 10, 10, 10, *rolls)))
                injury = result.resolution.target_state
                self.assertEqual(injury.wounds[-1].table_total, total)
                self.assertEqual(injury.wounds[:-1], result.crushed_rib.state.wounds)
                self.assertTrue(injury.conditions.has(Condition.DRAINED))
                self.assertEqual(injury.active_wound_effects[0], result.crushed_rib.state.active_wound_effects[0])
                self.assertEqual(result.state.pending is not None, has_pending)
                self.assertEqual(len(result.state.daily_wounds.receipts), 1)

    def test_new_stagger_is_retained_after_actual_protection_consumption(self):
        source = pending_request()
        result = execute(source, Dice((1, 10, 10, 10, 10, 10)))
        self.assertIsNotNone(result.crushed_rib)
        self.assertTrue(result.resolution.target_state.conditions.has(Condition.STAGGERED))
        self.assertTrue(result.resolution.target_state.conditions.has(Condition.DRAINED))
        self.assertNotEqual(result.resolution.target_state, result.crushed_rib.state)

    def test_consumed_receipt_admits_normal_lower_protection_without_second_consumption(self):
        first = execute(pending_request(), Dice((10,) * 6))
        source = source_with_injury(ordinary(), first.crushed_rib.state, consumed=first.crushed_rib)
        dice = Dice((10,) * 6)
        result = execute(source, dice)
        self.assertEqual(dice.calls, 6)
        self.assertIsNone(result.crushed_rib)
        self.assertIs(result.execution.resolution.attack.defender_test.trace.quality, TestQuality.NORMAL)
        self.assertEqual(result.resolution.target_state, first.crushed_rib.state)

    def test_pending_consumed_mutual_exclusion_foreign_actor_and_injury(self):
        source = pending_request()
        first = execute(source, Dice((10,) * 6))
        cases = (
            dict(crushed_rib_consumption=first.crushed_rib),
            dict(crushed_rib_preparation=corrupt(source.crushed_rib_preparation,
                source_request=replace(source.crushed_rib_preparation.source_request, actor_id='foreign'))),
        )
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises((TypeError, ValueError)):
                replace(source, **changes)
        with self.assertRaises(ValueError):
            replace(source, crushed_rib_preparation=None, crushed_rib_consumption=first.crushed_rib)

    def test_original_aliases_and_lists_fail_before_injected_rng(self):
        source = pending_request()
        mutations = (
            lambda s: object.__setattr__(s.execution.kernel_request, 'can_target_leave_zone', 1),
            lambda s: object.__setattr__(s.preparation.protection.source_request, 'defender_is_aware', 1),
            lambda s: object.__setattr__(s.preparation.protection.source_request, 'options',
                list(s.preparation.protection.source_request.options)),
            lambda s: object.__setattr__(s.preparation.npc_attack.snapshot.profiles[0].test_profile, 'dice', True),
            lambda s: object.__setattr__(s.crushed_rib_preparation.source_request.state.wounds[0], 'sequence', True),
            lambda s: object.__setattr__(s.preparation.npc_attack.attack.impact_spec, 'ignores_armour', 0),
            lambda s: object.__setattr__(s.preparation.npc_attack, 'applied_rule_ids',
                list(s.preparation.npc_attack.applied_rule_ids)),
            lambda s: object.__setattr__(s.preparation.protection, 'eligible_skills',
                tuple(skill.value for skill in s.preparation.protection.eligible_skills)),
            lambda s: object.__setattr__(s.execution.kernel_request.attack, 'is_close_range', 0),
        )
        for index, mutation in enumerate(mutations):
            bad = deepcopy(source)
            mutation(bad)
            dice = Dice(())
            with self.subTest(index=index), self.assertRaises((TypeError, ValueError)):
                execute(bad, dice)
            self.assertEqual(dice.calls, 0)

    def test_detached_actual_trace_aliases_damage_and_receipt_are_not_accepted(self):
        result = execute(pending_request(), Dice((10,) * 6))
        raw = result.execution.resolution
        for attack in (
            corrupt(raw.attack, outcome=raw.attack.outcome.value),
            corrupt(raw.attack, success_margin=False),
            corrupt(raw.attack, attacker_test=corrupt(raw.attack.attacker_test,
                trace=corrupt(raw.attack.attacker_test.trace, success_delta=False))),
            corrupt(raw.attack, defender_test=corrupt(raw.attack.defender_test,
                trace=corrupt(raw.attack.defender_test.trace, quality='grim'))),
        ):
            with self.subTest(attack=attack), self.assertRaises((TypeError, ValueError)):
                replace(result, execution=replace(result.execution, resolution=replace(raw, attack=attack)))
        with self.assertRaises((TypeError, ValueError)):
            replace(result, crushed_rib=None)
        with self.assertRaises((TypeError, ValueError)):
            replace(result, crushed_rib=corrupt(result.crushed_rib,
                source=corrupt(result.crushed_rib.source, effect=corrupt(result.crushed_rib.consumed_effect,
                    wound_sequence=True))))

    def test_same_id_wrong_kernel_wound_source_and_dropped_consequences_rejected(self):
        source = pending_request()
        result = execute(source, Dice((1, 2, 3, 10, 10, 10, 1, 1)))
        raw = result.execution.resolution
        roll = raw.pending_character_wound
        foreign_roll = corrupt(roll, source_request=corrupt(roll.source_request,
            wound=corrupt(roll.source_request.wound, state=source.execution.kernel_request.target_state)))
        with self.assertRaises(ValueError):
            replace(result, execution=replace(result.execution,
                resolution=replace(raw, pending_character_wound=foreign_roll)))
        with self.assertRaises(ValueError):
            replace(result, resolution=replace(result.resolution, target_state=result.crushed_rib.state))

    def test_invalid_result_and_stale_apply_do_not_rerun_rules(self):
        source = pending_request()
        result = execute(source, Dice((10,) * 6))
        with patch.object(executor, 'resolve_attack', side_effect=AssertionError('rerolled')):
            self.assertEqual(apply(source.state, result), result.state)
            with self.assertRaises(ValueError):
                apply(result.state, result)
            with self.assertRaises((TypeError, ValueError)):
                apply(source.state, corrupt(result, crushed_rib=None))


if __name__ == '__main__':
    unittest.main()
