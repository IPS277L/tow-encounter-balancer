"""Source-bound standard Recover consumes a slot and preserves Battered Leg."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from tests.helpers import SequenceRandom
from tests.unit.test_m8_battered_leg_prone_stand import source as stand_source
from towr.domain.action_execution_models import SkippedCastingTestAfterActionRequest
from towr.domain.condition_models import Condition
from towr.domain.npc_roster_battered_leg_models import require_battered_leg_completion
from towr.domain.npc_roster_battered_leg_recover_models import NpcRosterBatteredLegRecoverRequest
from towr.domain.npc_roster_turn_models import _validate_phase_source
from towr.domain.npc_wound_turn_end_models import NpcWoundTurnEndRequest
from towr.domain.turn_models import CombatActionDeclaration, CombatActionKind
from towr.engine import npc_roster_battered_leg_recover as engine
from towr.rules.casting_interruption_resolution import resolve_skipped_casting_test_after_action
from towr.rules.npc_roster_battered_leg_prone_resolution import stand_npc_roster_battered_leg_prone
from towr.rules.npc_wound_turn_end import end_npc_wound_turn


def source(*, spent=False, pool=1, casting=True):
    state = stand_source().state
    turn = state.round_state.active_turn
    slot = replace(turn.action_slots[0], declaration=CombatActionDeclaration(CombatActionKind.RECOVER))
    combat = replace(state.round_state, active_turn=replace(turn, action_slots=(slot,)))
    magic = replace(state.wizard.magic_state, miscast_dice=pool,
        casting_lore_id=state.wizard.magic_state.casting_lore_id if casting else None,
        casting_successes=state.wizard.magic_state.casting_successes if casting else 0,
        latest_casting_roll_successes=state.wizard.magic_state.latest_casting_roll_successes if casting else 0)
    spatial = state.spatial_state if not spent else replace(state.spatial_state,
        free_move_used_entity_ids=(*state.spatial_state.free_move_used_entity_ids, state.wizard.actor_id))
    state = replace(state, round_state=combat, wizard=replace(state.wizard, magic_state=magic),
        spatial_state=spatial, champion_attack=replace(state.champion_attack, round_state=combat))
    return NpcRosterBatteredLegRecoverRequest('battered:recover', state, state.wizard.actor_id)


class BatteredLegRecoverTests(unittest.TestCase):
    def test_standard_recover_removes_prone_and_consumes_only_the_action_slot(self):
        request = source()
        before = deepcopy(request)
        rng = Mock(wraps=SequenceRandom(()))
        with patch.object(engine, 'execute_recover_action', wraps=engine.execute_recover_action) as lower:
            result = engine.execute_npc_roster_battered_leg_recover(request, rng)
        lower.assert_called_once_with(request.recover_request, rng)
        rng.randint.assert_not_called()
        after = engine.apply_npc_roster_battered_leg_recover(request.state, result)
        self.assertEqual(request, before)
        self.assertTrue(after.round_state.active_turn.action_slots[0].executed)
        self.assertEqual(after.round_state.active_turn.action_slots[0].declaration.kind, CombatActionKind.RECOVER)
        self.assertEqual(after.consumed_execution_ids, (*request.state.consumed_execution_ids, request.id))
        self.assertEqual(after.spatial_state, request.state.spatial_state)
        injury = after.roster.participant(request.actor_id).state.injury
        self.assertFalse(injury.conditions.has(Condition.PRONE))
        self.assertEqual(injury.active_wound_effects, ())
        self.assertEqual(injury.wounds, request.state.roster.participant(request.actor_id).state.injury.wounds)
        self.assertFalse(injury.wounds[0].treated)
        self.assertFalse(injury.wounds[0].healed)
        self.assertEqual(after.champion_attack.roster, after.roster)
        self.assertEqual(after.minion_attack.roster, after.roster)
        for name in ('daily_wounds', 'consumed_execution_ids', 'consumed_wound_roll_ids'):
            self.assertEqual(getattr(after.champion_attack, name), getattr(request.state.champion_attack, name))
        self.assertEqual(after.battered_leg_receipt.endurance, request.state.battered_leg_receipt.endurance)
        self.assertEqual(after.battered_leg_receipt.prone_recover, result)
        self.assertIsNone(after.battered_leg_receipt.prone_stand)
        require_battered_leg_completion(after)

    def test_enemy_in_same_zone_and_spent_free_move_are_allowed(self):
        request = source(spent=True)
        self.assertTrue(request.recover_request.actor_has_enemy_in_zone)
        result = engine.execute_npc_roster_battered_leg_recover(request, SequenceRandom(()))
        self.assertEqual(result.state.spatial_state, request.state.spatial_state)
        self.assertEqual(result.recover.source_request.mode.value, 'standard')
        self.assertIsNone(result.recover.source_request.choice.staggered_target)
        self.assertIsNone(result.recover.source_request.choice.mount)
        self.assertIsNone(result.recover.source_request.choice.object_interaction)

    def test_recover_pool_reduction_precedes_skipped_casting_without_new_trigger(self):
        request = source(pool=2)
        with patch.object(engine, 'resolve_skipped_casting_test_after_action',
                wraps=engine.resolve_skipped_casting_test_after_action) as skipped:
            result = engine.execute_npc_roster_battered_leg_recover(request, SequenceRandom(()))
        skipped.assert_called_once()
        self.assertEqual(result.recover.resolution.magic_state.miscast_dice, 1)
        self.assertEqual(skipped.call_args.args[0].state, result.recover.resolution.magic_state)
        self.assertEqual(result.interruption.miscast_pool.previous_miscast_dice, 1)
        self.assertEqual(result.state.wizard.magic_state, request.state.wizard.magic_state)
        self.assertIsNone(result.state.pending_interruption)
        wrong = resolve_skipped_casting_test_after_action(SkippedCastingTestAfterActionRequest(
            request.id + ':skipped-casting', request.actor_id, result.recover.slot.execution,
            request.state.wizard.magic_state, request.state.wizard.caster.wizard_level,
            request.state.consumed_execution_ids))
        self.assertIsNotNone(wrong.miscast_pool.roll_request)
        with self.assertRaisesRegex(ValueError, 'skipped Casting result'):
            replace(result, interruption=wrong)

    def test_zero_active_pool_gets_one_skipped_die_and_inactive_casting_gets_none(self):
        active = engine.execute_npc_roster_battered_leg_recover(source(pool=0), SequenceRandom(()))
        self.assertEqual(active.recover.resolution.miscast_dice_removed, 0)
        self.assertEqual(active.state.wizard.magic_state.miscast_dice, 1)
        inactive = engine.execute_npc_roster_battered_leg_recover(source(pool=2, casting=False), SequenceRandom(()))
        self.assertIsNone(inactive.interruption)
        self.assertEqual(inactive.state.wizard.magic_state.miscast_dice, 1)
        self.assertIsNone(inactive.state.wizard.magic_state.casting_lore_id)

    def test_completed_recover_can_end_the_wizard_turn(self):
        result = engine.execute_npc_roster_battered_leg_recover(source(), SequenceRandom(()))
        after = result.state
        ended = end_npc_wound_turn(NpcWoundTurnEndRequest('end:recover', after, after.wizard.actor_id)).state
        self.assertIsNone(ended.round_state.active_turn)
        self.assertIn(after.wizard.actor_id, ended.round_state.completed_turn_entity_ids)
        self.assertEqual(ended.battered_leg_receipt, after.battered_leg_receipt)

    def test_casting_slot_foreign_actor_and_completed_action_cannot_recover(self):
        state = stand_source().state
        with self.assertRaisesRegex(ValueError, 'Recover slot'):
            NpcRosterBatteredLegRecoverRequest('wrong', state, state.wizard.actor_id)
        with self.assertRaisesRegex(ValueError, 'owner Wizard'):
            replace(source(), actor_id='brigand:0')
        after = engine.execute_npc_roster_battered_leg_recover(source(), SequenceRandom(())).state
        with self.assertRaises(ValueError):
            NpcRosterBatteredLegRecoverRequest('repeat', after, after.wizard.actor_id)

    def test_duplicate_and_stale_application_reject_before_projection(self):
        request = source()
        result = engine.execute_npc_roster_battered_leg_recover(request, SequenceRandom(()))
        with self.assertRaisesRegex(ValueError, 'already consumed'):
            engine.apply_npc_roster_battered_leg_recover(result.state, result)
        stale = replace(request.state, wizard=replace(request.state.wizard,
            magic_state=replace(request.state.wizard.magic_state, miscast_dice=2)))
        with self.assertRaisesRegex(ValueError, 'stale complete owner'):
            engine.apply_npc_roster_battered_leg_recover(stale, result)

    def test_recover_receipt_cannot_strip_consumption_or_reset_action_proof(self):
        request = source()
        after = engine.execute_npc_roster_battered_leg_recover(request, SequenceRandom(())).state
        with self.assertRaisesRegex(ValueError, 'consumed Recover action'):
            replace(after, consumed_execution_ids=request.state.consumed_execution_ids)
        with self.assertRaisesRegex(ValueError, 'same-turn Recover action proof'):
            replace(after, round_state=request.state.round_state,
                champion_attack=replace(after.champion_attack, round_state=request.state.round_state))
        stripped = replace(after, battered_leg_receipt=request.state.battered_leg_receipt)
        with self.assertRaisesRegex(ValueError, 'completed Test scope'):
            _validate_phase_source(stripped)

    def test_stand_and_recover_witnesses_are_mutually_exclusive(self):
        result = engine.execute_npc_roster_battered_leg_recover(source(), SequenceRandom(()))
        stood = stand_npc_roster_battered_leg_prone(stand_source())
        with self.assertRaisesRegex(ValueError, 'only once'):
            replace(result.state.battered_leg_receipt, prone_stand=stood)

    def test_raw_source_and_action_result_aliases_reject(self):
        request = deepcopy(source())
        injury = request.state.roster.participant(request.actor_id).state.injury
        object.__setattr__(injury.conditions, 'conditions', frozenset(('prone',)))
        rng = Mock()
        with self.assertRaises(TypeError):
            engine.execute_npc_roster_battered_leg_recover(request, rng)
        rng.randint.assert_not_called()
        result = deepcopy(engine.execute_npc_roster_battered_leg_recover(source(), SequenceRandom(())))
        object.__setattr__(result.recover.resolution, 'miscast_dice_removed', True)
        with self.assertRaises(TypeError):
            replace(result)
        result = deepcopy(engine.execute_npc_roster_battered_leg_recover(source(), SequenceRandom(())))
        object.__setattr__(result.interruption.miscast_pool, 'outcome', result.interruption.miscast_pool.outcome.value)
        with self.assertRaises(TypeError):
            replace(result)


if __name__ == '__main__':
    unittest.main()
