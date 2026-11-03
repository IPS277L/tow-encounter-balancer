"""One declared Recover action after Battered Leg, with real source/history."""
from dataclasses import replace
import pickle
import unittest
from unittest.mock import Mock

from tests.integration.test_m8_battered_leg_native import native, FAILURE, FIRST_FIVE
from tests.unit.test_m8_npc_magic_scenario import frame as authored_frame
from tests.unit.test_m8_npc_magic_scenario_runner import Dice
from tests.unit.test_m8_miscast_continuation_policy import continuation_policy
from towr.domain.condition_models import Condition
from towr.domain.npc_magic_battered_leg_policy import (
    NpcMagicBatteredLegHistory, initial_magic_battered_leg_history,
    advance_magic_battered_leg_history, magic_battered_leg_recover_selected,
)
from towr.domain.npc_magic_scenario_models import NpcMagicPronePolicy
from towr.domain.npc_magic_scenario_result_models import diagnose_npc_magic_unsupported
from towr.domain.npc_magic_step_models import NpcMagicScenarioOutcome as Outcome, NpcMagicUnsupportedReason as Reason
from towr.domain.npc_roster_battered_leg_recover_models import NpcRosterBatteredLegRecoverRequest, NpcRosterBatteredLegRecoverResult
from towr.domain.npc_roster_casting_models import NpcRosterCastingResult
from towr.domain.ranged_weapon_profiles import RangedWeaponRange
from towr.domain.turn_models import CombatActionKind
from towr.engine.npc_magic_scenario_runner import run_npc_magic_scenario
from towr.engine.npc_roster_battered_leg_recover import execute_npc_roster_battered_leg_recover


RECOVER_ROUND = (*FAILURE, *((10,) * 6))
ACTIVE_CASTING = (9, 10, 10, *((10,) * 6), *FIRST_FIVE, 10, 10, *((10,) * 12))


def source(*, active=False, rounds=1, mode=NpcMagicPronePolicy.RECOVER_SELF):
    base = native(completed_wizard=active, rounds=rounds)
    return replace(base, battered_leg_continuation=replace(base.battered_leg_continuation, prone_policy=mode))


def actual(scenario, values):
    rng = Dice(values)
    result = run_npc_magic_scenario(scenario, rng)
    rng.exhausted()
    return result


class BatteredLegRecoverNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = actual(source(), RECOVER_ROUND)
        cls.index = next(i for i,s in enumerate(cls.result.steps)
                         if isinstance(s.result, NpcRosterBatteredLegRecoverResult))
        cls.recovery = cls.result.steps[cls.index]

    def before_history(self):
        history = initial_magic_battered_leg_history(self.result.source)
        for step in self.result.steps[:self.index]:
            history = advance_magic_battered_leg_history(self.result.source, history, step)
        return history

    def test_recover_replaces_casting_spends_one_action_and_preserves_free_movement(self):
        result, step = self.result, self.recovery
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
        self.assertEqual((result.executed_actions, result.completed_rounds), (3, 1))
        self.assertFalse(any(isinstance(s.result, NpcRosterCastingResult) for s in result.steps))
        self.assertIs(step.before.round_state.active_turn.action_slots[0].declaration.kind, CombatActionKind.RECOVER)
        self.assertTrue(step.after.round_state.active_turn.action_slots[0].executed)
        self.assertEqual(step.after.consumed_execution_ids, (*step.before.consumed_execution_ids, step.id))
        self.assertEqual(step.before.spatial_state, step.after.spatial_state)
        old = step.before.roster.participant('wizard').state.injury
        new = step.after.roster.participant('wizard').state.injury
        self.assertEqual(old.wounds, new.wounds)
        self.assertFalse(new.conditions.has(Condition.PRONE))
        self.assertFalse(new.active_wound_effects)
        self.assertEqual(step.after.battered_leg_receipt.endurance, step.before.battered_leg_receipt.endurance)
        self.assertEqual(result.current.battered_leg_receipt.prone_recover, step.result)
        self.assertIsNone(result.current.battered_leg_receipt.prone_stand)

    def test_active_casting_reduces_pool_before_skipped_test_without_inventing_trigger(self):
        result = actual(source(active=True, rounds=2), ACTIVE_CASTING)
        step, = (s for s in result.steps if isinstance(s.result, NpcRosterBatteredLegRecoverResult))
        self.assertIs(result.outcome, Outcome.ROUND_LIMIT_REACHED)
        self.assertEqual((step.before.wizard.magic_state.miscast_dice,
                          step.result.recover.resolution.magic_state.miscast_dice,
                          step.after.wizard.magic_state.miscast_dice), (1, 0, 1))
        self.assertIsNotNone(step.result.interruption)
        self.assertIsNone(step.result.interruption.miscast_pool.roll_request)
        self.assertEqual(replace(step.before.wizard.magic_state, miscast_dice=1), step.after.wizard.magic_state)
        self.assertEqual(result.executed_actions, 6)

    def test_later_close_scene_and_spent_free_move_still_allow_standard_recover(self):
        # Author a later full-owner scene; initial Shooting scenes exclude Close.
        scenario, state = self.result.source, self.recovery.before
        old_zone = state.spatial_state.placement_for('wizard').zone_id
        later_zone = next(z for z in state.spatial_state.graph.zone_ids if z != old_zone)
        placements = tuple(replace(p, zone_id=later_zone) for p in state.spatial_state.placements)
        state = replace(state, spatial_state=replace(state.spatial_state, placements=placements,
            free_move_used_entity_ids=(*state.spatial_state.free_move_used_entity_ids, 'wizard')))
        frame = authored_frame(state)
        frame = replace(frame, pair_ranges=tuple(replace(p, target_range=RangedWeaponRange.CLOSE)
            if 'wizard' in (p.first_actor_id,p.second_actor_id) else p for p in frame.pair_ranges))
        changed = replace(scenario, scene_frames=(*scenario.scene_frames, frame))
        history = NpcMagicBatteredLegHistory(state, self.before_history().completion)
        self.assertTrue(magic_battered_leg_recover_selected(changed,state,'wizard',history))
        self.assertIsNone(diagnose_npc_magic_unsupported(changed,state,'later-close',battered_leg_history=history))
        request = NpcRosterBatteredLegRecoverRequest('later-close:recover',state,'wizard')
        self.assertTrue(request.recover_request.actor_has_enemy_in_zone)
        result = execute_npc_roster_battered_leg_recover(request,Mock(randint=Mock(side_effect=AssertionError('no RNG'))))
        self.assertFalse(result.completed_injury.conditions.has(Condition.PRONE))
        self.assertEqual(result.state.spatial_state,state.spatial_state)

    def test_journal_transport_rejects_missing_recover_and_mode_or_receipt_substitution(self):
        self.assertEqual(replace(pickle.loads(pickle.dumps(self.result))), self.result)
        with self.assertRaises(ValueError):
            replace(self.result,steps=(*self.result.steps[:self.index],*self.result.steps[self.index+1:]))
        for mode in (None,NpcMagicPronePolicy.SELF_STAND_WHEN_SAFE):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                replace(self.result,source=source(mode=mode))
        history=self.before_history()
        with self.assertRaises(ValueError):
            NpcMagicBatteredLegHistory(self.recovery.after,history.completion)
        with self.assertRaises(ValueError):
            replace(self.recovery.after.battered_leg_receipt,
                    prone_recover=replace(self.recovery.result,source=replace(self.recovery.result.source,id='foreign')))

    def test_new_staggered_after_recover_keeps_receipt_and_bounded_stop(self):
        result=actual(source(rounds=2),(*RECOVER_ROUND,1,10,10,10,10,10))
        self.assertIs(result.unsupported.reason,Reason.END_TURN)
        self.assertEqual(result.unsupported.missing_actor_ids,('wizard',))
        self.assertIsNotNone(result.current.battered_leg_receipt.prone_recover)
        self.assertTrue(result.current.roster.participant('wizard').state.injury.conditions.has(Condition.STAGGERED))

    def test_already_triggered_pool_cannot_bypass_mandatory_continuation(self):
        before=self.recovery.before
        magic=replace(before.wizard.magic_state,miscast_dice=3,casting_lore_id='lore:battle-magic')
        with self.assertRaisesRegex(ValueError,'mandatory Miscast'):
            replace(before,wizard=replace(before.wizard,magic_state=magic))

    def test_later_casting_miscast_preserves_recover_receipt_through_preparation_and_roll(self):
        scenario=replace(source(rounds=2),miscast_continuation=continuation_policy())
        result=actual(scenario,(*RECOVER_ROUND,*((10,)*6),9,9,9,1,1,1))
        self.assertIs(result.unsupported.reason,Reason.MISCAST_EFFECT)
        recovery,=(s.result for s in result.steps if isinstance(s.result,NpcRosterBatteredLegRecoverResult))
        self.assertEqual(result.current.battered_leg_receipt.prone_recover,recovery)
        origins=[s.origin_witness for s in result.steps if s.origin_witness is not None]
        self.assertEqual(len(origins),1)
        self.assertIsInstance(origins[0],NpcRosterCastingResult)
        self.assertEqual(replace(result),result)


if __name__=='__main__':
    unittest.main()
