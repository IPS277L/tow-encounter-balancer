"""Actual first Wound10 source; narrow Casting completion/owner admission."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.unit.test_m8_npc_magic_scenario_runner import admitted, Dice
from tests.unit.test_m8_npc_roster_casting import bound_request
from towr.domain.condition_models import Condition
from towr.domain.crushed_rib_test_models import CrushedRibCastingPreparationRequest
from towr.domain.cowardly_flight_casting_result_models import CowardlyFlightCastingStatus as Status
from towr.domain.npc_crushed_rib_models import NpcCrushedRibContext as Context, NpcCrushedRibConsumptionWitness as Witness
from towr.domain.npc_roster_casting_models import NpcRosterCastingRequest, NpcRosterCastingResult, NpcRosterCastingTargetContext
from towr.domain.test_models import InlineProfile, TestQuality
from towr.domain.turn_models import CombatSide
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.rules.crushed_rib_test_resolution import prepare_crushed_rib_casting
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting, apply_npc_roster_casting_result


def first_ten(*, threshold=3, level=4):
    scenario = admitted(wizard_side=CombatSide.OPPOSITION)
    initial = replace(scenario.initial, wizard=replace(scenario.initial.wizard,
        caster=replace(scenario.initial.wizard.caster, wizard_level=level, casting_profile=InlineProfile(3, threshold))))
    scenario = replace(scenario, initial=initial, actors=tuple(
        replace(a, willpower_profile=InlineProfile(3, threshold)) if a.actor_id == 'wizard' else a
        for a in scenario.actors))
    dice = Dice((1, 2, 3, 10, 10, 10, 10))
    stopped = run_npc_magic_scenario(scenario, dice)
    dice.exhausted()
    assert stopped.current.roster.participant('wizard').state.injury.wounds[0].table_total == 10
    return stopped.current


def prepared(state=None, *, identifier='crushed:casting', context=None, can_move=False):
    state = first_ten() if state is None else state
    caster = state.roster.participant(state.wizard.actor_id)
    fixture = bound_request().casting
    return prepare_npc_roster_casting(request_id=identifier, state=state, selected_zone_id='arena',
        targets=tuple(NpcRosterCastingTargetContext(p.state.actor_id, InlineProfile(3, 3), can_move)
                      for p in state.roster.participants if p.state.side is not caster.state.side),
        facts=fixture.facts, policy=fixture.policy,
        crushed_rib_context=Context(state, caster.state.actor_id, True) if context is None else context)


def execute(request, values):
    dice = Dice(values)
    lower = execute_cowardly_flight_casting(request.casting, dice)
    dice.exhausted()
    result = NpcRosterCastingResult(request, lower)
    return result, apply_npc_roster_casting_result(request.state, result)


class CrushedRibCastingTests(unittest.TestCase):
    def test_failed_test_consumes_once_before_pool_and_preserves_full_owner(self):
        request = prepared()
        before = deepcopy(request)
        with patch('towr.engine.cowardly_flight_casting.execute_casting_attempt',
                   wraps=__import__('towr.rules.casting_action_execution', fromlist=['execute_casting_attempt']).execute_casting_attempt) as attempt:
            result, state = execute(request, (1, 9, 10, 9))
        attempt.assert_called_once()
        self.assertIs(result.casting.status, Status.WAITING)
        receipt = result.casting.crushed_rib
        self.assertEqual(receipt.casting.test.successes, 0)
        self.assertEqual(receipt.casting.test.trace.final_values, (9, 9, 10))
        self.assertEqual(result.casting.magic_state.miscast_dice, 2)
        self.assertIs(state.roster.participant('wizard').state.injury, receipt.state)
        self.assertTrue(receipt.state.conditions.has(Condition.DRAINED))
        self.assertEqual(len(receipt.state.active_wound_effects), 1)
        self.assertEqual(receipt.state.wounds, request.crushed_rib_context.injury.wounds)
        self.assertEqual(state.roster, state.champion_attack.roster)
        self.assertEqual(state.roster, state.minion_attack.roster)
        self.assertEqual(state.champion_attack.daily_wounds, request.state.champion_attack.daily_wounds)
        self.assertEqual(state.champion_attack.consumed_wound_roll_ids, request.state.champion_attack.consumed_wound_roll_ids)
        self.assertEqual(state.consumed_execution_ids, (*request.state.consumed_execution_ids, request.casting.id))
        self.assertEqual(request, before)
        with self.assertRaises(ValueError): apply_npc_roster_casting_result(state, result)

    def test_completion_is_recorded_before_post_test_followups(self):
        request = prepared()
        events = []
        from towr.rules.crushed_rib_test_resolution import complete_crushed_rib_casting
        from towr.rules.casting_action_execution import resolve_casting_action_post_test
        def completed(*args):
            value = complete_crushed_rib_casting(*args)
            events.append(value)
            return value
        def post(*args):
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].casting, args[0].execution.casting)
            return resolve_casting_action_post_test(*args)
        with patch('towr.rules.crushed_rib_test_resolution.complete_crushed_rib_casting', side_effect=completed), \
             patch('towr.engine.cowardly_flight_casting.resolve_casting_action_post_test', side_effect=post):
            execute(request, (1, 9, 10, 9))

    def test_zero_success_without_rerolls_and_owned_nine_lock(self):
        for state, values, rerolls in ((first_ten(), (8, 9, 10), ()),
                                       (first_ten(threshold=9), (9, 1, 10, 9), (1,))):
            with self.subTest(threshold=state.wizard.caster.casting_profile.threshold):
                result, final = execute(prepared(state), values)
                trace = result.casting.crushed_rib.casting.test.trace
                self.assertEqual(tuple(r.index for r in trace.rerolls), rerolls)
                self.assertEqual(trace.applied_rule_ids, ('RULE-WOUND-TABLE:crushed_rib', 'RULE-MAGIC-003:rule-of-nine'))
                self.assertEqual(len(final.roster.participant('wizard').state.injury.active_wound_effects), 1)

    def test_miscast_pending_retains_consumed_injury_and_blocks_next_action(self):
        result, final = execute(prepared(first_ten(level=2)), (9, 9, 9))
        self.assertIs(result.casting.status, Status.MISCAST_REQUIRED)
        self.assertIs(final.pending_miscast, result.casting)
        self.assertEqual(final.wizard.magic_state.miscast_dice, 3)
        self.assertEqual(final.roster.participant('wizard').state.injury, result.casting.crushed_rib.state)
        with self.assertRaises(ValueError): Context(final, 'wizard', True, Witness(result, result.casting.crushed_rib))
        bad = deepcopy(final)
        object.__setattr__(bad.roster.participant('wizard').state.injury, 'active_wound_effects',
                           result.source.crushed_rib_context.injury.active_wound_effects)
        with self.assertRaises(ValueError): replace(bad)

    def test_no_context_and_missing_lower_preparation_are_refused(self):
        request = prepared()
        with self.assertRaises(ValueError): replace(request, crushed_rib_context=None)
        normal = replace(request.casting, crushed_rib_preparation=None)
        with self.assertRaises(ValueError): replace(request, casting=normal)
        with self.assertRaisesRegex(ValueError, 'Wound10'):
            NpcRosterCastingRequest(request.state, normal)
        result, final = execute(request, (10, 10, 10))
        self.assertIsNotNone(Context(final, 'wizard', True, Witness(result, result.casting.crushed_rib)))
        self.assertIsNone(final.pending_miscast)

    def test_preparation_full_action_binding_not_only_test_id(self):
        request = prepared()
        prep = request.casting.crushed_rib_preparation
        for casting in (replace(prep.source_request.casting, id='foreign'),
                        replace(prep.source_request.casting, state=replace(prep.source_request.casting.state, miscast_dice=1)),
                        replace(prep.source_request.casting, test=replace(prep.source_request.casting.test, profile=InlineProfile(3, 4)))):
            with self.subTest(casting=casting):
                foreign = prepare_crushed_rib_casting(replace(prep.source_request, casting=casting))
                with self.assertRaises(ValueError): replace(request.casting, crushed_rib_preparation=foreign)

    def test_original_nested_aliases_rejected_before_rng_or_result_equality(self):
        request = prepared()
        bad = deepcopy(request.casting)
        object.__setattr__(bad.crushed_rib_preparation.source_request.state.wounds[0], 'effect_resolved', 1)
        dice = Dice(())
        with self.assertRaises(TypeError): execute_cowardly_flight_casting(bad, dice)
        self.assertEqual(dice.calls, 0)
        result, _ = execute(request, (1, 9, 10, 9))
        for location in ('execution', 'completion'):
            with self.subTest(location=location):
                lower = deepcopy(result.casting)
                casting = deepcopy(lower.execution.casting)
                object.__setattr__(casting.test.trace, 'initial_values', (True, 9, 10))
                if location == 'execution': object.__setattr__(lower.execution, 'casting', casting)
                else: object.__setattr__(lower.crushed_rib, 'casting', casting)
                self.assertEqual(lower, result.casting)
                with self.assertRaises(TypeError): replace(lower)

    def test_result_rejects_missing_foreign_or_forged_completion(self):
        request = prepared()
        result, _ = execute(request, (10, 10, 10))
        with self.assertRaises(TypeError): replace(result.casting, crushed_rib=None)
        foreign, _ = execute(prepared(identifier='other:casting'), (10, 10, 10))
        with self.assertRaises(ValueError): replace(result.casting, crushed_rib=foreign.casting.crushed_rib)
        forged = deepcopy(result)
        object.__setattr__(forged.source, 'crushed_rib_context', None)
        with self.assertRaises(ValueError): apply_npc_roster_casting_result(request.state, forged)

    def test_detached_post_test_sources_do_not_launder_equal_primitive_aliases(self):
        result, _ = execute(prepared(), (9, 10, 10))
        for label in ('pool-outcome', 'pool-count', 'decision-choice', 'magic-count', 'receipt-round', 'post-execution'):
            with self.subTest(label=label):
                bad = deepcopy(result.casting)
                if label == 'pool-outcome':
                    object.__setattr__(bad.post_test.miscast_pool, 'outcome', bad.post_test.miscast_pool.outcome.value)
                elif label == 'pool-count': object.__setattr__(bad.post_test.miscast_pool, 'dice_added', True)
                elif label == 'decision-choice':
                    object.__setattr__(bad.post_test.decision, 'choice', bad.post_test.decision.choice.value)
                elif label == 'magic-count': object.__setattr__(bad.post_test.state, 'miscast_dice', True)
                elif label == 'receipt-round': object.__setattr__(bad.execution.slot.execution, 'round_number', True)
                else:
                    execution = deepcopy(bad.post_test.execution)
                    object.__setattr__(execution.casting.test.trace, 'quality', 'grim')
                    object.__setattr__(bad.post_test, 'execution', execution)
                self.assertEqual(bad, result.casting)
                with self.assertRaises(TypeError): replace(bad)

    def test_lower_none_cannot_hide_wound10_upper_source_after_unpickling(self):
        result, _ = execute(prepared(), (10, 10, 10))
        bad = deepcopy(result.source)
        object.__setattr__(bad, 'crushed_rib_context', None)
        object.__setattr__(bad.casting, 'crushed_rib_preparation', None)
        normal = execute_cowardly_flight_casting(bad.casting, Dice((10, 10, 10)))
        with self.assertRaisesRegex(ValueError, 'Wound10'):
            NpcRosterCastingResult(bad, normal)

    def test_source_facts_and_original_containers_fail_before_any_casting_rng(self):
        original = prepared().casting
        for label in ('fact', 'targets', 'round-sides', 'placements'):
            with self.subTest(label=label):
                bad = deepcopy(original)
                if label == 'fact': object.__setattr__(bad.facts, 'no_other_test_modifiers', 1)
                elif label == 'targets': object.__setattr__(bad, 'targets', list(bad.targets))
                elif label == 'round-sides': object.__setattr__(bad.round_state, 'side_order', list(bad.round_state.side_order))
                else: object.__setattr__(bad.spatial_state, 'placements', list(bad.spatial_state.placements))
                snapshot = deepcopy(bad)
                dice = Dice(())
                with self.assertRaises(TypeError): execute_cowardly_flight_casting(bad, dice)
                self.assertEqual(dice.calls, 0)
                self.assertEqual(bad, snapshot)
                with self.assertRaises(TypeError): replace(bad)


if __name__ == '__main__':
    unittest.main()
