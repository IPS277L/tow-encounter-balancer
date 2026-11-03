"""Actual failed Endurance -> own-turn free stand -> normal M8 continuation."""
from copy import deepcopy
from dataclasses import replace
from functools import partial
import os
import pickle
import unittest
from unittest.mock import patch

from tests.integration.test_m8_battered_leg_native import native, FAILURE, SUCCESS, scripted
from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from tests.unit.test_m8_npc_magic_scenario import frame as authored_frame
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_battered_leg_policy import (
    NpcMagicBatteredLegHistory, initial_magic_battered_leg_history,
    advance_magic_battered_leg_history, magic_battered_leg_prone_stand_eligible,
)
from towr.domain.npc_magic_journal_policy import magic_scene_key
from towr.domain.npc_magic_scenario_models import NpcMagicPronePolicy
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_roster_battered_leg_models import NpcRosterBatteredLegResult
from towr.domain.npc_roster_battered_leg_prone_models import NpcRosterBatteredLegProneStandResult
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.simulation.npc_magic_models import NpcMagicSimulationRequest
from towr.simulation.npc_magic_parallel import run_npc_magic_simulation_parallel


FAIL_AND_CONTINUE = (*FAILURE, *((10,) * 9))


def source(*, stand=True, rounds=1):
    base = native(rounds=rounds)
    return replace(base, battered_leg_continuation=replace(base.battered_leg_continuation,
        prone_policy=NpcMagicPronePolicy.SELF_STAND_WHEN_SAFE if stand else None))


def actual(scenario, values):
    rng = Dice(values)
    result = run_npc_magic_scenario(scenario, rng)
    rng.exhausted()
    return result


class BatteredLegProneNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = actual(source(), FAIL_AND_CONTINUE)
        cls.index = next(i for i, s in enumerate(cls.result.steps)
                         if isinstance(s.result, NpcRosterBatteredLegProneStandResult))
        cls.stand = cls.result.steps[cls.index]

    def history_before_stand(self):
        history = initial_magic_battered_leg_history(self.result.source)
        for step in self.result.steps[:self.index]:
            history = advance_magic_battered_leg_history(self.result.source, history, step)
        return history

    def test_failure_stands_only_on_wizard_turn_then_casts_and_completes_round(self):
        result, stand = self.result, self.stand
        completion = next(s for s in result.steps if isinstance(s.result, NpcRosterBatteredLegResult))
        self.assertFalse(completion.result.endurance.test_result.succeeded)
        self.assertEqual(completion.before.round_state.active_turn.actor_id, 'enemy')
        self.assertEqual(stand.actor_id, 'wizard')
        self.assertEqual(stand.before.round_state.active_turn.actor_id, 'wizard')
        self.assertIsInstance(result.steps[self.index + 1].result, NpcRosterCastingResult)
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
        self.assertEqual((result.executed_actions, result.completed_rounds), (3, 1))
        old = stand.before.roster.participant('wizard').state.injury
        new = stand.after.roster.participant('wizard').state.injury
        self.assertEqual(new.wounds, old.wounds)
        self.assertFalse(new.conditions.has(Condition.PRONE))
        self.assertFalse(new.active_wound_effects)
        self.assertEqual(stand.before.round_state, stand.after.round_state)
        self.assertEqual(stand.before.consumed_execution_ids, stand.after.consumed_execution_ids)
        self.assertEqual(stand.before.wizard, stand.after.wizard)
        self.assertEqual(stand.before.spatial_state.placements, stand.after.spatial_state.placements)
        self.assertIn('wizard', stand.after.spatial_state.free_move_used_entity_ids)
        self.assertEqual(result.current.battered_leg_receipt.endurance, completion.result.endurance)
        self.assertEqual(result.current.battered_leg_receipt.prone_stand, stand.result)

    def test_none_prone_policy_preserves_explicit_stop_without_an_extra_roll(self):
        result = actual(source(stand=False), FAILURE)
        self.assertIs(result.outcome, Outcome.UNSUPPORTED_PATH)
        self.assertIs(result.unsupported.reason, Reason.ACTOR_INJURY)
        self.assertEqual(result.current, self.stand.before)
        self.assertFalse(any(isinstance(s.result, NpcRosterBatteredLegProneStandResult) for s in result.steps))

    def test_close_scene_and_spent_free_move_do_not_authorize_stand(self):
        scenario, state = self.result.source, self.stand.before
        history = self.history_before_stand()
        frame = scenario.frame_for(magic_scene_key(state))
        self.assertTrue(magic_battered_leg_prone_stand_eligible(scenario, state, frame, history))
        # Initial Shooting scenes forbid enemy Close. Admit an explicit later
        # placement/frame for the pure eligibility boundary instead.
        enemy_zone = state.spatial_state.placement_for('enemy').zone_id
        later_zone = next(z for z in state.spatial_state.graph.zone_ids if z != enemy_zone)
        placements = tuple(replace(p, zone_id=later_zone) for p in state.spatial_state.placements)
        close_state = replace(state, spatial_state=replace(state.spatial_state, placements=placements))
        later = authored_frame(close_state)
        close = replace(later, attack_departures=frame.attack_departures,
            pair_ranges=tuple(replace(p, target_range=RangedWeaponRange.CLOSE)
            if 'wizard' in (p.first_actor_id, p.second_actor_id) else p for p in later.pair_ranges))
        changed = replace(scenario, scene_frames=(*scenario.scene_frames, close))
        close_history = NpcMagicBatteredLegHistory(close_state, history.completion)
        self.assertFalse(magic_battered_leg_prone_stand_eligible(changed, close_state, close, close_history))
        spent = replace(state, spatial_state=replace(state.spatial_state,
            free_move_used_entity_ids=(*state.spatial_state.free_move_used_entity_ids, 'wizard')))
        spent_history = NpcMagicBatteredLegHistory(spent, history.completion)
        self.assertFalse(magic_battered_leg_prone_stand_eligible(scenario, spent, frame, spent_history))

    def test_transported_journal_requires_recorded_stand_and_matching_root_witness(self):
        transported = pickle.loads(pickle.dumps(self.result))
        self.assertEqual(replace(transported), self.result)
        with self.assertRaises(ValueError):
            replace(self.result, steps=(*self.result.steps[:self.index], *self.result.steps[self.index + 1:]))
        history = self.history_before_stand()
        with self.assertRaises(ValueError):
            NpcMagicBatteredLegHistory(self.stand.after, history.completion)
        without = replace(self.stand.after, battered_leg_receipt=replace(
            self.stand.after.battered_leg_receipt, prone_stand=None))
        with self.assertRaises(ValueError):
            NpcMagicBatteredLegHistory(without, history.completion, self.stand.result)
        with self.assertRaises(ValueError):
            replace(self.result, source=source(stand=False))

    def test_actual_new_staggered_after_stand_retains_receipt_and_scope_stop(self):
        result = actual(source(rounds=2), (*FAIL_AND_CONTINUE, 1, 10, 10, 10, 10, 10))
        self.assertIs(result.unsupported.reason, Reason.END_TURN)
        self.assertEqual(result.unsupported.missing_actor_ids, ('wizard',))
        self.assertTrue(result.current.roster.participant('wizard').state.injury.conditions.has(Condition.STAGGERED))
        self.assertIsNotNone(result.current.battered_leg_receipt.prone_stand)
        self.assertEqual((result.executed_actions, result.completed_rounds), (4, 1))

    def test_success_does_not_stand_and_raw_policy_alias_is_rejected_before_rng(self):
        result = actual(source(), SUCCESS)
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
        self.assertIsNone(result.current.battered_leg_receipt.prone_stand)
        broken = deepcopy(source())
        object.__setattr__(broken.battered_leg_continuation, 'prone_policy', 'self_stand_when_safe')
        with patch('random.Random', side_effect=AssertionError('no RNG')):
            with self.assertRaises(TypeError):
                run_npc_magic_scenario(broken, Dice(()))

    def test_one_spawn_trial_keeps_selected_policy_and_native_outcome(self):
        request = NpcMagicSimulationRequest(self.result.source, 42, 1)
        factory = partial(scripted, seeds=(request.seed_for(0),), streams=(FAIL_AND_CONTINUE,), parent_pid=os.getpid())
        result = run_npc_magic_simulation_parallel(request, workers=1, batch_size=1, rng_factory=factory)
        record, = result.trials
        self.assertEqual(record.source_scenario, self.result.source)
        self.assertEqual(record.outcome, self.result.outcome)
        self.assertEqual((record.executed_action_count, record.started_round_count, record.completed_round_count),
                         (self.result.executed_actions, self.result.started_rounds, self.result.completed_rounds))

    def test_pending_miscast_after_stand_preserves_completion_and_stand_receipt(self):
        result = actual(source(), (*FAILURE, 9, 9, 9))
        self.assertIs(result.unsupported.reason, Reason.MISCAST_PREPARATION)
        self.assertIsNotNone(result.current.pending_miscast)
        self.assertIsNotNone(result.current.battered_leg_receipt.prone_stand)
        self.assertFalse(result.current.roster.participant('wizard').state.injury.conditions.has(Condition.PRONE))


if __name__ == '__main__':
    unittest.main()
