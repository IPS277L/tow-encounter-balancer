"""ADR-0046 low-level Prone Casting handoffs, not automatic runner support."""
import unittest

from tests.integration.test_m8_npc_roster_prone_stand import prone
from tests.unit.test_m8_cowardly_flight_casting_movement import movement_input, completion_request
from tests.unit.test_m8_npc_roster_casting import bound_request
from tests.unit.test_m8_npc_magic_scenario_runner import admitted, Dice
from towr.domain.condition_models import Condition
from towr.domain.cowardly_flight_casting_result_models import CowardlyFlightCastingStatus as Status
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult, NpcRosterCastingTargetContext
from towr.domain.npc_roster_casting_completion_models import (
    NpcRosterCastingCompletionRequest, NpcRosterCastingCompletionResult,
)
from towr.domain.npc_roster_prone_models import NpcRosterProneTurnEndRequest
from towr.domain.npc_magic_scenario_result_models import diagnose_npc_magic_unsupported
from towr.domain.npc_magic_step_models import NpcMagicUnsupportedReason as Reason
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting, complete_cowardly_flight_casting
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting, apply_npc_roster_casting_result
from towr.rules.npc_roster_casting_completion_resolution import (
    apply_npc_roster_casting_completion as apply_npc_roster_casting_completion_result,
)
from towr.rules.npc_roster_prone_resolution import end_npc_roster_prone_turn


def prepare(original, state):
    cast = original.casting
    return prepare_npc_roster_casting(request_id=cast.id, state=state,
        selected_zone_id=cast.selected_zone_id,
        targets=tuple(NpcRosterCastingTargetContext(t.actor_id, t.willpower_profile, t.can_give_ground)
                      for t in cast.targets), facts=cast.facts, policy=cast.policy)


class ProneCastingIntegrationTests(unittest.TestCase):
    def test_full_owner_prone_caster_wait_resolve_and_miscast_preserve_condition(self):
        scenario = admitted()
        original = run_npc_magic_scenario(scenario, Dice((9, 9, 9))).steps[-1].result.source
        for values, status in (((1, 10, 10), Status.WAITING),
                               ((1, 2, 3, 10, 10, 10), Status.SPELL_RESOLVED),
                               ((9, 9, 9), Status.MISCAST_REQUIRED)):
            with self.subTest(status=status):
                old = prone(prone(original.state, 'wizard'), 'enemy')
                source = prepare(original, old)
                dice = Dice(values)
                result = NpcRosterCastingResult(source, execute_cowardly_flight_casting(source.casting, dice))
                final = apply_npc_roster_casting_result(old, result)
                dice.exhausted()
                self.assertIs(result.casting.status, status)
                self.assertEqual(final.roster.participant('wizard'), old.roster.participant('wizard'))
                self.assertTrue(final.roster.participant('enemy').state.injury.conditions.has(Condition.PRONE))
                self.assertEqual(final.spatial_state, old.spatial_state)
                self.assertEqual(final.consumed_execution_ids, (*old.consumed_execution_ids, source.casting.id))
                self.assertEqual(final.champion_attack.roster, final.roster)
                self.assertEqual(final.minion_attack.roster, final.roster)
                if status is Status.MISCAST_REQUIRED:
                    self.assertIs(final.pending_miscast, result.casting)
                    with self.assertRaises(ValueError):
                        NpcRosterProneTurnEndRequest('end:blocked', final, 'wizard')
                else:
                    ended = end_npc_roster_prone_turn(NpcRosterProneTurnEndRequest('end:cast', final, 'wizard')).state
                    self.assertEqual(ended.roster, final.roster)
                    self.assertEqual(ended.wizard, final.wizard)

    def test_mixed_mobile_and_prone_targets_complete_only_real_movement_then_all_tests(self):
        original = bound_request(movement_input())
        old = prone(prone(original.state, 'wizard'), 'first')
        source = prepare(original, old)
        self.assertEqual(tuple(t.can_give_ground for t in source.casting.targets), (True, False))
        self.assertTrue(all(t.can_give_ground for t in original.casting.targets))
        cast_dice = Dice((1, 2, 3))
        pending = NpcRosterCastingResult(source, execute_cowardly_flight_casting(source.casting, cast_dice))
        current = apply_npc_roster_casting_result(old, pending)
        cast_dice.exhausted()
        self.assertEqual(tuple(f.target_id for f in pending.casting.pending_movements), ('second',))
        self.assertIsNone(pending.casting.willpower)
        completion = NpcRosterCastingCompletionRequest(current, completion_request(pending.casting))
        dice = Dice((1, 2, 3, 10, 10, 10))
        result = NpcRosterCastingCompletionResult(completion, complete_cowardly_flight_casting(completion.completion, dice))
        final = apply_npc_roster_casting_completion_result(current, result)
        dice.exhausted()
        self.assertEqual(tuple(t.target_id for t in result.completion.casting.willpower.targets), ('second', 'first'))
        self.assertEqual(final.spatial_state.placement_for('second').zone_id, 'empty')
        self.assertEqual(final.spatial_state.placement_for('first').zone_id, 'arena')
        self.assertEqual(final.spatial_state.gave_ground_entity_ids, ('second',))
        self.assertTrue(final.roster.participant('first').state.injury.conditions.has(Condition.PRONE))
        self.assertTrue(final.roster.participant('first').state.injury.conditions.has(Condition.BROKEN))
        self.assertEqual(final.roster.participant('wizard'), old.roster.participant('wizard'))
        self.assertEqual(final.consumed_execution_ids, (source.casting.id,))
        self.assertIsNone(final.pending_movement)
        with self.assertRaises(ValueError):
            apply_npc_roster_casting_completion_result(final, result)

    def test_all_prone_targets_suppress_authored_departures_but_not_willpower(self):
        original = bound_request(movement_input())
        old = prone(prone(original.state, 'second'), 'first')
        source = prepare(original, old)
        dice = Dice((1, 2, 3, 1, 2, 3, 10, 10, 10))
        result = NpcRosterCastingResult(source, execute_cowardly_flight_casting(source.casting, dice))
        dice.exhausted()
        self.assertIs(result.casting.status, Status.SPELL_RESOLVED)
        self.assertEqual(result.casting.pending_movements, ())
        self.assertEqual(result.state.spatial_state, old.spatial_state)
        self.assertEqual(tuple(t.target_id for t in result.casting.willpower.targets), ('second', 'first'))

    def test_legacy_scenario_diagnosis_still_stops_prone_before_action(self):
        scenario = admitted()
        original = run_npc_magic_scenario(scenario, Dice((9, 9, 9))).steps[-1].result.source
        for actor, reason in (('wizard', Reason.ACTOR_INJURY), ('enemy', Reason.TARGET_INJURY)):
            state = prone(original.state, actor)
            diagnostic = diagnose_npc_magic_unsupported(scenario, state, 'prone:legacy')
            self.assertIs(diagnostic.reason, reason)


if __name__ == '__main__':
    unittest.main()
