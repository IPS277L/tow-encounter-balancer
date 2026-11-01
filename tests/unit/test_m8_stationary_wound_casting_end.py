"""Explicit stationary Casting/end source, expiry and no-test boundaries."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from tests.helpers import SequenceRandom
from tests.integration.test_m8_champion_casting_handoff import wizard_turn
from tests.unit.test_m8_npc_roster_casting import bound_request
from tests.unit.test_m8_stationary_wound_context import post_stand, active_six
from towr.domain.condition_models import Condition
from towr.domain.injury_models import WoundConditionSourceSnapshot
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult
from towr.domain.npc_stationary_wound_models import NpcStationaryWoundContext as Context
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.test_models import InlineProfile
from towr.domain.npc_roster_casting_models import NpcRosterCastingTargetContext
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.rules.npc_roster_casting_resolution import prepare_npc_roster_casting, apply_npc_roster_casting_result
from towr.rules.npc_wound_turn_end import end_npc_wound_turn, apply_npc_wound_turn_end_result


def prepared(state, **changes):
    caster = state.roster.participant(state.wizard.actor_id)
    fixture = bound_request().casting
    arguments = dict(request_id='stationary:cast', state=state, selected_zone_id='arena',
        targets=tuple(NpcRosterCastingTargetContext(p.state.actor_id, InlineProfile(3, 3), False)
                      for p in state.roster.participants if p.state.side is not caster.state.side),
        facts=fixture.facts, policy=fixture.policy,
        stationary_wounds=Context(state, state.wizard.actor_id, True))
    return prepare_npc_roster_casting(**(arguments | changes))


def executed(state):
    request = prepared(state)
    result = NpcRosterCastingResult(request, execute_cowardly_flight_casting(
        request.casting, SequenceRandom((10, 10, 10))))
    return apply_npc_roster_casting_result(state, result)


def ending(state, *, other=False):
    return NpcWoundTurnEndRequest('stationary:end', state, state.wizard.actor_id,
        (WoundConditionSourceSnapshot(Condition.DRAINED, other),) if state.wound_expiries else (),
        stationary_wounds=Context(state, state.wizard.actor_id, True))


class StationaryCastingEndTests(unittest.TestCase):
    def test_actual_leg_cast_and_end_preserve_owner_histories(self):
        source = post_stand(actual=True)
        before = deepcopy(source)
        current = executed(source)
        original = source.roster.participant('wizard').state.injury
        request = ending(current)
        result = end_npc_wound_turn(request)
        final = apply_npc_wound_turn_end_result(current, result)
        self.assertEqual(final.roster.participant('wizard').state.injury, original)
        self.assertEqual(final.spatial_state, source.spatial_state)
        self.assertEqual(final.champion_attack.daily_wounds, source.champion_attack.daily_wounds)
        self.assertEqual(final.champion_attack.consumed_wound_roll_ids, source.champion_attack.consumed_wound_roll_ids)
        self.assertEqual(final.roster, final.champion_attack.roster)
        self.assertEqual(final.roster, final.minion_attack.roster)
        self.assertEqual(source, before)
        self.assertIsNone(final.round_state.active_turn)
        self.assertEqual(final.wound_turn_end_receipts[-1].id, request.id)

    def test_active_six_casts_and_expires_without_treating_either_wound(self):
        source = wizard_turn(active_six())
        before = deepcopy(source)
        current = executed(source)
        self.assertTrue(current.roster.participant(current.wizard.actor_id).state.injury.conditions.has(Condition.DRAINED))
        final = end_npc_wound_turn(ending(current)).state
        ctx = Context(final, final.wizard.actor_id, True)
        self.assertFalse(ctx.injury.conditions.has(Condition.DRAINED))
        self.assertEqual(ctx.injury.wounds, source.roster.participant(source.wizard.actor_id).state.injury.wounds)
        self.assertEqual(len(ctx.expired_stomach_blow_attack_ids), 1)
        self.assertEqual(len(ctx.terrain_effects), 1)
        self.assertFalse(final.wound_expiries)
        self.assertFalse(any(w.treated or w.healed for w in ctx.injury.wounds))
        self.assertEqual(source, before)

    def test_none_keeps_old_casting_and_end_rejections(self):
        state = post_stand()
        with self.assertRaisesRegex(ValueError, 'unsupported Wound'):
            prepared(state, stationary_wounds=None)
        current = executed(state)
        with self.assertRaisesRegex(ValueError, 'unsupported end-turn Wound'):
            replace(ending(current), stationary_wounds=None)

    def test_context_type_foreign_source_and_role_are_checked(self):
        state = post_stand()
        request = prepared(state)
        for bad in (True, {}, object()):
            with self.assertRaises(TypeError): replace(request, stationary_wounds=bad)
        foreign = replace(state, consumed_execution_ids=(*state.consumed_execution_ids, 'foreign'))
        with self.assertRaises(ValueError):
            replace(request, stationary_wounds=Context(foreign, foreign.wizard.actor_id, True))
        current = executed(state)
        end = ending(current)
        with self.assertRaises(ValueError): replace(end, actor_id='ally')
        with self.assertRaises(ValueError): replace(end, stationary_wounds=request.stationary_wounds)

    def test_external_or_wrong_expiry_snapshots_cannot_preserve_drained(self):
        current = executed(wizard_turn(active_six()))
        with self.assertRaises(ValueError): ending(current, other=True)
        with self.assertRaises(ValueError): replace(ending(current), condition_sources=())
        with self.assertRaises(ValueError):
            replace(ending(current), condition_sources=(WoundConditionSourceSnapshot(Condition.STAGGERED, False),))

    def test_end_schedules_once_without_rng_test_or_reexecution(self):
        current = executed(post_stand())
        request = ending(current)
        from towr.rules.turn_resolution import end_combat_turn
        with (patch('towr.rules.npc_wound_turn_end.end_combat_turn', wraps=end_combat_turn) as scheduler,
              patch('towr.rules.test_resolution.resolve_test', side_effect=AssertionError('no Test'))):
            result = end_npc_wound_turn(request)
            scheduler.assert_called_once()
        with patch('towr.rules.npc_wound_turn_end.end_combat_turn', side_effect=AssertionError('no rerun')):
            final = apply_npc_wound_turn_end_result(current, result)
            self.assertEqual(final, result.state)
        with self.assertRaises(ValueError): apply_npc_wound_turn_end_result(final, result)
        foreign = replace(current, consumed_execution_ids=(*current.consumed_execution_ids, 'other'))
        with self.assertRaises(ValueError): apply_npc_wound_turn_end_result(foreign, result)


if __name__ == '__main__':
    unittest.main()
