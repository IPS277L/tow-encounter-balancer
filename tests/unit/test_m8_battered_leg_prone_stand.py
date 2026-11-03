"""Full-owner Battered Leg self-stand preserves provenance and action budget."""
from copy import deepcopy
from dataclasses import replace
import unittest

from tests.helpers import SequenceRandom
from tests.unit.test_m8_battered_leg_owner import request as endurance_request
from tests.integration.test_m8_champion_casting_handoff import wizard_turn, prepare
from towr.domain.condition_models import Condition
from towr.domain.npc_roster_battered_leg_models import require_battered_leg_completion
from towr.domain.npc_roster_battered_leg_prone_models import NpcRosterBatteredLegProneStandRequest
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult
from towr.domain.npc_roster_turn_models import _validate_phase_source
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.test_models import InlineProfile
from towr.engine.cowardly_flight_casting import execute_cowardly_flight_casting
from towr.rules.npc_roster_battered_leg_resolution import execute_npc_roster_battered_leg
from towr.rules.npc_roster_battered_leg_prone_resolution import (
    stand_npc_roster_battered_leg_prone as stand,
    apply_npc_roster_battered_leg_prone_stand as apply,
)
from towr.rules.npc_roster_casting_resolution import apply_npc_roster_casting_result
from towr.rules.npc_wound_turn_end import end_npc_wound_turn


def source():
    completed = execute_npc_roster_battered_leg(
        endurance_request(), SequenceRandom((10, 10)))
    state = wizard_turn(completed.state)
    return NpcRosterBatteredLegProneStandRequest('battered:self-stand', state, state.wizard.actor_id, False)


class BatteredLegProneStandTests(unittest.TestCase):
    def test_self_stand_removes_only_sourced_prone_and_spends_only_free_move(self):
        request = source()
        before = deepcopy(request)
        result = stand(request)
        after = apply(request.state, result)
        injury = after.roster.participant(after.wizard.actor_id).state.injury
        self.assertEqual(request, before)
        self.assertFalse(injury.conditions.has(Condition.PRONE))
        self.assertEqual(injury.active_wound_effects, ())
        self.assertEqual(injury.wounds, request.state.battered_leg_receipt.endurance.wound_result.state.wounds)
        self.assertFalse(injury.wounds[0].treated)
        self.assertFalse(injury.wounds[0].healed)
        self.assertEqual(after.spatial_state.free_move_used_entity_ids,
                         (*request.state.spatial_state.free_move_used_entity_ids, request.actor_id))
        self.assertEqual(after.spatial_state.placements, request.state.spatial_state.placements)
        for field in ('round_state', 'wizard', 'consumed_execution_ids', 'wound_expiries', 'wound_turn_end_receipts'):
            self.assertEqual(getattr(after, field), getattr(request.state, field))
        for field in ('daily_wounds', 'consumed_execution_ids', 'consumed_wound_roll_ids'):
            self.assertEqual(getattr(after.champion_attack, field), getattr(request.state.champion_attack, field))
        self.assertEqual(after.champion_attack.roster, after.roster)
        self.assertEqual(after.minion_attack.roster, after.roster)
        self.assertEqual(after.battered_leg_receipt.endurance, request.state.battered_leg_receipt.endurance)
        self.assertEqual(after.battered_leg_receipt.prone_stand, result)
        self.assertEqual(after.battered_leg_receipt.completed_injury, injury)
        require_battered_leg_completion(after)

    def test_actual_casting_and_end_turn_accept_the_completed_stand(self):
        state = stand(source()).state
        casting = prepare(state)
        actual = execute_cowardly_flight_casting(casting.casting, SequenceRandom((10,) * 20))
        final = apply_npc_roster_casting_result(state, NpcRosterCastingResult(casting, actual))
        ended = end_npc_wound_turn(NpcWoundTurnEndRequest('end:stood-wizard', final, final.wizard.actor_id)).state
        self.assertIsNone(ended.round_state.active_turn)
        self.assertEqual(ended.battered_leg_receipt, state.battered_leg_receipt)
        self.assertEqual(ended.roster.participant(ended.wizard.actor_id).state.injury,
                         state.battered_leg_receipt.completed_injury)

    def test_success_or_missing_receipt_does_not_authorize_removal(self):
        completed = execute_npc_roster_battered_leg(endurance_request(), SequenceRandom((1, 10))).state
        current = wizard_turn(completed)
        with self.assertRaisesRegex(ValueError, 'failed-Test'):
            NpcRosterBatteredLegProneStandRequest('bad', current, current.wizard.actor_id, False)
        request = source()
        with self.assertRaisesRegex(ValueError, 'Endurance witness'):
            replace(request, state=replace(request.state, battered_leg_receipt=None))

    def test_close_enemy_and_non_boolean_facts_reject(self):
        request = source()
        with self.assertRaisesRegex(ValueError, 'Close Range'):
            replace(request, actor_has_enemy_in_close_range=True)
        for value in (0, 1, None, 'false'):
            with self.subTest(value=value), self.assertRaises(TypeError):
                replace(request, actor_has_enemy_in_close_range=value)

    def test_immediate_minion_turn_and_foreign_actor_reject(self):
        completed = execute_npc_roster_battered_leg(endurance_request(), SequenceRandom((10, 10))).state
        with self.assertRaisesRegex(ValueError, 'active unexecuted'):
            NpcRosterBatteredLegProneStandRequest('early', completed, completed.wizard.actor_id, False)
        with self.assertRaisesRegex(ValueError, 'owner Wizard'):
            replace(source(), actor_id='brigand:0')

    def test_spent_free_move_rejects_before_consumption(self):
        request = source()
        state = replace(request.state, spatial_state=replace(request.state.spatial_state,
            free_move_used_entity_ids=(request.actor_id,)))
        with self.assertRaisesRegex(ValueError, 'unused free movement'):
            replace(request, state=state)

    def test_duplicate_and_stale_apply_reject(self):
        request = source()
        result = stand(request)
        after = apply(request.state, result)
        with self.assertRaisesRegex(ValueError, 'stale or already consumed'):
            apply(after, result)
        with self.assertRaises(ValueError):
            replace(request, state=after)
        stale = replace(request.state, wizard=replace(request.state.wizard,
            magic_state=replace(request.state.wizard.magic_state,
                miscast_dice=request.state.wizard.magic_state.miscast_dice + 1)))
        with self.assertRaisesRegex(ValueError, 'stale or already consumed'):
            apply(stale, result)

    def test_stripped_condition_or_stand_witness_cannot_bypass_exact_injury_gate(self):
        request = source()
        result = stand(request)
        after = result.state
        stripped = replace(after, battered_leg_receipt=request.state.battered_leg_receipt)
        with self.assertRaisesRegex(ValueError, 'completed Test scope'):
            _validate_phase_source(stripped)
        with self.assertRaisesRegex(ValueError, 'Endurance witness'):
            _validate_phase_source(replace(after, battered_leg_receipt=None))

    def test_receipt_cannot_reset_same_round_stand_usage_or_rebind_completion(self):
        request = source()
        result = stand(request)
        after = result.state
        with self.assertRaisesRegex(ValueError, 'self-stand free move'):
            replace(after, spatial_state=request.state.spatial_state)
        different = replace(endurance_request(), endurance_profile=InlineProfile(2, 4))
        foreign = wizard_turn(execute_npc_roster_battered_leg(different, SequenceRandom((10, 10))).state)
        other = stand(NpcRosterBatteredLegProneStandRequest('foreign', foreign, foreign.wizard.actor_id, False))
        with self.assertRaisesRegex(ValueError, 'another Endurance completion'):
            replace(request.state.battered_leg_receipt, prone_stand=other)

    def test_new_condition_does_not_expand_the_isolated_injury_scope(self):
        request = source()
        actor = request.state.roster.participant(request.actor_id)
        injury = replace(actor.state.injury, conditions=actor.state.injury.conditions.with_condition(Condition.STAGGERED))
        roster = replace(request.state.roster, participants=tuple(
            replace(p, state=replace(p.state, injury=injury)) if p.state.actor_id == request.actor_id else p
            for p in request.state.roster.participants))
        state = replace(request.state, roster=roster,
            champion_attack=replace(request.state.champion_attack, roster=roster),
            minion_attack=replace(request.state.minion_attack, roster=roster))
        with self.assertRaisesRegex(ValueError, 'completed Test scope'):
            replace(request, state=state)

    def test_raw_aliases_in_source_and_lower_result_reject(self):
        request = deepcopy(source())
        injury = request.state.roster.participant(request.actor_id).state.injury
        object.__setattr__(injury.conditions, 'conditions', frozenset(('prone',)))
        with self.assertRaises(TypeError):
            stand(request)
        result = deepcopy(stand(source()))
        object.__setattr__(result.stand, 'actor_has_enemy_in_close_range', 0)
        with self.assertRaises(TypeError):
            replace(result)
        result = deepcopy(stand(source()))
        object.__setattr__(result.stand.state, 'round_number', float(result.stand.state.round_number))
        with self.assertRaises(TypeError):
            replace(result)


if __name__ == '__main__':
    unittest.main()
