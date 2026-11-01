"""Actual repeated9 full-owner stand and existing stationary Casting/end."""
from copy import deepcopy
from dataclasses import replace
from random import getstate
import unittest

from tests.unit.test_m8_repeated_leg_spasm_stand import actual, stand, apply
from tests.unit.test_m8_stationary_wound_casting_end import prepared, executed, ending
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_step_models import NpcMagicStep, NpcMagicUnsupportedReason
from towr.domain.npc_magic_journal_policy import validate_magic_step_policy
from towr.domain.npc_magic_scenario_result_models import diagnose_npc_magic_unsupported
from towr.domain.npc_roster_leg_spasm_models import NpcRosterLegSpasmStandRequest
from towr.domain.npc_roster_prone_models import NpcRosterProneStandRequest
from towr.domain.npc_stationary_wound_models import NpcStationaryWoundContext
from towr.rules.npc_wound_turn_end import end_npc_wound_turn, apply_npc_wound_turn_end_result


class RepeatedLegSpasmStandIntegrationTests(unittest.TestCase):
    def test_actual_two_wounds_stand_then_existing_context_casting_end(self):
        global_rng = getstate()
        stopped, source = actual()
        before = deepcopy(source)
        result = stand(source)
        current = apply(source.state, result)
        context = NpcStationaryWoundContext(current, 'wizard', True)
        self.assertEqual(len(context.terrain_effects), 2)
        self.assertEqual(context.condition_effects, ())
        self.assertFalse(context.can_give_ground)
        self.assertEqual(context.active_stomach_blows, ())
        self.assertEqual(context.expired_stomach_blow_attack_ids, ())
        self.assertEqual(tuple(w.roll_values for w in context.injury.wounds), ((9,), (4, 5)))
        casting = prepared(current)
        self.assertEqual(casting.stationary_wounds, context)
        current = executed(current)
        self.assertTrue(current.round_state.active_turn.action_slots[0].executed)
        self.assertEqual(current.roster.participant('wizard').state.injury, context.injury)
        end = end_npc_wound_turn(ending(current))
        final = apply_npc_wound_turn_end_result(current, end)
        self.assertIsNone(final.round_state.active_turn)
        self.assertIn('wizard', final.round_state.completed_turn_entity_ids)
        self.assertEqual(final.spatial_state, result.state.spatial_state)
        self.assertEqual(final.roster.participant('wizard').state.injury, context.injury)
        self.assertEqual(final.champion_attack.daily_wounds, source.state.champion_attack.daily_wounds)
        self.assertEqual(final.champion_attack.consumed_wound_roll_ids, source.state.champion_attack.consumed_wound_roll_ids)
        self.assertEqual(final.roster, final.champion_attack.roster)
        self.assertEqual(final.roster, final.minion_attack.roster)
        self.assertFalse(any(w.treated or w.healed for w in context.injury.wounds))
        self.assertEqual(source, before)
        self.assertEqual(stopped.current, before.state)
        self.assertEqual(getstate(), global_rng)

    def test_old_stand_context_and_runner_journal_scope_remain_closed(self):
        stopped, source = actual(miscast=True)
        old = source.state
        self.assertIs(diagnose_npc_magic_unsupported(stopped.source, old, 'still:unsupported').reason,
                      NpcMagicUnsupportedReason.ACTOR_INJURY)
        for request_type in (NpcRosterLegSpasmStandRequest, NpcRosterProneStandRequest):
            with self.assertRaises(ValueError): request_type('old:stand', old, 'wizard', False, True)
        with self.assertRaises(ValueError): NpcStationaryWoundContext(old, 'wizard', True)
        result = stand(source)
        with self.assertRaises(ValueError): validate_magic_step_policy(stopped.source, NpcMagicStep(result))
        self.assertTrue(old.roster.participant('wizard').state.injury.conditions.has(Condition.PRONE))
        self.assertFalse(result.state.roster.participant('wizard').state.injury.conditions.has(Condition.PRONE))
        with self.assertRaises(ValueError): prepared(result.state, stationary_wounds=None)

    def test_equal_wound_histories_with_foreign_full_owners_cannot_be_applied(self):
        _, source = actual()
        result = stand(source)
        final = apply(source.state, result)
        old = source.state
        foreign = replace(old, wizard=replace(old.wizard,
            caster=replace(old.wizard.caster, id='another:caster')))
        self.assertEqual(foreign.roster, old.roster)
        with self.assertRaises(ValueError): apply(foreign, result)
        with self.assertRaises(ValueError): apply(final, result)
        with self.assertRaises(TypeError): replace(source, previous_stand=result)


if __name__ == '__main__':
    unittest.main()
